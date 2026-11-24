"""Transport for KnowledgeClipper's shared workflow. The host owns credentials and quota."""
import base64
import io
import json
import os
import re
import socket
import ssl
import subprocess
import sys
from contextlib import closing
from functools import partial
from http.client import HTTPSConnection, HTTPException
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import BoundedSemaphore
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit
from zipfile import BadZipFile, ZipFile

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field
from PIL import Image

from .clipper_settings import Preferences, catalog, provider_post
from .judge import independent_settings
from .openai_vision import configured_vision, openai_vision_post
from .service import DomainError


SETTINGS = '/api/clipper/settings'
RULES = '/api/clipper/rules'
GATEWAY = '/api/clipper/workflow'
REFERENCE = '/api/clipper/reference'


class Reference(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(min_length=1, max_length=3000)


def reference_read(url):
    endpoint = urlsplit(url)
    query = dict(parse_qsl(endpoint.query, strict_parsing=True))
    host, path = endpoint.netloc, endpoint.path
    allowed = False
    if endpoint.scheme == 'https' and not endpoint.fragment:
        if host == 'en.wiktionary.org' and path.startswith('/api/rest_v1/page/definition/'):
            word = path.removeprefix('/api/rest_v1/page/definition/')
            allowed = bool(word and '/' not in word and not query)
        if host == 'en.wiktionary.org' and path == '/w/api.php':
            allowed = (set(query) <= {'action', 'page', 'prop', 'section', 'format'} and query.get('action') == 'parse'
                       and query.get('format') == 'json' and query.get('prop') in ('sections', 'text') and bool(query.get('page')))
        if host == 'api.tatoeba.org' and path == '/v1/sentences':
            allowed = (set(query) == {'lang', 'q', 'sort', 'limit', 'is_unapproved', 'is_orphan'} and bool(query['q'])
                       and query['lang'] in ('eng', 'cmn') and query['limit'] == '20' and query['sort'] == 'relevance'
                       and query['is_unapproved'] == query['is_orphan'] == 'no')
    if not allowed:
        raise DomainError('invalid_clip_reference', '词典和语料请求无效。', 422)
    with closing(HTTPSConnection(host, timeout=9)) as connection:
        connection.request('GET', path + ('?' + urlencode(query) if query else ''),
                           headers={'User-Agent': 'KnowledgeClipper/1.0 (personal learning dictionary)', 'Accept': 'application/json'})
        with connection.getresponse() as response:
            if response.status != 200:
                return {'status': response.status, 'content': '{}', 'mime': 'application/json'}
            body = response.read(2 * 1024 * 1024 + 1)
            if len(body) > 2 * 1024 * 1024:
                raise ValueError
            return {'status': 200, 'content': body.decode(), 'mime': 'application/json'}


class Operation(BaseModel):
    model_config = ConfigDict(extra='forbid')
    operation: Literal['model', 'speech', 'ocr']
    input: dict


def configured_service(name):
    if name == 'ocr' and (runner := os.environ.get('GRASPMEMOEDU_CLIPPER_MINERU_RUNNER')):
        return {'mineru_runner': runner}
    prefix = 'GRASPMEMOEDU_CLIPPER_' + name.upper() + '_'
    values = {local: os.environ.get(prefix + env, '').strip() for local, env in
              [('base_url', 'BASE_URL'), ('api_key', 'API_KEY'), ('model', 'MODEL')]}
    if not all(values.values()):
        raise DomainError('clip_service_unconfigured', '该站点服务尚未配置，可在剪藏设置中绑定自有服务。', 503)
    return values


def public_models(prefs, default_model):
    binding = prefs['bindings'].get('model') or {}
    if binding.get('active'):
        return binding['model'], binding['model']
    try:
        model = default_model()['model']
    except (ValueError, DomainError):
        model = ''
    image_model = os.environ.get('GRASPMEMOEDU_OPENAI_VISION_MODEL', '').strip()
    return model, image_model or os.environ.get('GRASPMEMOEDU_CLIPPER_IMAGE_MODEL', model)


def checked_png(data):
    try:
        raw = base64.b64decode(data, validate=True)
        if len(raw) > 32 * 1024 * 1024:
            raise ValueError
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != 'PNG' or image.width * image.height > 24_000_000:
                raise ValueError
            image.verify()
        return raw
    except (OSError, ValueError, TypeError, Image.DecompressionBombError):
        raise DomainError('invalid_clip_image', '请选择有效的 PNG 图片。', 422) from None


def model_call(config, allowed, source, timeout):
    payload = json.loads(source['body'])
    model = payload.get('model')
    if model not in allowed or not isinstance(payload.get('messages'), list) or not 1 <= len(payload['messages']) <= 600:
        raise DomainError('invalid_clip_model', '请选择当前账号可用的模型。', 422)
    messages = []
    has_image = False
    for item in payload['messages']:
        role, content = item['role'], item['content']
        if role not in ('user', 'system', 'assistant'):
            raise ValueError
        if isinstance(content, list):
            parts = []
            for part in content:
                if part['type'] == 'text' and isinstance(part.get('text'), str):
                    parts.append({'type': 'text', 'text': part['text']})
                elif part['type'] == 'image_url':
                    url = part['image_url']['url']
                    if not isinstance(url, str) or not url.startswith('data:image/png;base64,'):
                        raise ValueError
                    checked_png(url[22:])
                    has_image = True
                    parts.append({'type': 'image_url', 'image_url': {'url': url}})
                else:
                    raise ValueError
            # Text-only services also accept the original plain text representation.
            content = ''.join(p['text'] for p in parts) if all(p['type'] == 'text' for p in parts) else parts
        elif not isinstance(content, str):
            raise ValueError
        messages.append({'role': role, 'content': content})
    params = {'model': model, 'messages': messages, 'stream': payload.get('stream') is True}
    if payload.get('response_format') == {'type': 'json_object'}:
        params['response_format'] = payload['response_format']
    if type(payload.get('max_tokens')) is int:
        params['max_tokens'] = max(1, min(16384, payload['max_tokens']))
    if payload.get('thinking') == {'type': 'disabled'}:
        params['thinking'] = payload['thinking']
    if type(payload.get('temperature')) in (int, float):
        params['temperature'] = min(2, max(0, payload['temperature']))
    vision = configured_vision() if config.get('site_service') and has_image else None
    if vision:
        params['model'] = vision['model']
        if 'max_tokens' in params:
            params['max_completion_tokens'] = params.pop('max_tokens')
        params.pop('thinking', None)
        params.update(reasoning_effort='none', store=False, service_tier='default')
        body = openai_vision_post(vision, '/v1/chat/completions', params, timeout, 4 * 1024 * 1024)
    else:
        if config.get('site_service') and model == os.environ.get('GRASPMEMOEDU_OPENAI_VISION_MODEL'):
            params['model'] = config['model']
        body, _ = provider_post(config, '/chat/completions', params, timeout, 4 * 1024 * 1024)
    return {'status': 200, 'mime': 'text/event-stream' if params['stream'] else 'application/json',
            'content': body.decode('utf-8')}


def openai_over_ssh(port, url, *, timeout, **options):
    import websocket

    endpoint = urlsplit(url)
    if endpoint.scheme != 'wss' or endpoint.netloc != 'api.openai.com':
        raise ValueError('The SSH forward is reserved for OpenAI Realtime')
    try:
        with socket.create_connection(('127.0.0.1', port), timeout=min(timeout, 10)) as raw:
            tls = ssl.create_default_context().wrap_socket(raw, server_hostname=endpoint.hostname)
        try:
            return websocket.create_connection(url, socket=tls, timeout=timeout, **options)
        except BaseException:
            tls.close()
            raise
    except (OSError, websocket.WebSocketException):
        raise DomainError('clip_speech_unavailable', '暂时无法连接站点的朗读服务，可稍后重试。', 502) from None


def speech_call(config, source, timeout):
    text, voice = source['text'], source['voice']
    if not isinstance(text, str) or not text.strip() or len(text) > 18000 or not isinstance(voice, str) or len(voice) > 160:
        raise ValueError
    if int(source.get('pitchHz', 0)):
        raise DomainError('clip_audio_pitch', '当前语音服务不支持独立调节音高，请将音调设为 0。', 422)
    speed = max(.5, min(2, 1 + int(source.get('ratePercent', 0)) / 100))
    volume = max(0, min(3, 1 + int(source.get('volumePercent', 0)) / 100))
    endpoint = config['base_url'].rstrip('/')
    from mimo_tts import client, openai_audio
    synthesize = None
    transport = {}
    if endpoint == 'https://api.openai.com/v1' and config['model'] == openai_audio.MODEL:
        synthesize = openai_audio.synthesize
        voice = voice.removeprefix('openai-')
        if config.get('site_service') and (port := os.environ.get('GRASPMEMOEDU_CLIPPER_OPENAI_SSH_PORT')):
            if not port.isascii() or not port.isdecimal() or len(port) > 5 or not 1024 <= int(port) <= 65535:
                raise DomainError('clip_service_unconfigured', '站点朗读转发端口配置无效。', 503)
            transport['connect'] = partial(openai_over_ssh, int(port))
    elif endpoint == client.BASE_URL and config['model'] == client.MODELS['preset']:
        synthesize = client.synthesize
        voice = voice.removeprefix('mimo-')
        if voice not in client.VOICES:
            voice = client.default_voice(text)
    if synthesize:
        try:
            with TemporaryDirectory() as folder:
                recording = Path(folder) / 'speech.mp3'
                synthesize(text, recording, voice=voice, style=str(source.get('style', ''))[:3000],
                           api_key=config['api_key'], cache=False, speed=speed, volume=volume, **transport)
                if recording.stat().st_size > 12 * 1024 * 1024:
                    raise ValueError
                return {'mime': 'audio/mpeg', 'data': base64.b64encode(recording.read_bytes()).decode()}
        except client.MimoError:
            raise DomainError('clip_audio_failed', '语音服务没有生成可用录音，可重新朗读。', 502) from None
    data = {'model': config['model'], 'input': text, 'voice': voice, 'response_format': 'mp3', 'speed': speed}
    if source.get('style'):
        data['instructions'] = str(source['style'])[:3000]
    body, mime = provider_post(config, '/audio/speech', data, timeout, 12 * 1024 * 1024)
    if not mime.startswith('audio/') and mime != 'application/octet-stream':
        raise DomainError('clip_audio_failed', '语音服务未返回录音。', 502)
    if not (body.startswith(b'ID3') or len(body) > 2 and body[0] == 255 and (body[1] & 224) == 224):
        raise DomainError('clip_audio_failed', '语音服务未返回有效的 MP3 录音。', 502)
    if volume != 1:
        from mimo_tts.client import MimoError, transcode
        try:
            with TemporaryDirectory() as tmp:
                original, adjusted = Path(tmp) / 'original.mp3', Path(tmp) / 'adjusted.mp3'
                original.write_bytes(body)
                transcode(original, adjusted, volume=volume)
                body = adjusted.read_bytes()
        except MimoError:
            raise DomainError('clip_audio_failed', '录音音量调整失败，可重新朗读。', 502) from None
    return {'mime': 'audio/mpeg', 'data': base64.b64encode(body).decode()}


def mineru_text(runner, raw, source, timeout):
    program = Path(runner)
    if not program.is_absolute() or not program.is_file():
        raise DomainError('clip_service_unconfigured', '站点的 MinerU 程序尚未安装。', 503)
    language = source.get('mineruLanguage', 'ch')
    if not isinstance(language, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,31}', language):
        raise ValueError
    with TemporaryDirectory() as tmp:
        folder = Path(tmp)
        image, output = folder / 'selection.png', folder / 'result'
        image.write_bytes(raw)
        args = [sys.executable, str(program), str(image), '--output-dir', str(output), '--model-version', 'vlm',
                '--language', language, '--timeout', str(timeout), '--poll-interval', '3']
        for key, flag in [('mineruTable', '--no-table'), ('mineruFormula', '--no-formula')]:
            if not source.get(key, True):
                args.append(flag)
        inherited = {'PATH','HOME','USERPROFILE','SYSTEMROOT','PATHEXT','COMSPEC','LOCALAPPDATA',
                     'TEMP','TMP','TMPDIR','LANG','LC_ALL','SSL_CERT_FILE','SSL_CERT_DIR','MINERU_API_BASE','MINERU_API_TOKEN'}
        env = {k:v for k,v in os.environ.items() if k.upper() in inherited}
        env['NO_PROXY'] = '*'
        try:
            subprocess.run(args, cwd=program.parent, env=env, stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout+120, check=True)
            manifest, = output.rglob('manifest.json')
            result, = json.loads(manifest.read_bytes())['results']
            archive, = manifest.parent.rglob('mineru-result.zip')
            markdown, = manifest.parent.glob('*.md')
            if result.get('state') != 'done' or markdown.stat().st_size > 256*1024:
                raise ValueError
            with ZipFile(archive) as contents:
                if not any(name.lower().endswith('.md') for name in contents.namelist()) or contents.testzip():
                    raise ValueError
            text = markdown.read_text(encoding='utf-8')
            if not text.strip():
                raise ValueError
            return {'text': text}
        except (OSError, ValueError, KeyError, BadZipFile, subprocess.SubprocessError):
            raise DomainError('clip_ocr_failed', 'MinerU 未返回完整的识别结果，原图仍在草稿中。', 502) from None


def ocr_call(config, source, timeout):
    raw = checked_png(source['data'])
    if config.get('site_service') and config.get('mineru_runner'):
        return mineru_text(config['mineru_runner'], raw, source, timeout)
    instructions = ('逐字识别图片，按阅读顺序输出原文。保留换行。'
                    + ('保留 Markdown 表格。' if source.get('mineruTable') else '')
                    + ('公式保留 LaTeX。' if source.get('mineruFormula') else ''))
    data = {'model': config['model'], 'messages': [
        {'role': 'system', 'content': instructions},
        {'role': 'user', 'content': [{'type': 'text', 'text': 'OCR 语言：' + str(source.get('mineruLanguage', 'ch'))[:160]},
                                     {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,' + source['data']}}]}]}
    body, _ = provider_post(config, '/chat/completions', data, timeout, 256 * 1024)
    choice = json.loads(body)['choices'][0]
    if choice['finish_reason'] != 'stop' or not isinstance(choice['message']['content'], str):
        raise ValueError
    return {'text': choice['message']['content']}


def register_gateway(app, store, slots, model_settings):
    preferences = store.preferences
    reference_slots = BoundedSemaphore(16)

    def default_model():
        return model_settings() or independent_settings()

    def public(owner, prefs):
        model, image = public_models(prefs, default_model)
        return {**prefs, 'workflow': catalog()['workflow'], 'model': model, 'imageModel': image}

    @app.get(SETTINGS)
    def settings(request: Request):
        owner = request.state.clipper_access['learner_id']
        return public(owner, preferences.read(owner))

    @app.post(SETTINGS)
    def save_settings(update: Preferences, request: Request):
        owner = request.state.clipper_access['learner_id']
        return public(owner, preferences.save(owner, update))

    @app.get(RULES)
    def default_rules(request: Request):
        return {'rules': catalog()['rules']}

    @app.post(REFERENCE)
    def reference(call: Reference, request: Request):
        if not reference_slots.acquire(blocking=False):
            raise DomainError('clip_reference_busy', '词典服务正忙。', 503)
        try:
            return reference_read(call.url)
        except (ValueError, OSError, HTTPException):
            raise DomainError('clip_reference_failed', '开放语料未能返回结果。', 502) from None
        finally:
            reference_slots.release()

    @app.post(GATEWAY)
    def execute(call: Operation, request: Request):
        owner = request.state.clipper_access['learner_id']
        if not slots.acquire(blocking=False):
            raise DomainError('clip_model_busy', '剪藏服务正忙，请稍后重试。', 503)
        try:
            prefs = preferences.read(owner)
            timeout = prefs['values']['contentTimeoutSeconds']
            if call.operation == 'model':
                config = preferences.resolve(owner, 'model', default_model)
                allowed = public_models(prefs, default_model)
                if call.input.get('path') != '/chat/completions':
                    raise ValueError
                store.record_model_call(owner)
                return model_call(config, allowed, call.input, timeout)
            if call.operation == 'speech':
                config = preferences.resolve(owner, 'speech', lambda: configured_service('speech'))
                store.record_model_call(owner)
                return speech_call(config, call.input, timeout)
            config = preferences.resolve(owner, 'ocr', lambda: configured_service('ocr'))
            store.record_model_call(owner)
            return ocr_call(config, call.input, prefs['values']['mineruTimeoutSeconds'])
        except (OSError, ValueError, TypeError, KeyError, IndexError):
            raise DomainError('clip_service_failed', '剪藏服务未完成请求，草稿保留在当前浏览器。', 502) from None
        finally:
            slots.release()
