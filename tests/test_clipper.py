from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import os
import base64
import unittest
from unittest.mock import Mock
from unittest.mock import patch
from uuid import uuid4

from graspmemoedu.clipper import ClipperStore
from graspmemoedu.service import DomainError
from tests import test_admin_students as fixtures


class ClipperTests(unittest.TestCase):
    setUp = fixtures.AdminStudentsTests.setUp
    identity = fixtures.AdminStudentsTests.identity

    def read(self, endpoint, headers=None):
        return self.client.get('/api/clipper/' + endpoint, headers=headers or self.normal_headers)

    def post(self, endpoint, payload, headers=None):
        return self.client.post('/api/clipper/' + endpoint, headers=headers or self.normal_headers, json=payload)

    def test_scoped_mimo_speech_keeps_text_and_selects_provider_voice(self):
        sentence = '若 x 的平方等于零点二五，另一结论成立。'
        env = {'GRASPMEMOEDU_CLIPPER_SPEECH_BASE_URL': 'https://api.xiaomimimo.com/v1',
               'GRASPMEMOEDU_CLIPPER_SPEECH_MODEL': 'mimo-v2.5-tts',
               'GRASPMEMOEDU_CLIPPER_SPEECH_API_KEY': 'site-test-only'}
        expected_audio = b'ID3 test MP3'

        def write_audio(text, output, **options):
            output.write_bytes(expected_audio)

        synthesize = Mock(side_effect=write_audio)
        with patch.dict(os.environ, env), patch('mimo_tts.client.synthesize', synthesize):
            for requested, expected in [('zh-CN-XiaoxiaoNeural', 'Mia'), ('mimo-Dean', 'Dean')]:
                with self.subTest(voice=requested):
                    response = self.post('workflow', {'operation': 'speech',
                        'input': {'text': sentence, 'voice': requested, 'ratePercent': 10, 'volumePercent': -20}})
                    self.assertEqual(response.status_code, 200, response.text)
                    self.assertEqual(base64.b64decode(response.json()['data']), expected_audio)
                    args, options = synthesize.call_args
                    self.assertEqual(args[0], sentence)
                    self.assertEqual(options, {'voice': expected, 'style': '', 'api_key': 'site-test-only',
                                               'cache': False, 'speed': 1.1, 'volume': 0.8})

    def item(self, **kwargs):
        return {'id': str(uuid4()), 'kind': 'card', 'type_id': 'fast-answer', 'front': r'Why \(x^2\)?',
                'back': 'Synthetic answer', 'source': {'text': 'Synthetic selection', 'route': '#/subjects/math/topic/demo'},
                **kwargs}

    def test_cards_and_fsrs_are_private_including_between_administrators(self):
        item = self.item()
        self.assertEqual(self.post('items', item).status_code, 200)
        self.assertEqual(self.post('items', item).status_code, 200)
        self.assertEqual(self.post('items', {**item, 'back': 'different'}).status_code, 409)
        own = self.read('items?due=true').json()['items']
        self.assertEqual([card['id'] for card in own], [item['id']])
        self.assertEqual(self.read('items', self.admin_headers).json()['items'], [])
        rating = {'id': item['id'], 'attempt': str(uuid4()), 'revision': 0, 'rating': 3}
        self.assertEqual(self.post('review', rating, self.admin_headers).status_code, 404)
        first = self.post('review', rating)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(self.post('review', rating).json(), first.json())
        self.assertEqual(self.post('review', {**rating, 'attempt': str(uuid4())}).status_code, 409)
        self.assertEqual(self.read('items?due=true').json()['items'], [])
        with closing(self.store._connect()) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM clipper_reviews').fetchone()[0], 1)

    def test_excerpts_export_only_owner_and_preserve_literal_content_and_formula(self):
        item = self.item(kind='excerpt', type_id='excerpt-manual',
                         front='Synthetic >> {{word}}\n求证 \\(x^2>0\\)', back='')
        result = self.post('items', item)
        self.assertEqual(result.status_code, 200, result.text)
        today = self.read('excerpts?period=today').json()
        self.assertEqual(today['count'], 1)
        self.assertIn(r'Synthetic \>\> \{\{word\}\}', today['markdown'])
        self.assertIn(r'        - 求证  $x^2>0$', today['markdown'])
        self.assertEqual(self.read('excerpts?period=all').json(), today)
        self.assertEqual(self.read('excerpts?period=all', self.headers).json(), {'count': 0, 'markdown': ''})
        self.assertEqual(self.read('items?due=true').json()['items'], [])

    def test_public_guests_cannot_read_or_mutate(self):
        guests = {'Origin': 'https://site.test', 'X-Learning-Identity': self.store.create_guest()['identity_token']}
        for route in ['types', 'items', 'excerpts?period=all', 'settings', 'rules',
                      'media?item=' + str(uuid4()) + '&digest=' + '0' * 64]:
            self.assertEqual(self.read(route, guests).status_code, 403)
        self.assertEqual(self.post('items', self.item(), guests).status_code, 403)
        for route, payload in [('settings', {'revision': 0}), ('reference', {'url': 'https://example.org/'}),
                               ('workflow', {'operation': 'speech', 'input': {'text': 'example'}})]:
            self.assertEqual(self.post(route, payload, guests).status_code, 403)

    def test_formula_code_and_inline_picture_round_trip_through_study_and_export(self):
        import base64
        import hashlib
        import io
        from zipfile import ZipFile
        from PIL import Image
        image = io.BytesIO()
        Image.new('RGB', (3, 2), 'navy').save(image, format='PNG')
        data = image.getvalue()
        digest = hashlib.sha256(data).hexdigest()
        fence = chr(96) * 3
        raw = ('若 \\(x>0\\)，则成立。\n\n' + fence + 'python\nif x > 0:\n    print(x)\n' + fence +
               '\n\n图 ![示意图](asset:' + digest + ') 在此。')
        item = self.item(kind='excerpt', type_id='excerpt-manual', front=raw, back='', media=[{
            'hash': digest, 'mime': 'image/png', 'side': 'front', 'data': base64.b64encode(data).decode()}])
        self.assertEqual(self.post('items', item).status_code, 200)
        self.assertEqual(self.post('items', item).status_code, 200)
        row, = self.read('items?kind=excerpt').json()['items']
        self.assertEqual((row['front'], row['media'][0]['hash']), (raw, digest))
        url = 'media?item=' + row['id'] + '&digest=' + digest
        self.assertEqual(base64.b64decode(self.read(url).json()['data']), data)
        self.assertEqual(self.read(url, self.admin_headers).status_code, 404)
        for period in ('today', 'all'):
            result = self.read('excerpts?period=' + period).json()
            with ZipFile(io.BytesIO(base64.b64decode(result['zip']))) as z:
                markdown = z.read('摘录.md').decode()
                self.assertEqual(markdown, result['markdown'])
                self.assertIn('$x>0$', markdown)
                self.assertIn(fence + 'python\n          if x > 0:\n              print(x)\n          ' + fence, markdown)
                path = 'media/' + digest + '.png'
                self.assertIn('图 ![示意图](' + path + ') 在此。', markdown)
                self.assertEqual(markdown.count(path), 1)
                self.assertEqual(z.read(path), data)

    def test_review_reads_a_single_card_and_list_projection_omits_unused_material(self):
        source = {**self.item()['source'], 'title': 'Visible source', 'context': 'Long original context'}
        first = self.item(source=source)
        second = self.item(source=source)
        for item in (first, second):
            self.assertEqual(self.post('items', item).status_code, 200)
        with patch.object(self.store, 'resolve', wraps=self.store.resolve) as resolve:
            page = self.read('items?due=true&compact=true&limit=1')
            self.assertEqual(page.status_code, 200, page.text)
            self.assertEqual(resolve.call_count, 1)
        self.assertEqual(page.json()['next'], 1)
        self.assertEqual(page.json()['items'][0]['source'], {'title': source['title'], 'route': source['route']})
        self.assertEqual(self.read('items?limit=31').status_code, 422)
        self.assertEqual(self.read('items').json()['items'][0]['source'], source)

    def test_model_actions_share_rules_without_leaking_source_links_or_main_judge_usage(self):
        calls = []

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, _):
                payload = calls[-1]
                output = ('{"cards":[{"front":"Synthetic question","back":"Synthetic answer","typeId":"fast-answer"}]}'
                          if 'allowedTypes' in payload['messages'][1]['content'] else 'Synthetic model output')
                return json.dumps({'choices': [{'finish_reason': 'stop', 'message': {'content': output}}]}).encode()

        def provider(req, **_):
            data = json.loads(req.data)
            calls.append(data)
            return Response()

        env = {'GRASPMEMOEDU_CLIPPER_API_KEY': 'synthetic', 'GRASPMEMOEDU_CLIPPER_BASE_URL': 'https://test.invalid/v1',
               'GRASPMEMOEDU_CLIPPER_MODEL': 'synthetic'}
        source = self.item()['source']
        with patch.dict(os.environ, env), patch('graspmemoedu.voice_input.urlopen', provider):
            for action in ('chat', 'compose', 'lookup'):
                result = self.post('model', {'action': action, 'source': {**source, 'context': 'Synthetic context'}})
                self.assertEqual(result.status_code, 200, result.text)
                self.assertIn('Synthetic', result.text)
        self.assertEqual(len(calls), 3)
        self.assertNotIn(source['route'], repr(calls))
        self.assertIn('Synthetic context', repr(calls))
        with closing(self.store._connect()) as con:
            self.assertEqual(con.execute('SELECT count FROM clipper_model_usage').fetchone()[0], 3)
        with closing(self.app.state.public_limits.daily._connect()) as con:
            self.assertEqual(con.execute('SELECT count(*) FROM usage').fetchone()[0], 0)
        with patch.dict(os.environ, {'GRASPMEMOEDU_CLIPPER_DAILY_ACCOUNT': '3'}):
            store = ClipperStore(self.store)
            with self.assertRaisesRegex(Exception, '额度'):
                store.record_model_call(self.normal)

    def test_private_settings_revisions_and_account_bound_service_credentials(self):
        from graspmemoedu.clipper_settings import AccountPreferences
        prefs = AccountPreferences(self.store)
        secret = 'synthetic-test-credential'
        binding = {'service': 'speech', 'mode': 'own', 'endpoint': 'https://test.invalid/v1',
                   'model': 'test-speech', 'secret': secret}
        initial = self.read('settings').json()
        self.assertTrue(initial['values']['contextEnabled'])
        self.assertEqual(initial['values']['contextGranularity'], 'sentence')
        with patch.dict(os.environ, {'GRASPMEMOEDU_CLIPPER_VAULT_KEY': base64.b64encode(os.urandom(32)).decode()}):
            data = {'revision': 0, 'values': {'contextGranularity': 'paragraph'}, 'bindings': [binding]}
            saved = self.post('settings', data)
            self.assertEqual(saved.status_code, 200, saved.text)
            self.assertNotIn(secret, saved.text)
            self.assertEqual(self.post('settings', data).status_code, 409)
            self.assertEqual(self.read('settings', self.admin_headers).json()['bindings'], {})
            self.assertEqual(prefs.resolve(self.normal, 'speech', lambda: {})['api_key'], secret)
            self.assertNotIn('site_service', prefs.resolve(self.normal, 'speech', lambda: {}))
            self.assertTrue(prefs.resolve(self.admin, 'speech', lambda: {})['site_service'])
            with closing(self.store._connect()) as con:
                self.assertNotIn(secret.encode(), con.execute('SELECT sealed FROM clipper_bindings').fetchone()[0])
            changed = {k: v for k, v in binding.items() if k != 'secret'}
            changed['endpoint'] = 'https://other.invalid/v1'
            self.assertEqual(self.post('settings', {'revision': 1, 'bindings': [changed]}).status_code, 422)
            self.assertEqual(self.read('settings').json()['revision'], 1)
            self.assertEqual(self.post('settings', {'revision': 1, 'bindings': [{'service': 'speech','mode': 'remove'}]}).status_code, 200)
            self.assertEqual(self.read('settings').json()['bindings'], {})

    def test_account_modes_save_and_list_only_for_their_owner(self):
        modes = json.dumps({'modes': [{'id': 'my-practice', 'name': '我的练习'}]})
        self.assertEqual(self.post('settings', {'revision': 0, 'rules': {'modes.json': modes}}).status_code, 200)
        item = self.item(type_id='my-practice')
        self.assertEqual(self.post('items', item).status_code, 200)
        self.assertEqual(self.post('items', item, self.admin_headers).status_code, 422)
        self.assertIn({'id': 'my-practice', 'label': '我的练习'}, self.read('types').json()['types'])
        self.assertNotIn('my-practice', self.read('types', self.admin_headers).text)
        self.assertEqual(self.post('settings', {'revision': 1, 'rules': {'modes.json': '{"modes": null}'}}).status_code, 422)

    def test_site_mineru_checks_completed_artifacts_and_preserves_tex(self):
        import io
        from pathlib import Path
        from zipfile import ZipFile
        from PIL import Image
        from graspmemoedu.clipper_gateway import ocr_call
        stream = io.BytesIO()
        Image.new('RGB', (6, 8), 'white').save(stream, format='PNG')
        data = {'data': base64.b64encode(stream.getvalue()).decode(), 'mineruLanguage': 'en',
                'mineruFormula': True, 'mineruTable': False}
        config = {'site_service': True, 'mineru_runner': str(Path(__file__).resolve())}
        markdown = r'Given \(x=6\), the result is \(x+7=13\).'
        def complete_run(args, **kwargs):
            self.assertNotIn('HTTP_PROXY', kwargs['env'])
            self.assertIn('--no-table', args)
            self.assertNotIn('--no-formula', args)
            output = Path(args[args.index('--output-dir')+1]) / 'run'
            output.mkdir(parents=True)
            (output/'manifest.json').write_text('{"results":[{"state":"done"}]}')
            (output/'source.md').write_text(markdown)
            with ZipFile(output/'mineru-result.zip', 'w') as archive:
                archive.writestr('full.md', markdown)
        with patch('graspmemoedu.clipper_gateway.subprocess.run', side_effect=complete_run):
            self.assertEqual(ocr_call(config, data, 90)['text'], markdown)
        with patch('graspmemoedu.clipper_gateway.subprocess.run'), self.assertRaises(DomainError):
            ocr_call(config, data, 90)

    def test_media_manifests_load_once_per_page_and_private_bytes_only_on_request(self):
        from graspmemoedu import clipper_media
        for _ in range(4):
            self.assertEqual(self.post('items', self.item()).status_code, 200)
        with patch.object(clipper_media, 'manifests', wraps=clipper_media.manifests) as manifests:
            rows = self.read('items?kind=card').json()['items']
        self.assertEqual(len(rows), 4)
        self.assertEqual(manifests.call_count, 1)
        self.assertEqual(set(manifests.call_args.args[2]), {row['id'] for row in rows})

    def test_concurrent_model_calls_preserve_usage_and_enforce_configured_caps(self):
        limits = ('GRASPMEMOEDU_CLIPPER_DAILY_ACCOUNT', 'GRASPMEMOEDU_CLIPPER_DAILY_GLOBAL')

        def record(store, learner):
            try:
                store.record_model_call(learner)
            except DomainError as exc:
                self.assertEqual((exc.code, exc.status_code), ('clip_quota', 429))
                return False
            return True

        for account_limit, global_limit, expected in ((0, 0, 8), (3, 0, 3), (0, 3, 3)):
            with self.subTest(account_limit=account_limit, global_limit=global_limit):
                with closing(self.store._connect()) as con:
                    con.execute('DELETE FROM clipper_model_usage')
                with patch.dict(os.environ, dict(zip(limits, map(str, (account_limit, global_limit))))):
                    store = ClipperStore(self.store)
                with ThreadPoolExecutor(max_workers=8) as workers:
                    allowed = list(workers.map(lambda _: record(store, self.normal), range(8)))
                self.assertEqual(sum(allowed), expected)
                with closing(self.store._connect()) as con:
                    self.assertEqual(con.execute('SELECT count FROM clipper_model_usage').fetchone()[0], expected)


if __name__ == '__main__':
    unittest.main()
