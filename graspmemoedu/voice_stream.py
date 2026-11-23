"""Short-lived duplex dictation sessions. The browser only receives a finalized answer."""
import base64
from concurrent.futures import Future, ThreadPoolExecutor
from hashlib import sha256
import os
from queue import Queue
from threading import BoundedSemaphore, Event, Lock, Thread, Timer
from time import monotonic
from typing import Annotated, Literal
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

from .access import credential_digest
from .service import DomainError
from .voice_input import format_voice
from .voice_math import VoiceContext, quick_math

STREAM_PATH = '/api/voice-input/stream'
MAX_AUDIO = 120 * 32000
MAX_CHUNK = 64000
STREAM_BODY_LIMIT = 512 * 1024  # A full UTF-8 statement on open, or a bounded base64 PCM frame.


class Message(BaseModel):
    model_config = ConfigDict(extra='forbid')
    take: UUID


class Open(Message):
    op: Literal['open']
    profile: Literal['general', 'answer', 'calculator', 'answer_commands']
    context: VoiceContext = Field(default_factory=VoiceContext)


class Chunk(Message):
    op: Literal['audio', 'pause', 'finish']
    offset: int = Field(strict=True, ge=0, le=MAX_AUDIO)
    pcm: str = Field(max_length=(MAX_CHUNK + 2) // 3 * 4)


class Cancel(Message):
    op: Literal['cancel']


Packet = Annotated[Open | Chunk | Cancel, Field(discriminator='op')]


class Recognizer:
    """Per-site SDK client and two send workers. Each take gets a separate recognition task."""
    def __init__(self):
        self.client = None
        self.workers = ThreadPoolExecutor(max_workers=2)
        self.lock = Lock()

    def prepare(self):
        with self.lock:
            if self.client is not None:
                return
            key = os.environ.get('GRASPMEMOEDU_ASR_API_KEY')
            if key and key != 'PENDING_LOCAL_ENTRY':
                from dashscope import Client
                self.client = Client(api_key=key, region='cn-beijing', timeout=18)

    def __call__(self, context, update):
        self.prepare()
        if self.client is None:
            raise DomainError('transcription_unavailable', '语音转写尚未配置。', 503)
        return Outbox(self.workers, lambda: Duplex(self.client, context, update))

    def close(self):
        self.workers.shutdown(wait=True, cancel_futures=True)
        if self.client:
            self.client.close()


class Outbox:
    """Accept ordered PCM while the SDK negotiates task-started, then drain before finish-task."""
    def __init__(self, workers, connect):
        self.frames, self.aborted = Queue(), Event()
        self.done = workers.submit(self.send, connect)

    def send(self, connect):
        provider = connect()
        try:
            while not self.aborted.is_set():
                pcm = self.frames.get()
                if pcm is None:
                    if not self.aborted.is_set():
                        provider.finish()
                    break
                provider.write(pcm)
        finally:
            provider.close()

    def write(self, pcm):
        if self.done.done():
            self.done.result()
            raise ValueError('Premature end of stream')
        self.frames.put(pcm)

    def finish(self):
        self.frames.put(None)
        self.done.result(timeout=35)

    def close(self):
        self.aborted.set()
        self.frames.put(None)
        self.done.cancel()


class Duplex:
    def __init__(self, client, context, update):
        self.session = client.audio.asr.recognize(model='fun-asr-realtime', input=context.asr_input(),
            parameters={'max_sentence_silence': 320, 'heartbeat': True}, timeout=18)
        self.done = Future()
        try:
            self.session.start()
        except Exception:
            self.close()
            raise
        def receive():
            try:
                for result in self.session.results():
                    sentence = result.get_sentence()
                    if sentence:
                        update(sentence)
                self.done.set_result(None)
            except Exception:
                self.done.set_exception(DomainError('voice_stream_failed', '语音连接中断，请重试转写。', 502))
        Thread(target=receive, daemon=True).start()

    def write(self, pcm):
        if self.done.done():
            self.done.result()
            raise ValueError('Premature end of stream')
        self.session.send_audio_frame(pcm)

    def finish(self):
        self.session.stop()
        self.done.result(timeout=18)

    def close(self):
        self.session.close()


class Take:
    def __init__(self, opened, factory, formatter, speculate):
        self.opened, self.factory, self.formatter, self.speculate = opened, factory, formatter, speculate
        self.lock, self.sentences_lock = Lock(), Lock()
        self.provider = self.timer = self.pending = None
        self.offset = self.attempts = self.segments = 0
        self.sentences, self.prefix, self.last = {}, '', None
        self.closed = self.paused = False
        self.used = self.started = monotonic()

    def start_segment(self):
        if self.segments >= 24:
            raise DomainError('voice_pause_limit', '这段录音已多次暂停，请结束后再开始一段。', 422)
        self.segments += 1
        self.provider = self.factory(self.opened.context, self.update)
        self.paused = False

    def current_text(self):
        return (self.prefix + ''.join(self.sentences[index][0] for index in sorted(self.sentences))).strip()

    @staticmethod
    def key(text):
        return text.strip().rstrip('。')

    def update(self, sentence):
        index, text = sentence.get('sentence_id'), sentence.get('text')
        if type(index) is not int or not 0 <= index < 4096 or not isinstance(text, str):
            raise ValueError('Invalid recognition event')
        with self.sentences_lock:
            if self.closed:
                return
            self.sentences[index] = text, sentence.get('sentence_end', sentence.get('end_time') is not None) is True
            full = self.current_text()
            if len(full) > 16000:
                raise ValueError('Transcript too long')
            if self.timer:
                self.timer.cancel()
            if self.opened.profile in ('answer', 'calculator') and full and self.attempts < 3:
                self.timer = Timer(.25, self.prepare, args=(full,))
                self.timer.daemon = True
                self.timer.start()

    def prepare(self, text):
        with self.sentences_lock:
            if self.closed or self.key(text) != self.key(self.current_text()) or self.attempts >= 3:
                return
            if self.pending and (self.pending[0] == self.key(text) or not self.pending[1].done()):
                return
            if quick_math(text, self.opened.profile, self.opened.context) is not None:
                return
            work = self.speculate(self.formatter, text, self.opened.profile, self.opened.context)
            if work is not None:
                self.pending = self.key(text), work
                self.attempts += 1

    def end_segment(self):
        if self.provider is not None:
            try:
                self.provider.finish()
            finally:
                self.provider.close()
                self.provider = None
            with self.sentences_lock:
                if any(text and not final for text, final in self.sentences.values()):
                    raise DomainError('voice_incomplete', '未收到完整的转写，请重试。', 502)
                self.prefix = self.current_text()
                self.sentences.clear()
        self.paused = True

    def consume(self, packet, pcm, signature):
        if self.last and self.last[0] == signature:
            return self.last[1]
        if packet.offset != self.offset:
            raise DomainError('voice_offset', '录音片段顺序已改变，请重试。', 409)
        if self.offset + len(pcm) > MAX_AUDIO or not pcm and packet.op == 'audio':
            raise DomainError('invalid_recording', '录音片段为空或超过时长。', 422)
        if pcm:
            if not self.provider:
                self.start_segment()
            self.provider.write(pcm)
            self.offset += len(pcm)
        if packet.op in ('pause', 'finish'):
            self.end_segment()
        response = {'offset': self.offset}
        if packet.op == 'finish':
            with self.sentences_lock:
                self.closed = True
                if self.timer:
                    self.timer.cancel()
                final, pending = self.prefix, self.pending
            if not final:
                raise DomainError('voice_empty', '未识别到语音。', 422)
            if pending and self.key(final) == pending[0]:
                try:
                    response['text'] = pending[1].result()
                except Exception:
                    pass
            if 'text' not in response:
                response['text'] = self.formatter(final, self.opened.profile, self.opened.context)
        self.last = signature, response
        return response

    def close(self):
        with self.sentences_lock:
            self.closed = True
            if self.timer:
                self.timer.cancel()
        if self.provider:
            self.provider.close()
            self.provider = None


class Sessions:
    def __init__(self, slots, reserve, factory=None, formatter=format_voice):
        self.slots, self.reserve, self.formatter = slots, reserve, formatter
        self.factory = factory if factory is not None else Recognizer()
        self.lock = Lock()
        self.active, self.receipts = {}, {}
        self.workers, self.capacity = ThreadPoolExecutor(max_workers=2), BoundedSemaphore(2)

    def close(self):
        with self.lock:
            active = list(self.active.items())
        for key, take in active:
            with take.lock:
                self.retire(key, take)
        self.workers.shutdown(wait=True, cancel_futures=True)
        if isinstance(self.factory, Recognizer):
            self.factory.close()

    def speculate(self, fn, *args):
        if not self.capacity.acquire(blocking=False):
            return None
        future = self.workers.submit(fn, *args)
        future.add_done_callback(lambda _: self.capacity.release())
        return future

    def retire(self, key, take):
        # Call with the take lock held. Never wait for the provider under the registry lock.
        try:
            take.close()
        finally:
            with self.lock:
                if self.active.get(key) is take:
                    del self.active[key]
                    self.slots.release()

    def expire(self, key, take):
        with take.lock:
            if take.closed:
                return
            if monotonic() - take.used > (125 if take.paused else 20) or monotonic() - take.started > 300:
                self.retire(key, take)
                return
        self.schedule(key, take)

    def schedule(self, key, take):
        timer = Timer(10, self.expire, args=(key, take))
        timer.daemon = True
        timer.start()

    def forget(self, key, expiry):
        with self.lock:
            if key in self.receipts and self.receipts[key][0] == expiry:
                del self.receipts[key]

    def handle(self, account, scope, packet):
        key = scope, packet.take
        pcm, signature = b'', None
        if isinstance(packet, Chunk):
            try:
                pcm = base64.b64decode(packet.pcm, validate=True)
                if len(pcm) % 2 or len(pcm) > MAX_CHUNK:
                    raise ValueError()
            except ValueError:
                raise DomainError('invalid_recording', '录音片段格式无效。', 422) from None
            signature = packet.op, packet.offset, sha256(pcm).digest()
        with self.lock:
            now = monotonic()
            self.receipts = {k: v for k, v in self.receipts.items() if v[0] > now}
            if key in self.receipts:
                _, old, result = self.receipts[key]
                if signature == old:
                    return result
                if isinstance(packet, Cancel):
                    return {}
                raise DomainError('voice_finished', '这段录音已结束。', 409)
            take = self.active.get(key)
            if take is None:
                if isinstance(packet, Cancel):
                    return {}
                if not isinstance(packet, Open):
                    raise DomainError('voice_not_found', '录音连接已结束，请重试转写。', 404)
                if any(owner == scope for owner, _ in self.active) or not self.slots.acquire(blocking=False):
                    raise DomainError('transcription_busy', '语音转写繁忙，请稍后重试。', 429)
                take = Take(packet, self.factory, self.formatter, self.speculate)
                self.active[key] = take
        with take.lock:
            if take.closed:
                if take.last and signature == take.last[0]:
                    return take.last[1]
                raise DomainError('voice_finished', '这段录音已结束。', 409)
            take.used = monotonic()
            try:
                if isinstance(packet, Open):
                    if packet != take.opened:
                        raise DomainError('voice_context_changed', '录音目标已改变。', 409)
                    if not take.segments:
                        self.reserve(account)
                        take.start_segment()
                        self.schedule(key, take)
                    return {'offset': take.offset}
                if isinstance(packet, Cancel):
                    self.retire(key, take)
                    return {}
                if not take.segments:
                    raise DomainError('voice_opening', '录音连接尚在建立。', 409)
                result = take.consume(packet, pcm, signature)
                if packet.op == 'finish':
                    with self.lock:
                        if len(self.receipts) >= 64:
                            del self.receipts[next(iter(self.receipts))]
                        expiry = monotonic() + 30
                        self.receipts[key] = expiry, signature, result
                    timer = Timer(30, self.forget, args=(key, expiry))
                    timer.daemon = True
                    timer.start()
                    self.retire(key, take)
                return result
            except DomainError as error:
                if error.code not in ('voice_offset', 'voice_context_changed', 'voice_opening'):
                    self.retire(key, take)
                raise
            except Exception:
                self.retire(key, take)
                raise DomainError('voice_stream_failed', '流式转写未完成，请重试转写。', 502) from None


def register_voice_stream(app, access_store, slots, reserve):
    sessions = Sessions(slots, reserve)
    @app.post(STREAM_PATH)
    def stream(request: Request, payload: Packet):
        token = request.headers.get('x-learning-identity')
        access = access_store.resolve(token)
        if access.get('role') != 'account':
            raise DomainError('transcription_account_required', '请登录账号后使用语音转写。', 403)
        return sessions.handle(access, credential_digest('voice-take', token), payload)
    return sessions
