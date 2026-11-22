from contextlib import ExitStack
import json
from pathlib import Path
import unittest
from zipfile import ZipFile

from graspmemoedu.catalog import Catalog
from graspmemoedu.config import Settings
from graspmemoedu.ma_question_plan import validate_plan
from graspmemoedu.mathacademy_import import SourceIndex, install, prepare, scoped_question_inventory
from graspmemoedu.service import create_learning_service
from tests.fixtures import temporary_test_directory
from tests.test_mathacademy_import import source


class MAQuestionPlanTests(unittest.TestCase):
    def test_new_import_hides_calculation_options_and_keeps_judgment(self):
        with temporary_test_directory() as temporary, ExitStack() as resources:
            root = Path(temporary)
            lesson = source(1)['lesson']
            original = lesson['steps'].pop()['question']
            questions = [
                {**original, 'id': 501, 'format': 'MC', 'text': 'Find x and y. Hint: try 3.',
                 'choice1': '3 and 7', 'choice2': '9 and 2'},
                {**original, 'id': 502, 'format': 'MC', 'text': 'Which claim follows?',
                 'choice1': 'The model is unbiased.', 'choice2': 'The model is consistent.'},
                {**original, 'id': 503, 'format': 'DS', 'text': 'Evaluate x and assess the claim.',
                 'body': {'segments': [
                     {'text': 'Hint: use the previous result. The value is '}, {'select': {'options': ['42', '51']}},
                     {'sectionDivider': True}, {'select': {'options': ['supported', 'unsupported']}},
                 ]}},
                original,
            ]
            lesson['steps'].extend({'type': 'question', 'number': i, 'question': q}
                                   for i, q in enumerate(questions, 3))
            with ZipFile(root / 'topics.zip', 'w') as archive:
                archive.writestr('topic-json/topic-1.json', json.dumps({'lesson': lesson}))
            node = {'id': 1, 'name': 'Synthetic 1', 'course': {'id': 10, 'name': 'Practice'},
                    'unit': {'id': 1, 'number': 1, 'name': 'Unit'},
                    'module': {'id': 1, 'number': 1, 'name': 'Module'}, 'prerequisites': []}
            with ZipFile(root / 'graphs.zip', 'w') as archive:
                archive.writestr('course-knowledge-graph/course-10.json', json.dumps({'topics': {'1': node}}))
            index = SourceIndex(root / 'topics.zip', root / 'graphs.zip')
            resources.callback(index.archive.close)
            scope = index.scope([10])
            inventory = scoped_question_inventory(index, scope)
            self.assertEqual(set(inventory), {'1/501', '1/502', '1/503'})
            plan = {key: {'source_sha256': item['source_sha256'], 'mode': 'keep',
                          'reason': 'Assess the candidate statements.'} for key, item in inventory.items()}
            with self.assertRaisesRegex(ValueError, 'cover the inventory'):
                prepare(index, scope, root / 'cache', root / 'missing-plan')
            legacy = root / 'as-source'
            prepare(index, scope, root / 'cache', legacy, question_plan=plan)
            install(legacy, root / 'existing')
            previous = (root / 'existing/active-content.json').read_bytes()
            plan['1/501'].update(mode='fill', labels=['x =', 'y ='], edits=[[' Hint: try 3.', '']],
                                 reason='Both values can be computed from the task.')
            plan['1/503'].update(mode='fill', dropdowns=['s0-p1'],
                                 section_edits={'s0-p0': [['Hint: use the previous result. ', '']]},
                                 reason='Only the first control asks for a computed value.')
            with self.assertRaisesRegex(ValueError, 'source binding changed'):
                validate_plan(inventory, {**plan, '1/501': {**plan['1/501'], 'source_sha256': 'changed'}})
            package = root / 'fill-in'
            prepare(index, scope, root / 'cache', package, question_plan=plan)
            self.assertEqual(install(package, root / 'existing')['status'], 'unchanged')
            self.assertEqual((root / 'existing/active-content.json').read_bytes(), previous)

            install(package, root / 'new')
            settings = Settings.load(root / 'new')
            topic = Catalog.load(settings).topic('ma-topic-1')
            reader = create_learning_service(topic, root / 'new')
            rows = {row['id']: row for row in reader.state()['blocks']}
            fill = rows['ma-question-501']['interaction']
            self.assertEqual([item['type'] for item in fill['controls']], ['text', 'text'])
            self.assertEqual(fill['grading'], 'unavailable')
            self.assertNotIn('try 3', json.dumps(rows))
            self.assertNotIn('9 and 2', json.dumps(rows))
            self.assertEqual(rows['ma-question-502']['interaction']['type'], 'choice')
            self.assertEqual(len(rows['ma-question-502']['interaction']['options']), 2)
            mixed = rows['ma-question-503']['interaction']
            self.assertEqual([r['type'] for r in mixed['controls']], ['text', 'select'])
            self.assertEqual(len(mixed['sections']), 2)
            self.assertNotIn('"51"', json.dumps(mixed))
            self.assertNotIn('Hint:', json.dumps(mixed))
            self.assertNotIn('PRIVATE-CANDIDATE', json.dumps(rows))
            frozen = json.loads((package / 'mathacademy-sources/topics/ma-topic-1.json').read_bytes())
            self.assertEqual(frozen['lesson'], lesson)
