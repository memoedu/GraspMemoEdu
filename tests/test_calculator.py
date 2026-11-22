from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from graspmemoedu.calculator import from_mathacademy, normalize, policy
from graspmemoedu.author_import import prepare_topic
from graspmemoedu.mathacademy_import import question_model
from graspmemoedu.service import LearningService
from graspmemoedu.source_content import reading_blocks
from graspmemoedu.topic_format import normalize_document
from tests.fixtures import synthetic_course
from tests.topic_format_fixtures import lesson_document


class CalculatorSchemaTests(unittest.TestCase):
    def test_topic_inheritance_and_explicit_question_level(self):
        topic = {'calculate': {'level': 'cas', 'disable_modules': ['probability'],
                               'disable_keys': ['sin'], 'enable_modules': ['modular']}}
        item = {'calculate': {'level': 'scientific', 'disable_keys': ['cos'], 'enable_modules': ['graph']}}
        self.assertEqual(policy(topic, item), {'level': 'scientific', 'disable_modules': ['probability'],
                                               'disable_keys': ['cos', 'sin'], 'enable_modules': ['graph']})
        self.assertEqual(policy(topic, {'calculate': {'disable_keys': ['add']}})['level'], 'cas')
        self.assertIsNone(policy(topic, {'calculate': 'none'}))
        self.assertIsNone(policy(topic, {'calculate': None}))
        self.assertIsNone(policy({}, {}))

    def test_invalid_configuration_cannot_silently_enable(self):
        for value in (True, 3, 'Scientific', {'level': 'no-limit'}, {},
                      {'enable_modules': ['symbolic']}, {'disable_modules': ['typo']},
                      {'disable_keys': 'sin'}, {'disable_keys': ['sin', 'sin']}, {'foo': []}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                normalize(value)

    def test_new_and_legacy_mathacademy_metadata(self):
        self.assertEqual(from_mathacademy('Graphing'), {'level': 'scientific', 'enable_modules': ['graph']})
        self.assertEqual(from_mathacademy('Standard'), {'level': 'basic'})
        self.assertEqual(from_mathacademy('unknown'), {'level': 'none'})

        class Assets:
            def render(self, source, html, gaps):
                return html or source

        q = question_model({'id': 1, 'question': 'Test', 'calculator': 'Graphing'}, Assets(), [], example=True)
        self.assertEqual(q['html'], 'Test')
        self.assertEqual(q['calculate'], from_mathacademy('Graphing'))
        step = question_model({'id': 2, 'question': 'Test', 'calculate': 'basic', 'calculator': 'Graphing'},
                              Assets(), [], example=True, step={'calculate': 'cas'})
        self.assertEqual(step['calculate'], {'level': 'basic'})
        generated = '<aside class="inline-document-callout callout" data-callout="requirement"><strong>要求</strong><p>Calculator: Graphing</p></aside>'
        authored = '<aside class="inline-document-callout callout" data-callout="requirement"><strong>要求</strong><p>Explain your choice.</p></aside>'
        q.update(html=q['html'] + generated + authored)
        del q['calculate']
        blocks = reading_blocks({
            'source_adapter': 'mathacademy', 'introductions': [], 'unassigned_questions': [q],
            'modules': [], 'content_order': [],
        })
        self.assertEqual(blocks[0]['html'], 'Test' + authored)
        self.assertEqual(blocks[0]['calculate'], from_mathacademy('Graphing'))
        self.assertIsNone(policy({}, {'constraints': 'Graphing'}))

    def test_topic_author_format_keeps_metadata_only_on_questions(self):
        original = {'topic_format_version': 2, 'title': 'Calculator', 'id': 'calculator-fixture',
                    'topic_kind': 'lesson', 'calculate': 'scientific', 'nodes': [
                        {'id': 'intro', 'text': 'Introduction', 'children': [{'id': 'intro-body', 'text': 'Compute.'}]},
                        {'id': 'example-1', 'text': 'Example 1', 'calculate': 'basic',
                         'children': [{'id': 'stem', 'text': '2+2'},
                                      {'id': 'solution', 'text': 'Explanation',
                                       'children': [{'id': 'answer', 'text': '4'}]}]}]}
        normalized, _ = normalize_document(original)
        self.assertEqual(normalized['calculate'], 'scientific')
        self.assertEqual(normalized['nodes'][1]['calculate'], 'basic')
        wrong = deepcopy(original)
        wrong['nodes'][0]['calculate'] = 'cas'
        with self.assertRaisesRegex(ValueError, 'calculate belongs'):
            normalize_document(wrong)

    def test_lesson_projects_the_effective_policy(self):
        topic = synthetic_course(1)
        topic['calculate'] = {'level': 'cas', 'disable_modules': ['symbolic']}
        topic['modules'][0]['example']['calculate'] = 'basic'
        with tempfile.TemporaryDirectory() as folder:
            service = LearningService(topic, Path(folder))
            state = service.state()
        example = next(step for step in state['steps'] if step['kind'] == 'example')
        self.assertEqual(example['calculate'], {'level': 'basic', 'disable_modules': ['symbolic']})

    def test_mechanical_author_import_preserves_topic_and_question_metadata(self):
        document = lesson_document()
        document['calculate'] = {'level': 'scientific', 'disable_keys': ['sin']}
        example = document['nodes'][1]
        example['calculate'] = 'basic'
        example['children'][2]['calculate'] = None
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            source = root / 'source.json'
            source.write_text(json.dumps(document), encoding='utf-8')
            prepare_topic(source, document['id'], root / 'prepared')
            topic = json.loads((root / 'prepared' / 'topic.json').read_text(encoding='utf-8'))
        result = topic['modules'][0]
        self.assertEqual(topic['calculate'], document['calculate'])
        self.assertEqual(result['example']['calculate'], 'basic')
        self.assertIn('calculate', result['practices'][0])
        self.assertIsNone(result['practices'][0]['calculate'])
