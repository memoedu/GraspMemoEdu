import base64
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Event
import unittest
from unittest.mock import Mock
from uuid import uuid4

from graspmemoedu.service import DomainError
from graspmemoedu.voice_input import refine_voice
from graspmemoedu.voice_math import VoiceContext, quick_math
from graspmemoedu.voice_stream import Cancel, Chunk, Open, Outbox, Sessions


class MathDictationTests(unittest.TestCase):
    def test_full_stem_reaches_formatter_and_recognizer_has_bounded_turns(self):
        stem = '请用题目定义的变量作答。' * 230 + '使用末尾条件。'
        context = VoiceContext(stem=stem, symbols=['a^{next}'])
        generator = Mock(return_value='其中，\\(a^{next}=4\\)')
        refine_voice('其中，下一个 a 是四', 'answer', generator, context=context)
        self.assertEqual(generator.call_args.args[1]['notation']['stem'], stem)
        turns = context.asr_input()['context']
        self.assertEqual(len(turns), 5)
        self.assertTrue(all(0 < len(turn['content'][0]['text']) <= 400 for turn in turns))
        self.assertTrue(turns[-1]['content'][0]['text'].endswith('使用末尾条件。'))
        short = VoiceContext(stem='平面上有三个点，求另一个点的坐标。')
        self.assertEqual(short.asr_input()['context'][0]['content'][0]['text'], short.stem)

    def test_same_audio_different_visible_question_and_explicit_indices(self):
        coordinates = VoiceContext(stem='写出点的坐标。', domains=['coordinates'], dimensions=2)
        scalar = VoiceContext(stem='写出点的横坐标。', domains=['coordinates'], dimensions=2)
        self.assertEqual(quick_math('-34。', 'answer', coordinates), '(-3,4)')
        self.assertEqual(quick_math('-34。', 'answer', scalar), '-34')
        self.assertEqual(quick_math('负三、四', 'answer', coordinates), '(-3,4)')
        self.assertEqual(quick_math('负十一', 'answer', coordinates), '-11')
        self.assertEqual(quick_math('a六', 'answer', VoiceContext(symbols=['a^{new}'])), 'a^{new}')
        self.assertEqual(quick_math('a六', 'answer', VoiceContext(symbols=['a_{6}'])), 'a_{6}')
        self.assertIsNone(quick_math('a六', 'answer', VoiceContext(symbols=['a^{new}', 'a_{new}'])))
        self.assertIsNone(quick_math('a四', 'answer', VoiceContext(symbols=['a^{new}'])))

    def test_math_scope_case_and_no_computation(self):
        for profile in ('calculator', 'answer'):
            self.assertEqual(quick_math('B加七减t', profile, VoiceContext(symbols=['B', 't'])), 'B+7-t')
            self.assertEqual(quick_math('二乘三等于七', profile, VoiceContext()), '2*3=7')
        integral = quick_math('积分，t的立方加五乘t，微分t', 'answer', VoiceContext())
        self.assertEqual(integral, r'\(\int t^3+5\cdot t\,dt\)')
        for phrase in ('积分。t的立方，加五乘，t。微分t', '积分t的立方加五，乘t，微分，t'):
            self.assertEqual(quick_math(phrase, 'answer', VoiceContext()), integral)
        self.assertIsNone(quick_math('积分，t的立方加五，整体乘t，微分t', 'answer', VoiceContext()))
        self.assertIsNone(quick_math('把积分的结果算出来', 'answer', VoiceContext()))
        named = VoiceContext(stem='两次测量分别记为 a 和 b，更新后的读数用 b 表示。', symbols=['a', 'b'])
        self.assertEqual(quick_math('更新后的读数等于五。', 'answer', named), 'b=5')
        named.stem = '温度用 a 表示，若改用另一套单位，温度用 b 表示。'
        self.assertIsNone(quick_math('温度等于五', 'answer', named))


class Provider:
    def __init__(self, context, update):
        self.update = update
        self.received = []
        self.final = '二加七'
        self.closed = False

    def write(self, data):
        self.received.append(data)
        self.update({'sentence_id': 0, 'text': '二加一', 'sentence_end': False})

    def finish(self):
        if self.final is not None:
            self.update({'sentence_id': 0, 'text': self.final, 'sentence_end': True})

    def close(self):
        self.closed = True


class VoiceSessionTests(unittest.TestCase):
    def test_capture_survives_slow_negotiation_and_immediate_stop(self):
        opening = Event()
        provider = Mock()
        def connect():
            assert opening.wait(timeout=1)
            return provider
        with ThreadPoolExecutor(max_workers=1) as workers:
            output = Outbox(workers, connect)
            output.write(b'first')
            output.write(b'last')
            opening.set()
            output.finish()
            output.close()
        self.assertEqual([call.args[0] for call in provider.write.call_args_list], [b'first', b'last'])
        provider.finish.assert_called_once()
        provider.close.assert_called_once()

    def setUp(self):
        self.providers = []
        def factory(context, update):
            provider = Provider(context, update)
            self.providers.append(provider)
            return provider
        self.reserve = Mock()
        self.registry = Sessions(BoundedSemaphore(2), self.reserve, factory, lambda t, p, c: t)
        self.account = {'learner_id': 'synthetic'}
        self.start = Open(op='open', take=uuid4(), profile='answer', context=VoiceContext(stem='合成题干'))
        self.call(self.start)
        self.addCleanup(lambda: self.call(Cancel(op='cancel', take=self.start.take)))
        self.addCleanup(self.registry.workers.shutdown)

    def call(self, packet, scope='account-session'):
        return self.registry.handle(self.account, scope, packet)

    def packet(self, op, offset=0, pcm=b''):
        return Chunk(op=op, take=self.start.take, offset=offset, pcm=base64.b64encode(pcm).decode())

    def test_revisions_are_private_and_tail_and_retries_commit_once(self):
        self.call(self.start)
        first = self.packet('audio', pcm=b'\x01\x02')
        self.assertEqual(self.call(first), {'offset': 2})
        self.assertEqual(self.call(first), {'offset': 2})
        with self.assertRaises(DomainError):
            self.call(self.packet('audio', offset=4, pcm=b'\x00\x00'))
        with self.assertRaises(DomainError):
            self.call(first, 'different-account')
        last = self.packet('finish', 2, b'\x03\x04')
        self.assertEqual(self.call(last), {'offset': 4, 'text': '二加七'})
        self.assertEqual(self.call(last)['text'], '二加七')
        self.assertEqual(self.providers[0].received, [b'\x01\x02', b'\x03\x04'])
        self.reserve.assert_called_once()
        self.assertTrue(self.providers[0].closed)

    def test_pause_releases_provider_and_resume_keeps_one_answer(self):
        self.call(self.packet('pause', 0, b'\x01\x02'))
        self.assertTrue(self.providers[0].closed)
        self.call(self.packet('audio', 2, b'\x03\x04'))
        self.providers[1].final = '减三'
        self.assertEqual(self.call(self.packet('finish', 4))['text'], '二加七减三')
        self.reserve.assert_called_once()

    def test_partial_only_cannot_commit(self):
        self.call(self.packet('audio', 0, b'\x01\x02'))
        self.providers[0].final = None
        with self.assertRaises(DomainError) as error:
            self.call(self.packet('finish', 2))
        self.assertEqual(error.exception.code, 'voice_incomplete')
        self.assertTrue(self.providers[0].closed)
        self.assertFalse(self.registry.active)

    def test_cancel_is_idempotent_and_releases_slot(self):
        cancel = Cancel(op='cancel', take=self.start.take)
        self.call(cancel)
        self.call(cancel)
        self.assertTrue(self.providers[0].closed)
        self.assertFalse(self.registry.active)
