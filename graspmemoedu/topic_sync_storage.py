"""Authenticated, immutable Topic snapshots in a private GitHub repository."""

import base64
import binascii
from datetime import datetime
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
from threading import Lock
import time

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import httpx

from .service import DomainError


_REPO = re.compile(r'[A-Za-z0-9_-]+/[A-Za-z0-9_.-]+')
_REVISION = re.compile(r'[0-9a-f]{64}')
_FORMAT = b'GME1'
SNAPSHOT_LIMIT = 2 * 1024 * 1024


def _offline():
    return DomainError('topic_sync_storage_unavailable', '同步文件库暂不可用，请稍后重试。', 503)


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def _base64url(raw):
    return base64.urlsafe_b64encode(raw).rstrip(b'=').decode('ascii')


class GitHubFiles:
    """Installation credentials remain on the server. Only ciphertext crosses this boundary."""

    def __init__(self, repo, app_id, installation_id, private_key, *, client=None, clock=time.time):
        if not _REPO.fullmatch(repo) or not str(app_id).isdigit() or not str(installation_id).isdigit():
            raise ValueError('Invalid Topic sync GitHub configuration')
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise ValueError('Topic sync GitHub App requires an RSA key')
        self.repo = repo
        self.app_id = str(app_id)
        self.installation_id = str(installation_id)
        self.private_key = private_key
        self.client = client or httpx.Client(base_url='https://api.github.com', timeout=12)
        self.clock = clock
        self._token = ''
        self._expires_at = 0
        self._lock = Lock()

    def _request(self, method, route, token, *, accept='application/vnd.github+json', **kwargs):
        try:
            return self.client.request(method, route, headers={
                'Authorization': 'Bearer ' + token,
                'Accept': accept,
                'X-GitHub-Api-Version': '2026-03-10',
            }, **kwargs)
        except httpx.HTTPError:
            raise _offline() from None

    @staticmethod
    def _body(response, status):
        if response.status_code != status:
            raise _offline()
        try:
            return response.json()
        except ValueError:
            raise _offline() from None

    def _access_token(self):
        with self._lock:
            now = int(self.clock())
            if now < self._expires_at - 60:
                return self._token
            header = _base64url(_json({'alg': 'RS256', 'typ': 'JWT'}))
            claims = _base64url(_json({'iat': now - 60, 'exp': now + 480, 'iss': self.app_id}))
            message = f'{header}.{claims}'
            signature = self.private_key.sign(message.encode(), padding.PKCS1v15(), hashes.SHA256())
            response = self._request('POST', f'/app/installations/{self.installation_id}/access_tokens',
                                     f'{message}.{_base64url(signature)}',
                                     json={'repositories': [self.repo.split('/', 1)[1]],
                                           'permissions': {'contents': 'write'}})
            token = self._body(response, 201)
            try:
                access = token['token']
                expires = datetime.fromisoformat(token['expires_at']).timestamp()
                repository = self._body(self._request('GET', f'/repos/{self.repo}', access), 200)
                if repository['private'] is not True or repository['full_name'].lower() != self.repo.lower():
                    raise _offline()
            except (KeyError, TypeError, ValueError):
                raise _offline() from None
            self._token, self._expires_at = access, expires
            return access

    def read(self, path):
        response = self._request('GET', f'/repos/{self.repo}/contents/{path}', self._access_token(),
                                 params={'ref': 'main'}, accept='application/vnd.github.object+json')
        if response.status_code == 404:
            return None
        value = self._body(response, 200)
        try:
            # The Contents endpoint requires raw media for objects above 1 MiB.
            if value['encoding'] == 'none':
                return self._read_large_blob(value['sha'])
            if value['type'] != 'file' or value['encoding'] != 'base64':
                raise _offline()
            return base64.b64decode(''.join(value['content'].split()), validate=True)
        except (KeyError, TypeError, ValueError, binascii.Error):
            raise _offline() from None

    def _read_large_blob(self, sha):
        if not isinstance(sha, str) or not re.fullmatch('[a-f0-9]{40}', sha):
            raise _offline()
        blob = self._body(self._request('GET', f'/repos/{self.repo}/git/blobs/{sha}', self._access_token()), 200)
        try:
            if blob['encoding'] != 'base64':
                raise _offline()
            return base64.b64decode(''.join(blob['content'].split()), validate=True)
        except (KeyError, TypeError, ValueError, binascii.Error):
            raise _offline() from None

    def write_new(self, path, data):
        response = self._request('PUT', f'/repos/{self.repo}/contents/{path}', self._access_token(), json={
            'branch': 'main', 'message': 'Save immutable content revision',
            'content': base64.b64encode(data).decode('ascii'),
        })
        if response.status_code == 201:
            return True
        if response.status_code in (409, 422):
            return False
        raise _offline()


class SealedSnapshots:
    def __init__(self, files, key):
        if len(key) != 32:
            raise ValueError('Topic sync encryption requires a 32-byte key')
        self.files = files
        self._cipher = AESGCM(hmac.digest(key, b'graspmemoedu/topic-sync/encryption/v1', 'sha256'))
        self._index_key = hmac.digest(key, b'graspmemoedu/topic-sync/index/v1', 'sha256')

    def _location(self, scope, revision):
        if not _REVISION.fullmatch(revision):
            raise ValueError('Invalid Topic sync revision')
        folder = hmac.digest(self._index_key, _json(scope), 'sha256').hex()
        return f'snapshots/{folder[:2]}/{folder}/{revision}.bin', _json([scope, revision])

    def _revision(self, scope, data):
        return hmac.digest(self._index_key, _json(scope) + b'\0' + data, 'sha256').hex()

    def fingerprint(self, scope, snapshot):
        return self._revision(scope, _json(snapshot))

    def save(self, scope, snapshot):
        data = _json(snapshot)
        if len(data) > SNAPSHOT_LIMIT:
            raise DomainError('topic_sync_document_too_large', '正文超过单次同步上限。', 413)
        revision = self._revision(scope, data)
        path, aad = self._location(scope, revision)
        nonce = os.urandom(12)
        sealed = _FORMAT + nonce + self._cipher.encrypt(nonce, data, aad)
        if not self.files.write_new(path, sealed) and self.load(scope, revision) != snapshot:
            raise _offline()
        return revision

    def load(self, scope, revision):
        path, aad = self._location(scope, revision)
        sealed = self.files.read(path)
        if not sealed or not sealed.startswith(_FORMAT) or len(sealed) > SNAPSHOT_LIMIT + 32:
            raise _offline()
        try:
            data = self._cipher.decrypt(sealed[4:16], sealed[16:], aad)
            if not hmac.compare_digest(revision, self._revision(scope, data)):
                raise _offline()
            return json.loads(data)
        except (InvalidTag, ValueError):
            raise _offline() from None


def configured_snapshots():
    """Load explicit service credentials, never ambient CLI credentials."""
    repo = os.environ.get('GRASPMEMOEDU_SYNC_REPO')
    if not repo:
        return None
    try:
        key = base64.b64decode(Path(os.environ['GRASPMEMOEDU_SYNC_ENCRYPTION_KEY_FILE']).read_bytes().strip(),
                               validate=True)
        private_key = serialization.load_pem_private_key(
            Path(os.environ['GRASPMEMOEDU_SYNC_GITHUB_KEY_FILE']).read_bytes(), password=None)
        return SealedSnapshots(GitHubFiles(repo, os.environ['GRASPMEMOEDU_SYNC_GITHUB_APP'],
                                           os.environ['GRASPMEMOEDU_SYNC_GITHUB_INSTALLATION'], private_key), key)
    except (KeyError, OSError, ValueError):
        raise ValueError('Topic sync service credentials are incomplete or invalid') from None
