import base64
from datetime import datetime, timedelta, timezone
import json
import unittest

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
import httpx

from graspmemoedu.service import DomainError
from graspmemoedu.topic_sync_storage import GitHubFiles, SealedSnapshots


class TopicSyncStorageTests(unittest.TestCase):
    def setUp(self):
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.repo = 'test-owner/test-content'
        self.files = {}
        self.renewals = 0
        self.private = True
        self.client = httpx.Client(base_url='https://api.github.com', transport=httpx.MockTransport(self.github))
        self.addCleanup(self.client.close)
        self.storage = SealedSnapshots(GitHubFiles(self.repo, '1234', '5678', self.key, client=self.client),
                                       bytes(range(32)))

    def github(self, request):
        route, method = request.url.path, request.method
        self.assertEqual(request.url.host, 'api.github.com')
        if route == '/app/installations/5678/access_tokens':
            self.renewals += 1
            self.assertEqual(method, 'POST')
            self.assertEqual(json.loads(request.content), {
                'repositories': ['test-content'], 'permissions': {'contents': 'write'}})
            jwt = request.headers['authorization'].removeprefix('Bearer ')
            header, claims, signature = jwt.split('.')
            raw_signature = base64.urlsafe_b64decode(signature + '=' * (-len(signature) % 4))
            self.key.public_key().verify(raw_signature, (header + '.' + claims).encode(),
                                         padding.PKCS1v15(), hashes.SHA256())
            expiry = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            return httpx.Response(201, json={'token': 'synthetic-installation-value', 'expires_at': expiry})
        self.assertEqual(request.headers['authorization'], 'Bearer synthetic-installation-value')
        if route == '/repos/' + self.repo:
            return httpx.Response(200, json={'private': self.private, 'full_name': self.repo})
        prefix = '/repos/' + self.repo + '/contents/'
        self.assertTrue(route.startswith(prefix))
        filename = route.removeprefix(prefix)
        if method == 'PUT':
            payload = json.loads(request.content)
            self.assertEqual(payload['branch'], 'main')
            if filename in self.files:
                return httpx.Response(422, json={})
            self.files[filename] = base64.b64decode(payload['content'])
            return httpx.Response(201, json={})
        if filename not in self.files:
            return httpx.Response(404, json={})
        return httpx.Response(200, json={'type': 'file', 'encoding': 'base64',
                                        'content': base64.b64encode(self.files[filename]).decode()})

    def test_app_uses_one_scoped_token_and_never_uploads_topic_titles_or_plaintext(self):
        scope = ('personal', 'private-account-fixture', 'private-topic-fixture')
        document = {'title': 'Synthetic private content', 'blocks': []}
        revision = self.storage.save(scope, document)
        self.assertEqual(self.storage.save(scope, document), revision)
        self.assertEqual(self.storage.load(scope, revision), document)
        self.assertEqual(self.renewals, 1)
        self.assertEqual(len(self.files), 1)
        path, ciphertext = next(iter(self.files.items()))
        self.assertNotIn('private-account-fixture', path)
        self.assertNotIn('private-topic-fixture', path)
        self.assertNotIn(b'Synthetic private content', ciphertext)

    def test_a_repository_that_is_not_private_is_rejected_before_any_write(self):
        self.private = False
        with self.assertRaises(DomainError) as rejected:
            self.storage.save(('personal', 'account', 'topic'), {'title': 'example'})
        self.assertEqual(rejected.exception.status_code, 503)
        self.assertEqual(self.files, {})
