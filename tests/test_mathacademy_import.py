"""Independent synthetic sources: shared identity, atomic install and safe reading."""
from copy import deepcopy
from contextlib import closing
import json
from pathlib import Path
import sqlite3
import unittest
import zipfile

from fastapi.testclient import TestClient
from graspmemoedu.mathacademy_import import (
    PRACTICE_ENRICHMENT, SourceIndex, Assets, Renderer, adapt, file_hash, prepare, install, source_fingerprint,
)
from graspmemoedu.catalog import Catalog
from graspmemoedu.config import Settings
from graspmemoedu.course_graph import GraphStore
from graspmemoedu.api import create_app
from graspmemoedu.site_backup import backup_site, restore_site
from graspmemoedu.question_types import validate_interaction, public_interaction, parse_answer, deterministic_verdict
from graspmemoedu.service import create_learning_service
from tests.fixtures import temporary_test_directory, DeterministicJudge
from tests.test_ordered_learning import ordered_topic, payload, active


def source(tid):
    return {'lesson': {'topic': {'id': tid, 'name': 'Synthetic ' + str(tid)}, 'taskId': 123,
        'steps': [{'id': 10, 'number': 1, 'type': 'tutorial', 'contentId': 100 + tid,
                   'tutorial': {'id': 100 + tid, 'title': 'Synthetic guidance', 'content': '> ```python\n> if x < 4:\n>     x += 1\n> ```', 'html': ''}},
                  {'id': 11, 'number': 2, 'type': 'example', 'contentId': 200 + tid,
                   'example': {'id': 200 + tid, 'title': 'Synthetic example', 'question': 'Read $x^2$.', 'explanation': '', 'calculator': 'None'}},
                  {'id': 12, 'number': 3, 'type': 'question', 'contentId': 300 + tid,
                   'question': {'id': 300 + tid, 'exampleId': 200 + tid, 'text': 'Fill the number of faces.', 'format': 'FR',
                                'freeResponse': {'segments': [{'textbox': {'answer': 'PRIVATE-CANDIDATE', 'type': 'number'}}, {'text': ' face(s)'}]}}}]}}


def composite():
    return {'version': 2, 'type': 'composite', 'grading': 'exact',
        'controls': [{'id': f'c{i}', 'type': 'select', 'options': [{'id': 'yes', 'text': 'Yes'}, {'id': 'no', 'text': 'No'}], 'answers': ['yes']} for i in range(23)],
        'sections': [{'id': f's{i}', 'html': '<p>Section</p>', 'complete': True,
                      'control_ids': [f'c{n}' for n in range(23) if n % 10 == i]} for i in range(10)]}


class MathAcademyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = temporary_test_directory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name); self.data = self.root / 'site'; self.cache = self.root / 'cache'; self.package = self.root / 'package'
        self.topics = self.root / 'topics.zip'; self.graphs = self.root / 'graphs.zip'
        with zipfile.ZipFile(self.topics, 'w') as z:
            for tid in (1, 2, 3):
                z.writestr(f'topic-json/topic-{tid}.json', json.dumps(source(tid)))
        with zipfile.ZipFile(self.graphs, 'w') as z:
            for cid, tids in [(10, [1, 2]), (20, [2, 3])]:
                nodes = {str(tid): {'id': tid, 'name': 'Synthetic ' + str(tid),
                    'course': {'id': cid, 'name': 'Course ' + str(cid)}, 'unit': {'id': 1, 'number': 1, 'name': 'Unit'},
                    'module': {'id': 1, 'number': 1, 'name': 'Module'}, 'prerequisites': [1] if tid == 2 else []} for tid in tids}
                z.writestr(f'course-knowledge-graph/course-{cid}.json', json.dumps({'topics': nodes}))
        self.index = SourceIndex(self.topics, self.graphs)
        self.addCleanup(self.index.archive.close)

    def prepared(self):
        prepare(self.index, self.index.scope([20]), self.cache, self.package)

    def test_scope_is_explicit_graph_closure_and_fingerprint_ignores_capture_state(self):
        self.assertEqual(self.index.scope([20])['topic_ids'], [1, 2, 3])
        a, b = source(1), source(1); b['lesson']['taskId'] = 999
        b['lesson']['steps'][2]['question']['rendered'] = True
        self.assertEqual(source_fingerprint(a), source_fingerprint(b))
        b['lesson']['steps'][0]['tutorial']['content'] = 'Changed teaching'
        self.assertNotEqual(source_fingerprint(a), source_fingerprint(b))

    def test_indented_original_choice_image_uses_the_same_source_renderer(self):
        capture = source(1)
        png = ('data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC'
               '0lEQVR42mP8/x8AAwMCAO+jR8sAAAAASUVORK5CYII=')
        raw = '    <img src="' + png + '" />'
        capture['lesson']['steps'][2]['question'].update(format='MC', choice1=raw, choice2='`<img>`')
        renderer = Renderer()
        try:
            topic = renderer.render(adapt(capture, Assets(self.cache, {})))
        finally:
            renderer.close()
        option, code = topic['modules'][0]['practices'][0]['interaction']['options']
        self.assertEqual(option['text'], raw)
        self.assertIn('<img src="' + png + '"', option['html'])
        self.assertIn('<code>&lt;img&gt;</code>', code['html'])

    def test_atomic_activation_idempotency_shared_identity_and_backup(self):
        self.prepared()
        with self.assertRaisesRegex(RuntimeError, 'pre-activation'):
            install(self.package, self.data, fail_at='activate')
        self.assertFalse((self.data / 'active-content.json').exists())
        result = install(self.package, self.data)
        self.assertEqual(result['status'], 'installed_with_source_gaps')
        self.assertEqual(result['trainable'], 0)
        before = (self.data / 'active-content.json').read_bytes()
        self.assertEqual(install(self.package, self.data)['status'], 'unchanged')
        self.assertEqual(before, (self.data / 'active-content.json').read_bytes())
        settings = Settings(data_dir=self.data); catalog = Catalog.load(settings)
        self.assertEqual(catalog.topic_courses['ma-topic-2'], {'ma-course-10', 'ma-course-20'})
        self.assertIsNone(catalog.course_context('ma-topic-2')['id'])
        self.assertEqual(GraphStore(settings, catalog).dependencies()['ma-topic-2'], ['ma-topic-1'])
        reader = create_learning_service(catalog.topic('ma-topic-2'), self.data)
        state = reader.state()
        self.assertTrue(state['read_only'])
        practice = next(row for row in state['blocks'] if row['id'] == 'ma-question-302')
        self.assertTrue(practice['preview_answer'])
        self.assertEqual(practice['interaction']['type'], 'composite')
        self.assertEqual(practice['actions'], [])
        self.assertNotIn('PRIVATE-CANDIDATE', json.dumps(state))
        with closing(sqlite3.connect(self.data / 'learning.sqlite3')) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM topics').fetchone()[0], 0)
        result = backup_site(settings, self.root / 'backup.zip')
        restore_site(self.root / 'backup.zip', self.root / 'restored')
        restored = Catalog.load(Settings(data_dir=self.root / 'restored'))
        self.assertEqual(restored.topics, catalog.topics)
        self.assertEqual(restored.topic_courses, catalog.topic_courses)
        restored_state = create_learning_service(restored.topic('ma-topic-2'), self.root / 'restored').state()
        self.assertTrue(next(row for row in restored_state['blocks'] if row['id'] == practice['id'])['preview_answer'])

    def test_enrichment_upgrades_existing_read_only_topic_in_both_courses(self):
        from graspmemoedu.lesson_display import DIRECTORY, display_key
        from graspmemoedu.topic_install import encoded

        self.prepared()
        install(self.package, self.data)
        settings = Settings.load(self.data)
        old = Catalog.load(settings)
        tid = 'ma-topic-2'
        topic = deepcopy(old.topics[tid])
        before = old.topic_paths[tid]
        source_file = settings.content_dir / 'mathacademy-sources' / 'topics' / f'{tid}.json'
        raw_before = file_hash(source_file)
        module = topic['modules'][0]
        module['example'].update(reference_answer='4', explanation_html='<p>Two squared is four.</p>', constraints='Exact.')
        q = module['practices'][0]
        q.update(reference_answer='6', explanation_html='<p>A cube has six faces.</p>', constraints='Exact.')
        q['interaction']['grading'] = 'exact'
        q['interaction']['controls'][0]['answers'] = ['6']
        module['practices'].extend({**deepcopy(q), 'id': f'variant-{i}'} for i in range(6))
        topic['availability'].update(trainable=True, reasons=[])
        topic['version'] = 'new-synthetic-version'
        paths = {
            f'topics/{tid}.json': topic,
            f'{DIRECTORY}/{tid}.json': {'schema': 1, 'topic_id': tid, 'version': topic['version'],
                                       'values': {display_key('html', topic['introductions'][0]['html']): '<p>译文</p>'}},
            'report.json': {'readable': 1, 'trainable': 1, 'untrainable': 0},
            'catalog.json': {'courses': [{'id': 'ma-course-20', 'description': old.courses['ma-course-20']['description'],
                                          'units': [], 'topics': [{'id': tid, 'path': f'topics/{tid}.json'}]}]},
        }
        upgrade = self.root / 'enrichment'
        for name, payload in paths.items():
            path = upgrade / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(encoded(payload))
        manifest = {'schema': 1, 'kind': PRACTICE_ENRICHMENT,
                    'enrichment': {tid: {'topic_sha256': '0' * 64, 'raw_sha256': raw_before}},
                    'files': {name: file_hash(upgrade / name) for name in paths}}
        path = upgrade / 'manifest.json'
        path.write_bytes(encoded(manifest))
        pointer = self.data / 'active-content.json'
        original_pointer = pointer.read_bytes()
        with self.assertRaisesRegex(ValueError, 'source or version differs'):
            install(upgrade, self.data)
        self.assertEqual(pointer.read_bytes(), original_pointer)
        manifest['enrichment'][tid]['topic_sha256'] = file_hash(before)
        display_rel = f'{DIRECTORY}/{tid}.json'
        display_path = upgrade / display_rel
        archived = {**paths[display_rel], 'values': {**paths[display_rel]['values'], 'stale': '<p>旧译文</p>'}}
        display_path.write_bytes(encoded(archived))
        manifest['files'][display_rel] = file_hash(display_path)
        path.write_bytes(encoded(manifest))
        with self.assertRaisesRegex(ValueError, 'unbound display fields'):
            install(upgrade, self.data)
        self.assertEqual(pointer.read_bytes(), original_pointer)
        display_path.write_bytes(encoded(paths[display_rel]))
        manifest['files'][display_rel] = file_hash(display_path)
        path.write_bytes(encoded(manifest))
        with self.assertRaisesRegex(RuntimeError, 'pre-activation'):
            install(upgrade, self.data, fail_at='activate')
        self.assertEqual(pointer.read_bytes(), original_pointer)
        self.assertEqual(install(upgrade, self.data)['upgraded'], [tid])
        installed = Catalog.load(Settings.load(self.data))
        self.assertEqual(installed.courses, old.courses)
        self.assertEqual(installed.topic_courses[tid], old.topic_courses[tid])
        self.assertTrue(installed.topics[tid]['availability']['trainable'])
        self.assertEqual(file_hash(Settings.load(self.data).content_dir / 'mathacademy-sources' / 'topics'
                                   / f'{tid}.json'), raw_before)
        self.assertEqual(install(upgrade, self.data)['status'], 'unchanged')

    def test_reader_and_catalog_enforce_test_purpose_and_qualification(self):
        self.prepared(); install(self.package, self.data)
        settings = Settings(data_dir=self.data, public_api_origin='https://source.test', allowed_origins=('https://site.test',))
        app = create_app(settings)
        with TestClient(app, base_url='https://source.test') as client:
            headers = {'Origin': 'https://site.test'}
            guest = client.post('/api/access/guest', headers=headers, json={}).json()
            headers['X-Learning-Identity'] = guest['identity_token']
            self.assertEqual(client.get('/api/catalog', headers=headers).json()['courses'], [])
            for flags, allowed in [({'purpose': 'test'}, False), ({'purpose': 'learner', 'is_advanced_learner': True, 'is_student': True}, False),
                                   ({'purpose': 'test', 'is_advanced_learner': True, 'is_student': True}, True),
                                   ({'purpose': 'learner', 'is_admin': True}, False), ({'purpose': 'test', 'is_admin': True}, True)]:
                with app.state.access_store._transaction() as con:
                    account = app.state.access_store._insert_account(con, 'Synthetic', **flags)
                login = client.post('/api/access/login', headers=headers, json={'invitation_code': account['invitation_code']})
                self.assertEqual(login.status_code, 200, login.text)
                headers['X-Learning-Identity'] = login.json()['identity_token']
                response = client.get('/api/state?topic_id=ma-topic-2&subject_id=math', headers=headers)
                self.assertEqual(response.status_code, 200 if allowed else 403, response.text[:200])
                if allowed:
                    self.assertTrue(response.json()['read_only'])
                    self.assertEqual(response.json()['learner_id'], login.json()['access']['learner_id'])
                    dashboard = client.get('/api/dashboard?course_id=ma-course-20&subject_id=math', headers=headers)
                    self.assertEqual(dashboard.status_code, 200, dashboard.text[:300])
                    self.assertEqual(dashboard.json()['tasks'], [])
                    self.assertEqual({t['status'] for t in dashboard.json()['topics']}, {'read_only'})

    def test_material_and_help_previews_reuse_existing_guidance_translation(self):
        from graspmemoedu.content_reports import ContentText
        from graspmemoedu.lesson_display import DIRECTORY, display_key

        self.prepared()
        install(self.package, self.data)
        settings = Settings.load(self.data)
        topic = Catalog.load(settings).topics['ma-topic-2']
        intro = topic['introductions'][0]
        translated = '<p>学生当前看见的指导。</p>'
        file = settings.content_dir / DIRECTORY / (topic['id'] + '.json')
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps({'schema': 1, 'topic_id': topic['id'], 'version': topic['version'],
                                    'values': {display_key('html', intro['html']): translated,
                                               display_key('title', intro['title']): '已翻译的指导'}}),
                        encoding='utf-8')
        app = create_app(settings)
        with TestClient(app, base_url='http://127.0.0.1:8767') as client:
            headers = {'Origin': 'http://127.0.0.1:8767'}
            headers['X-Learning-Session'] = client.get('/api/session', headers=headers).json()['session_token']
            roles = [{'is_admin': True}, {'is_advanced_learner': True, 'is_student': True}]
            accounts = []
            for role in roles:
                with app.state.access_store._transaction() as con:
                    account = app.state.access_store._insert_account(con, 'Preview fixture', purpose='test', **role)
                login = client.post('/api/access/login', headers=headers, json={'invitation_code': account['invitation_code']})
                self.assertEqual(login.status_code, 200, login.text)
                accounts.append(login.json())
            admin = {**headers, 'X-Learning-Identity': accounts[0]['identity_token']}
            student = {**headers, 'X-Learning-Identity': accounts[1]['identity_token']}
            block = 'introduction:' + intro['id']
            preview = client.get('/api/materials/content', headers=admin, params={'topic_id': topic['id'], 'subject_id': 'math'})
            self.assertEqual(preview.status_code, 200, preview.text[:400])
            material = next(item for item in preview.json()['blocks'] if item['id'] == block)
            self.assertEqual((material['title'], material['html']), ('已翻译的指导', translated))

            context = {'topic_id': topic['id'], 'content_block_id': block, 'content_version': topic['version']}
            help_view = client.post('/api/help-requests/preview?subject_id=math', headers=student, json=context)
            self.assertEqual(help_view.status_code, 200, help_view.text[:400])
            self.assertIn('学生当前看见的指导。', help_view.json()['content_html'])

            help_store = app.state.help_requests
            legacy = {'id': 'legacy', 'learner_id': accounts[1]['access']['learner_id'], 'created_at': 'fixture',
                      'body': json.dumps({'request': {**context, 'request_id': 'legacy', 'message': 'fixture'},
                                          'content_text': ''.join(ContentText(intro['html']).parts)})}
            self.assertEqual(help_store._render_record(legacy)['content_html'], intro['html'])

    def test_later_import_keeps_earlier_previews_when_adding_shared_topics(self):
        from graspmemoedu.lesson_display import DIRECTORY

        first = self.root / 'first-package'
        prepare(self.index, self.index.scope([10]), self.cache, first)
        install(first, self.data)
        path = Settings.load(self.data).content_dir / DIRECTORY / 'preview.json'
        before = json.loads(path.read_bytes())['topics']
        self.assertEqual(set(before), {'ma-topic-1', 'ma-topic-2'})
        self.prepared()
        install(self.package, self.data)
        path = Settings.load(self.data).content_dir / DIRECTORY / 'preview.json'
        after = json.loads(path.read_bytes())['topics']
        self.assertEqual(set(after), {*before, 'ma-topic-3'})
        self.assertEqual({tid: after[tid] for tid in before}, before)

    def test_composite_submission_requires_all_ten_sections_and_hides_keys(self):
        spec = composite(); validate_interaction(spec)
        question = {'interaction': spec}; public = public_interaction(question)
        self.assertNotIn('answers', json.dumps(public))
        answer = {'section': 9, 'values': {f'c{i}': 'yes' for i in range(23)}}
        self.assertTrue(deterministic_verdict(question, json.dumps(answer))[0])
        answer['section'] = 8
        with self.assertRaises(ValueError):
            parse_answer(question, json.dumps(answer))
        spec['sections'][9]['complete'] = False
        with self.assertRaises(ValueError):
            validate_interaction(spec)

    def test_independent_guidance_and_saved_group_keep_their_translations(self):
        from graspmemoedu.lesson_display import DIRECTORY, display_key

        topic = ordered_topic()
        topic.update(id='ma-topic-682', source_adapter='mathacademy')
        intro = topic['introductions'][0]
        extra = {'id': 'next-guidance', 'title': 'Next & details', 'html': '<p>Second explanation.</p>'}
        topic['introductions'].insert(1, extra)
        topic['content_order'].insert(1, {'kind': 'introduction', 'id': extra['id']})
        directory = self.data / DIRECTORY
        directory.mkdir(parents=True)
        (directory / (topic['id'] + '.json')).write_text(json.dumps({
            'schema': 1, 'topic_id': topic['id'], 'version': topic['version'],
            'values': {display_key('html', intro['html']): '<p>第一段指导。</p>',
                       display_key('title', extra['title']): '下一节 & 细节',
                       display_key('html', extra['html']): '<p>第二段指导。</p>'},
        }), encoding='utf-8')

        service = create_learning_service(topic, self.data, DeterministicJudge())
        recap = active(service.state())
        self.assertEqual(recap['introduction_id'], intro['id'])
        self.assertEqual(recap['html'], '<p>第一段指导。</p>')
        service.advance(payload(service))
        guidance = active(service.choose(payload(service, choice='unmastered')))
        self.assertEqual(guidance['introduction_ids'], [extra['id']])
        self.assertEqual(guidance['title'], '下一节 & 细节')
        self.assertEqual(guidance['html'], '<p>第二段指导。</p>')

        # A previously saved multi-block step remains readable in history.
        with service._transaction() as con:
            saved = service._load(con)
            service._step(saved).update(introduction_id=intro['id'], introduction_ids=[intro['id'], extra['id']])
            service._save(con, saved)
        guidance = active(service.state())
        self.assertEqual(guidance['introduction_ids'], [intro['id'], extra['id']])
        self.assertIn('<p>第一段指导。</p>', guidance['html'])
        self.assertIn('<h3>下一节 &amp; 细节</h3><p>第二段指导。</p>', guidance['html'])
        self.assertNotIn(extra['html'], guidance['html'])
        self.assertEqual(service.course['introductions'][1], extra)

    def test_trailing_guidance_survives_mastered_path_refresh_and_replay(self):
        topic = ordered_topic()
        topic['introductions'].append({'id': 'tail', 'title': 'Final proof', 'html': '<p>Proof</p>'})
        topic['content_order'].append({'kind': 'introduction', 'id': 'tail'})
        service = create_learning_service(topic, self.data, DeterministicJudge())
        for _ in topic['modules']:
            service.choose(payload(service, choice='mastered'))
            result = service.submit(payload(service, answer='correct')); service.process_submission(result['submission_id'])
            service.advance(payload(service))
        self.assertEqual(service.state()['status'], 'in_progress')
        self.assertEqual(active(service.state())['introduction_id'], 'tail')
        service = create_learning_service(topic, self.data, DeterministicJudge())
        self.assertEqual(active(service.state())['introduction_id'], 'tail')
        action = payload(service); service.advance(action); service.advance(action)
        self.assertEqual(service.state()['status'], 'completed')
        with closing(service._connect()) as con:
            state = json.loads(con.execute('SELECT body FROM topics').fetchone()[0])
            self.assertEqual(state['read_introductions'].count('tail'), 1)


if __name__ == '__main__':
    unittest.main()
