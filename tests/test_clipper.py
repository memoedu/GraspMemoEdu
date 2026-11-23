from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import json
import os
import unittest
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
        for route in ['types', 'items', 'excerpts?period=all']:
            self.assertEqual(self.read(route, guests).status_code, 403)
        self.assertEqual(self.post('items', self.item(), guests).status_code, 403)

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
