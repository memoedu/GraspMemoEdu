from contextlib import closing
from copy import deepcopy
import json
from pathlib import Path
import sqlite3
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from graspmemoedu.api import create_app
from graspmemoedu.atomic import AtomicLearningService
from graspmemoedu.config import Settings
from graspmemoedu.question_types import validate_interaction
from graspmemoedu.training_content import fingerprint
from tests.fixtures import temporary_test_directory
from atomic_fixtures import atomic_topic
from test_atomic_api import write_catalog
import test_training_api as helpers


class RubberDuckTests(unittest.TestCase):
    call = helpers.TrainingAPITests.call
    account = helpers.TrainingAPITests.account

    def setUp(self):
        temporary = temporary_test_directory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        write_catalog(self.root)
        self.bank = json.loads(Path(__file__).with_name('fixtures').joinpath('rubber-duck-bank.json').read_bytes())
        for group in self.bank['groups']:
            for question in group['questions']:
                question.update(html='<p>' + question['question'] + '</p>',
                                reference_answer=question['explanation'], explanation_html='<p>解析</p>', constraints='按大纲讲解')
        self.bank.update(schema=1)
        self.bank['version'] = fingerprint(self.bank)
        (self.root / 'training-banks').mkdir()
        (self.root / 'training-banks/rubber-duck-qa.json').write_text(json.dumps(self.bank), encoding='utf-8')
        (self.root / 'test-materials.json').write_text(json.dumps({'schema': 1, 'banks': [self.bank['id']]}), encoding='utf-8')
        service = AtomicLearningService(atomic_topic('english', 'atomic-english'), self.root)
        self.app = create_app(Settings(data_dir=self.root, public_api_origin='https://training.test',
                                      allowed_origins=('https://site.test',)), service)
        self.client = TestClient(self.app, base_url='https://training.test')
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.headers = {'Origin': 'https://site.test'}
        guest = self.call('POST', '/api/access/guest', {})
        self.headers['X-Learning-Identity'] = guest['identity_token']
        self.reader = '/api/training/group?bank_id=rubber-duck-qa&group_id=outline&reader=1'

    def state(self, ident):
        return self.call('GET', '/api/training/state?attempt_id=' + ident)

    def submit(self, payload):
        state = self.call('POST', '/api/training/submit', payload)
        until = time.monotonic() + 10
        while state['submission_status'] in ('pending', 'running') and time.monotonic() < until:
            time.sleep(.02)
            state = self.state(payload['attempt_id'])
        return state

    def test_progress_privacy_gating_retry_idempotency_and_completion(self):
        self.call('GET', self.reader, status=403)
        self.account(is_student=True, purpose='test')
        self.call('GET', self.reader, status=403)
        self.account(is_advanced_learner=True, is_student=True, purpose='test')
        preview = self.call('GET', self.reader)['reader_states']['statistics']
        self.assertTrue(preview['preview'])
        self.assertFalse(preview['can_self_rate'])
        outline = preview['outline']
        self.assertEqual((outline['covered'], outline['total']), (0, 7))
        self.assertEqual(outline['root']['text'], '描述一组数据')
        self.assertEqual([n['id'] for n in outline['root']['children']], ['mean', 'median', 'mode', 'range', 'outlier'])
        self.assertNotIn('mean-rule', json.dumps(preview))
        self.assertNotIn('把所有数据相加', json.dumps(preview, ensure_ascii=False))
        self.assertEqual(outline['root']['children'][0]['children'], [{'type': 'hidden'}])
        ident = preview['attempt_id']
        self.call('POST', '/api/training/open', {'request_id': ident, 'bank_id': 'rubber-duck-qa',
            'group_id': 'outline', 'question_id': 'statistics'})
        self.call('POST', '/api/training/reveal', {'attempt_id': ident}, status=403)

        def ask(transcript, *ids):
            payload = {'request_id': str(uuid4()), 'attempt_id': ident, 'answer': transcript}
            generate.return_value = json.dumps({'matches': dict.fromkeys(ids, transcript)})
            return self.submit(payload), payload

        with patch('graspmemoedu.voice_input.complete') as generate:
            wrong, _ = ask('极差是最大值和最小值相加。')
            self.assertEqual((wrong['phase'], wrong['outline']['covered']), ('answer', 0))
            later, _ = ask('二、四、六的平均数是四。', 'mean-example')
            self.assertEqual(later['outline']['covered'], 0)
            outer, first = ask('极端值比起中位数更容易改变平均数。', 'outlier-effect')
            self.assertEqual(outer['outline']['covered'], 1)
            self.assertNotIn('mean-example', json.dumps(outer))
            shallow, _ = ask('先排序，奇数项就取中间一个。', 'median-rule')
            self.assertEqual(shallow['outline']['covered'], 2)
            self.assertNotIn('median-even', json.dumps(shallow))
            parent, _ = ask('把各项加起来，再除以个数。', 'mean-rule')
            self.assertEqual(parent['outline']['covered'], 4)
            self.assertIn('mean-example', json.dumps(self.state(ident)))
            self.assertEqual(self.submit(first)['outline']['covered'], 4)

            generate.return_value = '{"matches":{"range-rule":"made up evidence"}}'
            payload = {'request_id': str(uuid4()), 'attempt_id': ident, 'answer': '最大值减最小值是极差。'}
            failure = self.submit(payload)
            self.assertEqual((failure['submission_status'], failure['outline']['covered']), ('error', 4))
            generate.return_value = json.dumps({'matches': {'range-rule': payload['answer']}})
            self.assertEqual(self.submit(payload)['outline']['covered'], 5)
            done, receipt = ask('偶数项时取中间两个的平均值；众数出现最频繁，可以并列。', 'median-even', 'mode-rule')
            self.assertEqual((done['phase'], done['outline']['covered']), ('done', 7))
            self.assertTrue(done['result']['correct'])
            calls = generate.call_count
            self.assertEqual(self.submit(receipt)['result'], done['result'])
            self.assertEqual(generate.call_count, calls)

        with closing(sqlite3.connect(self.root / 'learning.sqlite3')) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM training_ratings').fetchone()[0], 1)
        self.account(is_advanced_learner=True, is_student=True, purpose='test')
        self.call('GET', '/api/training/state?attempt_id=' + ident, status=404)

    def test_schema_rejects_cross_surface_usage_and_duplicate_nodes(self):
        spec = self.bank['groups'][0]['questions'][0]['interaction']
        validate_interaction(spec, allow_outline=True)
        with self.assertRaises(ValueError):
            validate_interaction(spec)
        repeated = deepcopy(spec)
        repeated['root']['children'].append(repeated['root']['children'][0])
        with self.assertRaises(ValueError):
            validate_interaction(repeated, allow_outline=True)
