import base64
from io import BytesIO
from unittest import TestCase
from unittest.mock import Mock

from PIL import Image

from graspmemoedu.judging import instant_question, judge_answer, local_verdict
from graspmemoedu.question_types import WHITEBOARD_ANSWER, display_answer, parse_submission_answer
from graspmemoedu.service import DomainError
from graspmemoedu.whiteboard_ocr import checked_png


def image_bytes(fmt, dimensions=(120, 80)):
    target = BytesIO()
    Image.new('RGB', dimensions, color='white').save(target, format=fmt)
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
