import base64
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore, Event
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from graspmemoedu.service import DomainError
from graspmemoedu.voice_input import format_voice, live_text, refine_voice
from graspmemoedu.voice_math import VoiceContext, quick_math
from graspmemoedu.voice_stream import MAX_AUDIO, Cancel, Chunk, Open, Outbox, Sessions


class MathDictationTests(unittest.TestCase):
    def test_textbox_scope_reaches_asr_and_refinement_without_consuming_the_whole_prompt(self):
        box = {'before': 'p' * 3000 + '左侧温度', 'selected': '选中词', 'after': '右侧压强' + 'q' * 3000}
        c = VoiceContext(stem='题干开头' + '某' * 3000 + '题干末尾', textbox=box)
        parts = [v['content'][0]['text'] for v in c.asr_input('本次前句')['context']]
        self.assertTrue(len(parts) <= 5 and all(0 < len(t) <= 400 for t in parts))
        for expected in ('题干开头', '题干末尾', '左侧温度', '选中词', '右侧压强', '本次前句'):
            self.assertIn(expected, ''.join(parts))
        for profile in ('general', 'calculator', 'answer'):
            model = Mock(side_effect=['non_writing', '样本'] if profile == 'general' else ['x'])
            refine_voice('本次口述', profile, model, context=c)
            instructions, source = model.call_args.args
            self.assertIn('只输出本次', instructions)
            self.assertEqual(source['transcript'], '本次口述')
            self.assertEqual(source['notation']['textbox'], box)
            self.assertEqual(source['notation']['stem'], c.stem)

    def test_only_the_spoken_insertion_uses_notation_from_either_side_and_the_selection(self):
        for area, letter in [('before', 'r'), ('after', 's'), ('selected', 't')]:
            c = VoiceContext(stem='半径用 a 表示。', symbols=['a'], textbox={area: f'半径用 {letter} 表示。'})
            self.assertEqual(format_voice('半径等于五', 'answer', c, live=True), letter + '=5')
        self.assertEqual(quick_math('b加七', 'calculator', VoiceContext(textbox={'before': '2*B+'})), 'B+7')
        self.assertEqual(quick_math('a六', 'answer', VoiceContext(textbox={'after': 'a_{6}'})), 'a_{6}')
        self.assertIsNone(quick_math('a六', 'answer', VoiceContext(textbox={'before': 'a^{new}，a_{new}'})))

    def test_direct_repairs_preserve_surrounding_speech_and_quotations(self):
        context = VoiceContext()
        self.assertEqual(format_voice('先记下来。会议定在周三，不对，是周五。', 'general', context, live=True),
                         '先记下来。会议定在周五。')
        self.assertEqual(format_voice('他说“不对，是周五”。', 'general', context, live=True), '他说“不对，是周五”。')
        self.assertEqual(format_voice('八乘四。加七，不对，是五', 'calculator', context, live=True), '8*4+5')
        self.assertEqual(format_voice('函数不对称。', 'general', context, live=True), '函数不对称。')
        self.assertEqual(format_voice('总数是六，不对，是九。', 'general', context, live=True), '总数是九。')
        self.assertEqual(live_text('12+8。不对，应该是', 'calculator', context, partial=True)[0], '12+8')
        self.assertEqual(format_voice('保留这句话。', 'answer_commands', context, live=True), '保留这句话。')

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
        continued = context.asr_input('仅本次录音的前文')['context']
        self.assertEqual(len(continued), 5)
        self.assertTrue(continued[-1]['content'][0]['text'].endswith('使用末尾条件。\n仅本次录音的前文'))

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

    def test_explicit_vector_direction_limits_and_derivative_are_preserved(self):
        context = VoiceContext(style='math', symbols=['Q', 't'])
        for spoken, latex in (
            ('横向量，负三、Q、七', r'\begin{pmatrix}-3&Q&7\end{pmatrix}'),
            ('竖着的向量 是 七，零，负二', r'\begin{pmatrix}7\\0\\-2\end{pmatrix}'),
            ('积分从负二到七，t平方减四，微分t', r'\int_{-2}^{7} t^2-4\,dt'),
            ('积分t平方减四乘t，dt，从负二到七', r'\int_{-2}^{7} t^2-4\cdot t\,dt'),
            ('偏Q比偏t等于t加九', r'\frac{\partial Q}{\partial t}=t+9'),
            ('偏Q比偏t', r'\frac{\partial Q}{\partial t}'),
        ):
            with self.subTest(spoken=spoken):
                self.assertEqual(quick_math(spoken, 'answer', context), latex)


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
        self.history = []
        self.contexts = []
        def factory(context, update, *, live=False, previous=''):
            provider = Provider(context, update)
            self.providers.append(provider)
            self.history.append(previous)
            self.contexts.append(context)
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

    def packet(self, op, offset=0, pcm=b'', part=None):
        return Chunk(op=op, take=self.start.take, offset=offset, pcm=base64.b64encode(pcm).decode(), part=part)

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

    def test_opted_in_snapshots_replace_retract_and_cross_pause(self):
        self.call(Cancel(op='cancel', take=self.start.take))
        packet = self.start.model_copy(update={'live': True, 'profile': 'general'})
        self.registry.formatter = format_voice
        self.call(packet)
        first = self.packet('audio', pcm=b'ab')
        self.assertEqual(self.call(first), {'offset': 2, 'preview': '二加一'})
        self.assertEqual(self.call(first)['preview'], '二加一')
        provider = self.providers[-1]
        provider.write = lambda pcm: None
        provider.update({'sentence_id': 0, 'text': '', 'sentence_end': False})
        self.assertEqual(self.call(self.packet('audio', 2, b'cd'))['preview'], '')
        provider.update({'sentence_id': 0, 'text': '一起散步', 'sentence_end': False})
        self.assertEqual(self.call(self.packet('audio', 4, b'ef'))['preview'], '一起散步')
        provider.final = '一起散步。'
        self.assertEqual(self.call(self.packet('pause', 6))['preview'], '一起散步。')
        self.assertEqual(self.call(self.packet('audio', 6, b'gh'))['preview'], '一起散步。二加一')
        self.providers[-1].final = '明天。'
        self.assertEqual(self.call(self.packet('finish', 8))['text'], '一起散步。明天。')

    def test_structured_commands_never_expose_or_apply_an_interim(self):
        self.call(Cancel(op='cancel', take=self.start.take))
        self.call(self.start.model_copy(update={'live': True, 'profile': 'answer_commands'}))
        self.assertEqual(self.call(self.packet('audio', pcm=b'ab')), {'offset': 2})
        self.assertEqual(self.call(self.packet('finish', 2))['text'], '二加七')

    def test_manual_cuts_hide_revisions_and_keep_context_without_replaying_prior_audio(self):
        self.call(Cancel(op='cancel', take=self.start.take))
        self.registry.formatter = format_voice
        self.call(self.start.model_copy(update={'manual': True, 'live': True}))
        audio = self.packet('audio', pcm=b'ab')
        self.assertEqual(self.call(audio), {'offset': 2})
        self.assertEqual(self.providers[-1].received, [b'ab'])
        paused = self.call(self.packet('pause', 2))
        self.assertEqual(paused, {'offset': 2})
        cut = self.packet('cut', 2, part=0)
        self.assertEqual(self.call(cut), {'offset': 2, 'text': '2+7'})
        self.assertEqual(self.call(cut), {'offset': 2, 'text': '2+7'})
        self.assertEqual(self.call(self.packet('cut', 2, part=1)), {'offset': 2, 'text': ''})
        with self.assertRaises(DomainError):
            self.call(self.packet('cut', 2, part=4))
        self.assertEqual(self.call(self.packet('audio', 2, b'cd')), {'offset': 4})
        self.assertEqual(self.providers[-1].received, [b'cd'])
        self.assertIn('2+7', self.contexts[-1].textbox.before)
        self.providers[-1].final = '四加六'
        finish = self.packet('finish', 4, part=2)
        self.assertEqual(self.call(finish), {'offset': 4, 'text': '4+6'})
        self.assertEqual(self.call(finish), {'offset': 4, 'text': '4+6'})

    def test_natural_pause_drains_the_provider_and_keeps_the_recording_and_context(self):
        self.call(Cancel(op='cancel', take=self.start.take))
        self.registry.formatter = format_voice
        self.call(self.start.model_copy(update={'live': True, 'profile': 'general'}))
        voice, silence = b'ab' * (160 * 9), bytes(320 * 51)
        with patch('graspmemoedu.voice_stream.Vad.is_speech', lambda vad, data, rate: any(data)):
            # Frame analysis must work even when the network splits a VAD frame.
            self.call(self.packet('audio', 0, voice[:234]))
            self.call(self.packet('audio', 234, voice[234:]))
            self.providers[-1].final = '周三。'
            result = self.call(self.packet('audio', len(voice), silence))
            self.assertEqual(result['preview'], '周三。')
            self.assertTrue(self.providers[-1].closed)
            offset = len(voice) + len(silence)
            sessions = len(self.providers)
            self.call(self.packet('audio', offset, bytes(9600)))
            self.assertEqual(len(self.providers), sessions)
            offset += 9600
            self.call(self.packet('audio', offset, voice))
            self.assertEqual(self.history[-1], '周三。')
            self.providers[-1].final = '不对，是周五。'
            self.assertEqual(self.call(self.packet('finish', offset + len(voice)))['text'], '周五。')
            self.assertEqual(b''.join(self.providers[-2].received + self.providers[-1].received),
                             voice + silence + bytes(8000) + voice)

    def test_independent_cuts_reset_offsets_limits_and_only_use_new_audio(self):
        self.call(Cancel(op='cancel', take=self.start.take))
        self.reserve.reset_mock()
        context = VoiceContext(stem=self.start.context.stem,
                               textbox={'before': '前文', 'selected': '旧文', 'after': '后文'})
        self.registry.formatter = format_voice
        self.call(self.start.model_copy(update={'manual': True, 'independent': True, 'context': context}))
        with patch('graspmemoedu.voice_stream.SpeechBoundary.reached', return_value=False):
            for offset in range(0, MAX_AUDIO, 64000):
                self.assertEqual(self.call(self.packet('audio', offset, bytes(64000), part=0)),
                                 {'offset': offset + 64000})
        first = self.packet('cut', MAX_AUDIO, part=0)
        self.assertEqual(self.call(first), {'offset': MAX_AUDIO, 'text': '2+7'})
        self.assertEqual(self.call(first), {'offset': MAX_AUDIO, 'text': '2+7'})
        self.assertEqual(self.call(self.packet('cut', part=1)), {'offset': 0, 'text': ''})
        with self.assertRaises(DomainError):
            self.call(self.packet('audio', pcm=b'cd', part=1))
        self.assertEqual(self.call(self.packet('audio', pcm=b'cd', part=2)), {'offset': 2})
        self.assertEqual(self.providers[-1].received, [b'cd'])
        textbox = self.contexts[-1].textbox
        self.assertEqual(textbox.before, '前文 2+7')
        self.assertEqual(textbox.selected, '')
        self.assertEqual(textbox.after, '后文')
        self.providers[-1].final = '四加六'
        self.assertEqual(self.call(self.packet('finish', 2, part=2)), {'offset': 2, 'text': '4+6'})
        self.assertEqual(self.reserve.call_count, 2)

    def test_cancel_is_idempotent_and_releases_slot(self):
        cancel = Cancel(op='cancel', take=self.start.take)
        self.call(cancel)
        self.call(cancel)
        self.assertTrue(self.providers[0].closed)
        self.assertFalse(self.registry.active)
