from contextlib import closing
import secrets
import unittest
from unittest.mock import patch
from uuid import uuid4

from graspmemoedu.catalog import Catalog
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
        load = Catalog.load

        def shared_catalog(settings, fallback=None):
            original = load(settings, fallback)
            second_course = {**original.course('math'), 'id': 'another-math-course'}
            topics = dict(original.topics)
            topic_id = original.default_topic_id
            topics[topic_id] = {**topics[topic_id], 'source_adapter': 'hyperskill', 'hyperskill': {'topic_id': 321}}
            return Catalog([*original.courses.values(), second_course], topics,
                           original.default_topic_id, original.topic_paths)

        with (patch('graspmemoedu.api.configured_snapshots', return_value=SealedSnapshots(self.files, bytes(32))),
              patch.object(Catalog, 'load', side_effect=shared_catalog)):
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

    def write(self, title, headers, *, previous=None, baseline=None):
        revision = str(uuid4())
        response = self.post('body', headers, {'topic_id': self.topic, 'expected_revision': previous,
                             'expected_baseline_revision': baseline, 'revision': revision,
                             'document': {'title': title, 'blocks': []}})
        self.assertEqual(response.status_code, 200, response.text)
        return revision

    def group(self, headers, course, baseline=None, *, editable=True, **previous):
        payload = {'course_id': course, 'group_id': str(uuid4()), 'expected_revision': None,
                   'revision': str(uuid4()), 'name': 'Group fixture', 'editable': editable,
                   'baselines': {self.topic: baseline} if baseline else {}, **previous}
        return self.post('groups', headers, payload)

    def assign(self, course, group, headers=None, *, expected=None):
        return self.post('group-member', headers or self.admin_headers, {
            'learner_id': self.student, 'course_id': course, 'group_id': group, 'expected_group_id': expected})

    def test_different_course_baselines_cannot_split_one_shared_topic(self):
        first = self.write('First baseline', self.admin_headers)
        second = self.write('Second baseline', self.admin_headers, previous=first)
        math = self.group(self.admin_headers, 'math', first).json()
        crossing = self.group(self.admin_headers, 'another-math-course', second).json()
        self.assertEqual(self.assign('math', math['group_id']).status_code, 200)
        rejected = self.assign('another-math-course', crossing['group_id'])
        self.assertEqual(rejected.status_code, 409, rejected.text)
        self.assertEqual(rejected.json()['detail']['code'], 'topic_sync_baseline_conflict')
        self.assertIsNone(self.get('group-member', self.admin_headers, learner_id=self.student,
                                   course_id='another-math-course').json()['membership'])
        compatible = self.group(self.admin_headers, 'another-math-course', first, group_id=crossing['group_id'],
                                expected_revision=crossing['revision']).json()
        self.assertEqual(self.assign('another-math-course', compatible['group_id']).status_code, 200)
        rejected = self.group(self.admin_headers, 'math', second, group_id=math['group_id'],
                              expected_revision=math['revision'])
        self.assertEqual(rejected.status_code, 409)
        result = self.get('body', self.headers, topic_id=self.topic).json()
        self.assertEqual(result['baseline_revision'], first)
        self.assertEqual(result['document']['title'], 'First baseline')

    def test_reassigning_a_group_preserves_personal_body_and_enforces_editing(self):
        curated = self.write('Curated version', self.admin_headers)
        first = self.group(self.admin_headers, 'math', curated).json()
        self.assertEqual(self.assign('math', first['group_id']).status_code, 200)
        personal = self.write('My changes', self.headers, baseline=curated)
        other_course = self.group(self.admin_headers, 'another-math-course', curated, editable=False).json()
        self.assertEqual(self.assign('another-math-course', other_course['group_id']).status_code, 200)
        body = {'topic_id': self.topic, 'expected_revision': personal, 'revision': str(uuid4()),
                'document': {'title': 'Should be blocked', 'blocks': []}}
        result = self.post('body', self.headers, body)
        self.assertEqual(result.json()['detail']['code'], 'topic_sync_edit_disabled')
        self.assertEqual(self.assign('another-math-course', None, expected=other_course['group_id']).status_code, 200)
        official = self.group(self.admin_headers, 'math').json()
        self.assertEqual(self.assign('math', official['group_id'], expected=first['group_id']).status_code, 200)
        result = self.get('body', self.headers, topic_id=self.topic).json()
        self.assertEqual(result['revision'], personal)
        self.assertIsNone(result['baseline_revision'])
        self.assertEqual(result['document']['title'], 'My changes')

    def test_another_admin_must_explicitly_coordinate_a_group_change(self):
        self.app.state.help_requests.assign_admins(self.student, [self.admin, self.other])
        first = self.group(self.admin_headers, 'math').json()
        second = self.group(self.other_headers, 'math', editable=False).json()
        self.assertEqual(self.assign('math', first['group_id']).status_code, 200)
        rejected = self.assign('math', second['group_id'], self.other_headers)
        self.assertEqual(rejected.json()['detail']['code'], 'topic_sync_group_conflict')
        self.assertEqual(self.get('group-member', self.other_headers, learner_id=self.student,
                                  course_id='math').json()['membership']['group_id'], first['group_id'])
        self.assertEqual(self.assign('math', second['group_id'], self.other_headers, expected=first['group_id']).status_code, 200)
        self.assertEqual(self.get('groups', self.headers).status_code, 403)

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

    def test_same_knowledge_base_keeps_the_original_document_across_devices(self):
        self.assertEqual(self.pair(self.headers).status_code, 200)
        self.assertEqual(self.bind().status_code, 200)
        other_device = str(uuid4())
        self.device = other_device
        self.authorization = {'Authorization': 'TopicSync ' + self.device + '.' + self.secret}
        self.assertEqual(self.pair(self.headers).status_code, 200)
        self.assertEqual(self.get('binding', self.headers, topic_id=self.topic, device_id=other_device).json()['rem_id'],
                         'document')
        self.assertEqual(self.bind('duplicate').status_code, 409)

    def test_hyperskill_catalogue_only_returns_topics_available_to_the_paired_account(self):
        self.assertEqual(self.pair(self.headers).status_code, 200)
        expected = {'topics': {'321': self.topic}}
        self.assertEqual(self.get('device-hyperskill', self.authorization).json(), expected)
        self.store.set_permissions(self.student, topic_ids=[])
        self.assertEqual(self.get('device-hyperskill', self.authorization).json(), {'topics': {}})

    def test_open_ticket_is_issued_only_to_current_owner_and_consumed_once(self):
        self.assertEqual(self.pair(self.headers).status_code, 200)
        self.assertEqual(self.bind().status_code, 200)
        payload = {'device_id': self.device, 'topic_id': self.topic}
        self.assertEqual(self.post('open-ticket', self.normal_headers, payload).json()['detail']['code'],
                         'topic_sync_account_mismatch')
        ticket = self.post('open-ticket', self.headers, payload).json()['ticket']
        opened = self.post('device-open', self.authorization, {'ticket': ticket})
        self.assertEqual(opened.json(), {'topic_id': self.topic, 'kb_id': 'kb', 'rem_id': 'document'})
        self.assertEqual(self.post('device-open', self.authorization, {'ticket': ticket}).status_code, 403)
        ticket = self.post('open-ticket', self.headers, payload).json()['ticket']
        self.store.revoke_sessions(self.student)
        self.assertEqual(self.post('device-open', self.authorization, {'ticket': ticket}).status_code, 401)

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
