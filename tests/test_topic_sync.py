from contextlib import closing
import secrets
import unittest
from unittest.mock import patch
from uuid import uuid4

from graspmemoedu.service import DomainError
from graspmemoedu.topic_sync_storage import SealedSnapshots
from tests import test_admin_students as fixtures


class MemoryFiles:
    def __init__(self):
        self.files = {}

    def write_new(self, path, data):
        if path in self.files:
            return False
        self.files[path] = data
        return True

    def read(self, path):
        return self.files.get(path)


class TopicSyncTests(unittest.TestCase):
    identity = fixtures.AdminStudentsTests.identity

    def setUp(self):
        self.files = MemoryFiles()
        with patch('graspmemoedu.api.configured_snapshots', return_value=SealedSnapshots(self.files, bytes(32))):
            fixtures.AdminStudentsTests.setUp(self)
        self.topic = self.course['id']
        self.device = str(uuid4())
        self.secret = secrets.token_urlsafe(32)
        self.authorization = {'Authorization': 'TopicSync ' + self.device + '.' + self.secret}

    def get(self, path, headers, **params):
        return self.client.get('/api/topic-sync/' + path, headers=headers, params=params)

    def post(self, path, headers, payload=None, **params):
        return self.client.post('/api/topic-sync/' + path, headers=headers, params=params, json=payload or {})

    def ticket(self, headers):
        response = self.post('pair-ticket', headers)
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()['ticket']

    def pair(self, headers, *, kb='kb'):
        return self.post('pair-device', {}, {'ticket': self.ticket(headers), 'device_id': self.device,
                                          'device_secret': self.secret, 'kb_id': kb})

    def bind(self, rem='document'):
        return self.post('device-binding', self.authorization, {'topic_id': self.topic, 'kb_id': 'kb',
                                                                'rem_id': rem})

    def test_original_binding_cannot_be_taken_over_by_another_login(self):
        first = self.pair(self.headers)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.bind().status_code, 200)
        self.assertEqual(self.bind().status_code, 200)
        self.assertEqual(self.bind('another-document').status_code, 409)
        response = self.get('binding', self.normal_headers, topic_id=self.topic, device_id=self.device)
        self.assertEqual(response.json()['detail']['code'], 'topic_sync_account_mismatch')
        self.assertEqual(self.pair(self.normal_headers).json()['detail']['code'], 'topic_sync_account_mismatch')
        self.assertEqual(self.pair(self.headers, kb='wrong').json()['detail']['code'], 'topic_sync_knowledge_base_mismatch')
        result = self.get('binding', self.headers, topic_id=self.topic, device_id=self.device)
        self.assertEqual(result.json()['rem_id'], 'document')
        self.assertEqual(self.get('device-resolve', self.authorization, kb_id='kb', rem_id='document').json()['topic_id'], self.topic)
        self.assertEqual(self.get('device-resolve', {**self.authorization, 'Origin': 'https://site.test'},
                                  kb_id='kb', rem_id='document').status_code, 403)

    def test_revoked_account_and_device_cannot_access_companion_or_web_data(self):
        self.assertEqual(self.pair(self.headers).status_code, 200)
        self.app.state.topic_sync.set_excluded(self.student, True)
        self.assertEqual(self.get('body', self.headers, topic_id=self.topic).json()['detail']['code'], 'topic_sync_disabled')
        self.assertEqual(self.get('device-body', self.authorization, topic_id=self.topic).json()['detail']['code'],
                         'topic_sync_disabled')
        self.app.state.topic_sync.set_excluded(self.student, False)
        self.store.revoke_sessions(self.student)
        self.assertEqual(self.get('device-body', self.authorization, topic_id=self.topic).status_code, 401)
        bad = {'Authorization': 'TopicSync ' + self.device + '.' + secrets.token_urlsafe(32)}
        self.assertEqual(self.get('device-body', bad, topic_id=self.topic).status_code, 403)

    def test_both_transport_paths_share_private_immutable_versions(self):
        self.assertEqual(self.pair(self.headers).status_code, 200)
        self.assertEqual(self.bind().status_code, 200)
        first, second = str(uuid4()), str(uuid4())
        body = {'format': 'topic-outline-v1', 'title': 'Private example', 'blocks': [
            {'id': 'parent', 'text': 'Synthetic private text'},
            {'id': 'child', 'parent_id': 'parent', 'kind': 'formula', 'text': r'\frac{a}{b}'},
        ]}
        change = {'topic_id': self.topic, 'expected_revision': None, 'revision': first, 'document': body}
        response = self.post('body', self.headers, change, device_id=self.device)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.get('device-body', self.authorization, topic_id=self.topic).json()['revision'], first)
        self.assertEqual(self.get('body', self.normal_headers, topic_id=self.topic).json()['document'], None)
        self.assertEqual(self.post('body', self.headers, change).json(), response.json())
        self.assertEqual(self.post('device-body', self.authorization, {**change, 'revision': second}).status_code, 409)
        changed = {**body, 'title': 'Edited on companion'}
        other_change = {**change, 'revision': second, 'expected_revision': first, 'document': changed}
        self.assertEqual(self.post('device-body', self.authorization, other_change).status_code, 200)
        web = self.get('body', self.headers, topic_id=self.topic).json()
        self.assertEqual(web['revision'], second)
        self.assertEqual(web['document']['title'], 'Edited on companion')
        self.assertEqual(len(self.files.files), 2)
        for path, ciphertext in self.files.files.items():
            self.assertTrue(ciphertext.startswith(b'GME1'))
            self.assertNotIn(b'Synthetic private text', ciphertext)
            self.assertNotIn(self.topic, path)
        with closing(self.store._connect()) as con:
            raw = con.execute('SELECT snapshot FROM topic_sync_revisions').fetchall()
        self.assertEqual(len(raw), 2)
        self.assertTrue(all(len(row['snapshot']) == 64 for row in raw))

    def test_bad_tree_and_tampered_snapshot_report_errors(self):
        invalid = {'topic_id': self.topic, 'expected_revision': None, 'revision': str(uuid4()),
                   'document': {'title': 'Invalid', 'blocks': [{'id': 'loop', 'parent_id': 'loop', 'text': ''}]}}
        self.assertEqual(self.post('body', self.headers, invalid).status_code, 422)
        snapshots = self.app.state.topic_sync.snapshots
        scope = ('personal', self.student, self.topic)
        version = snapshots.save(scope, {'synthetic': 'content'})
        path, content = next(iter(self.files.files.items()))
        self.files.files[path] = content[:-1] + bytes([content[-1] ^ 1])
        with self.assertRaises(DomainError):
            snapshots.load(scope, version)
