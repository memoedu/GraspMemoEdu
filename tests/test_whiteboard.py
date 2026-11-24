import base64
from io import BytesIO
import json
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw

from graspmemoedu.judging import instant_question, judge_answer, local_verdict
from graspmemoedu.question_types import WHITEBOARD_ANSWER, display_answer, parse_submission_answer
from graspmemoedu.service import DomainError
from graspmemoedu.whiteboard_ocr import WHITEBOARD_PATH, checked_png, recognize_selection, register_whiteboard_ocr


def image_bytes(fmt, dimensions=(120, 80), *, strokes=()):
    target = BytesIO()
    image = Image.new('RGB', dimensions, color='white')
    draw = ImageDraw.Draw(image)
    for stroke in strokes:
        draw.line(stroke, fill='#fefefe', width=2)
    image.save(target, format=fmt)
    return base64.b64encode(target.getvalue()).decode()


class WhiteboardTests(TestCase):
    def setUp(self):
        self.question = {
            'question': 'Fill the two blanks.',
            'constraints': 'Use equivalent expressions.',
            'reference_answer': 'The first value is 3. The second value is 5.',
            'interaction': {'type': 'fill_blank', 'grading': 'exact', 'blanks': [
                {'id': 'first', 'answers': ['3']}, {'id': 'second', 'answers': ['5']},
            ]},
        }

    def test_whiteboard_uses_existing_semantic_judge_and_paid_admission(self):
        text = 'b = 5 after reduction. The first blank is 1 + 2.'
        answer = WHITEBOARD_ANSWER + text
        self.assertEqual(parse_submission_answer(self.question, answer), text)
        self.assertEqual(display_answer(self.question, answer), text)
        self.assertFalse(instant_question(self.question, answer))
        require = Mock()
        self.assertIsNone(local_verdict(self.question, {}, {'request_id': 'whiteboard', 'answer': answer}, None, require))
        require.assert_called_once_with(None, 1)
        judge = Mock(return_value={'status': 'judged', 'correct': True, 'reason': 'Equivalent work'})
        self.assertEqual(judge_answer(judge, self.question, answer), (True, 'Equivalent work'))
        self.assertEqual(judge.call_args.args[2], text)
        self.assertIn('1. 3\n2. 5', judge.call_args.args[1])

    def test_normal_controls_keep_deterministic_grading(self):
        answer = '{"first":"3","second":"5"}'
        judge = Mock()
        self.assertTrue(instant_question(self.question, answer))
        self.assertTrue(judge_answer(judge, self.question, answer)[0])
        judge.assert_not_called()

    def test_empty_or_ungradable_work_is_rejected(self):
        with self.assertRaises(ValueError):
            parse_submission_answer(self.question, WHITEBOARD_ANSWER + ' ')
        self.question['interaction']['grading'] = 'unavailable'
        with self.assertRaises(ValueError):
            parse_submission_answer(self.question, WHITEBOARD_ANSWER + 'a = 3')

    def test_image_is_decoded_and_reencoded(self):
        self.assertTrue(checked_png(image_bytes('PNG')).startswith('data:image/png;base64,'))
        for invalid in ('@', image_bytes('JPEG'), image_bytes('PNG', (2600, 2000))):
            with self.assertRaises(DomainError):
                checked_png(invalid)

    def test_even_faint_ink_is_sent_unchanged(self):
        strokes = [((400, 310), (433, 330)), ((490, 350), (517, 380))]
        original = image_bytes('PNG', (1280, 1024), strokes=strokes)
        self.assertEqual(checked_png(original, skip_blank=True), checked_png(original))
        self.assertIsNone(checked_png(image_bytes('PNG'), skip_blank=True))

    def test_recognize_accepts_current_and_cached_chinese_ui_languages(self):
        app = FastAPI()
        app.state.public_limits = SimpleNamespace(consume=Mock(), submissions_per_minute=12, daily=None)
        access = Mock()
        access.resolve.return_value = {'features': ['submit_answer'], 'learner_id': 'fixture', 'role': 'guest'}
        register_whiteboard_ocr(app, access)
        image = image_bytes('PNG', strokes=[((30, 30), (70, 51))])
        with TestClient(app) as client, patch('graspmemoedu.whiteboard_ocr.recognize_whiteboard') as recognize:
            recognize.return_value = {'status': 'insufficient', 'feedback': 'Missing work'}
            for sent, expected in [('zh', 'zh'), ('zh-CN', 'zh'), ('en', 'en')]:
                with self.subTest(language=sent):
                    reply = client.post(WHITEBOARD_PATH, json={'image': image, 'language': sent})
                    self.assertEqual(reply.status_code, 200)
                    self.assertEqual(reply.json()['status'], 'insufficient')
                    self.assertEqual(recognize.call_args.args[0].language, expected)
            reply = client.post(WHITEBOARD_PATH, json={'image': image, 'language': 'unknown'})
            self.assertEqual(reply.status_code, 422)
            for language, feedback in [('zh-CN', '白板是空白的'), ('en', 'Write your answer')]:
                reply = client.post(WHITEBOARD_PATH, json={'image': image_bytes('PNG'), 'language': language})
                self.assertEqual(reply.status_code, 200)
                self.assertEqual(reply.json()['status'], 'insufficient')
                self.assertIn(feedback, reply.json()['feedback'])
            self.assertEqual(recognize.call_count, 3)

    def test_selected_formula_uses_annotation_capture_gateway(self):
        png = checked_png(image_bytes('PNG'))
        with patch.dict('os.environ', {'GRASPMEMOEDU_WHITEBOARD_FORMULA_TOKEN': 'fixture'}), \
                patch('graspmemoedu.whiteboard_ocr.urlopen', return_value=BytesIO(b'{"latex":"mod(17,5)"}')) as request:
            result = recognize_selection(SimpleNamespace(language='zh'), png)
        self.assertEqual(result, {'status': 'ready', 'answer': 'mod(17,5)'})
        sent = request.call_args.args[0]
        self.assertEqual(sent.full_url, 'http://127.0.0.1:18879/recognize')
        self.assertEqual(json.loads(sent.data), {'png': png, 'outputFormat': 'calculator'})
