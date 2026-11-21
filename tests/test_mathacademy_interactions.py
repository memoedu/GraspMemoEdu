import unittest

from graspmemoedu.mathacademy_interactions import source_variant
from graspmemoedu.mathacademy_import import controls
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

    def test_complete_section_bodies_work_without_a_top_level_body(self):
        source = {'id': 90, 'format': 'PR', 'text': 'Work through both stages.', 'sections': [
            {'body': {'segments': [{'text': 'First: '}, {'textbox': {'type': 'number', 'answer': '3'}}]}},
            {'segments': [{'text': 'Then: '}, {'select': {'options': ['up', 'down'], 'sectionIndex': 1}}]},
        ]}
        original = {'id': 'ma-question-90', 'source_format': 'PR', 'question': source['text']}
        variant = source_variant(original, source, PlainAssets(), [1])
        spec = variant['interaction']
        self.assertEqual([c['type'] for c in spec['controls']], ['text', 'select'])
        self.assertEqual([s['control_ids'] for s in spec['sections']], [['c90s0p1'], ['c90s1p1']])
        self.assertTrue(deterministic_verdict(variant, demo_answer(variant))[0])

    def test_sparse_dividers_preserve_original_section_indices(self):
        source = {'id': 91, 'format': 'DS', 'text': 'Check each stage.', 'sections': [{} for _ in range(5)],
                  'body': {'segments': [
                      {'text': 'First: '}, {'select': {'options': ['yes', 'no'], 'sectionIndex': 0}},
                      {'sectionDivider': True},
                      {'text': 'Fourth: '}, {'select': {'options': ['no', 'yes'], 'sectionIndex': 3}},
                  ]}, 'selects': [{'sectionIndex': 4, 'options': ['yes', 'no']}]}
        gaps = []
        spec = controls(source, PlainAssets(), gaps)
        self.assertEqual([s['complete'] for s in spec['sections']], [True, False, False, True, False])
        self.assertEqual([g['section'] for g in gaps], [1, 2, 4])
        self.assertEqual([s['control_ids'] for s in spec['sections']],
                         [['c91s0p1'], [], [], ['c91s3p1'], ['c91s4p0']])
        original = {'id': 'ma-question-91', 'source_format': 'DS', 'question': source['text']}
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            source_variant(original, source, PlainAssets(), [0, 1, 0])

    def test_dropdown_format_can_include_multiple_source_sections(self):
        source = {'id': 93, 'format': 'SS', 'body': {'segments': [
            {'text': 'Start: '}, {'select': {'options': ['a', 'b']}},
            {'sectionDivider': True},
            {'text': 'Continue: '}, {'select': {'options': ['c', 'd']}},
        ]}}
        spec = controls(source, PlainAssets(), [])
        self.assertEqual([s['control_ids'] for s in spec['sections']], [['c93s0p1'], ['c93s1p1']])
        self.assertEqual([c['type'] for c in spec['controls']], ['select', 'select'])
