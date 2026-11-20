import unittest

from graspmemoedu.mathacademy_interactions import source_variant
from graspmemoedu.question_types import demo_answer, deterministic_verdict, public_interaction


class PlainAssets:
    def render(self, text, _html, _gaps):
        return text


class MathAcademyInteractionTests(unittest.TestCase):
    def test_verified_blanks_keep_order_and_hide_answers(self):
        source = {'id': 42, 'format': 'FR', 'text': 'Calculate both values.', 'freeResponse': {'segments': [
            {'text': 'First: '}, {'textbox': {'type': 'number', 'answer': '3'}},
            {'newline': True}, {'text': 'Second: '}, {'textbox': {'type': 'number', 'answer': '-0.21'}},
        ]}}
        original = {'id': 'ma-question-42', 'source_format': 'FR', 'question': 'Calculate both values.\n\nFirst: [?]'}
        variant = source_variant(original, source, PlainAssets())
        spec = variant['interaction']
        self.assertEqual(spec['sections'][0]['control_ids'], [row['id'] for row in spec['controls']])
        self.assertIn('First: {{control:', spec['sections'][0]['html'])
        self.assertTrue(deterministic_verdict(variant, demo_answer(variant))[0])
        self.assertTrue(deterministic_verdict(variant, demo_answer(variant).replace('"3"', '"3.000"'))[0])
        self.assertFalse(deterministic_verdict(variant, demo_answer(variant).replace('"3"', '"30"'))[0])
        self.assertFalse(any('answers' in row for row in public_interaction(variant)['controls']))
        self.assertEqual(variant['question'], source['text'])

    def test_dropdown_requires_a_bound_index_and_stem(self):
        source = {'id': 64, 'format': 'SS', 'text': 'Choose a direction.', 'body': {'segments': [
            {'select': {'options': ['north', 'south']}},
        ]}}
        original = {'id': 'ma-question-64', 'source_format': 'SS', 'question': source['text']}
        with self.assertRaisesRegex(ValueError, 'verified answer'):
            source_variant(original, source, PlainAssets())
        variant = source_variant(original, source, PlainAssets(), [1])
        self.assertEqual(variant['interaction']['controls'][0]['answers'], ['o1'])
        with self.assertRaisesRegex(ValueError, 'same source stem'):
            source_variant({**original, 'question': 'Choose a speed.'}, source, PlainAssets(), [1])

    def test_source_multiple_choice_uses_the_verified_option(self):
        source = {'id': 71, 'format': 'MC', 'text': 'Pick a private method.', 'choice1': 'one', 'choice2': 'two'}
        original = {'id': 'ma-question-71', 'source_format': 'MC', 'question': source['text']}
        variant = source_variant(original, source, PlainAssets(), [1])
        self.assertTrue(deterministic_verdict(variant, '{"selected":"o2"}')[0])
        self.assertFalse(deterministic_verdict(variant, '{"selected":"o1"}')[0])
        self.assertNotIn('correct_id', public_interaction(variant))
