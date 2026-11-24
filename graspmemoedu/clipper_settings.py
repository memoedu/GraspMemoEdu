"""Per-account clipper preferences and credentials for explicitly bound services."""
import base64
from contextlib import closing
from functools import lru_cache
import ipaddress
import json
import os
from pathlib import Path
import socket
import ssl
from http.client import HTTPSConnection
from urllib.parse import urlsplit
from typing import Literal

import httpx
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from .service import DomainError


@lru_cache
def catalog():
    return json.loads(Path(__file__).with_name('clipper_catalog.json').read_bytes())


class Binding(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    service: Literal['model', 'speech', 'ocr']
    mode: Literal['site', 'own', 'remove']
    endpoint: str = Field(default='', max_length=512)
    model: str = Field(default='', max_length=160)
    secret: SecretStr | None = Field(default=None, min_length=1, max_length=4096)


class Preferences(BaseModel):
    model_config = ConfigDict(extra='forbid', hide_input_in_errors=True)
    revision: int = Field(ge=0)
    values: dict = Field(default_factory=dict)
    rules: dict[str, str] = Field(default_factory=dict)
    bindings: list[Binding] = Field(default_factory=list, max_length=3)


def checked_endpoint(value):
    try:
        url = urlsplit(value.strip().rstrip('/'))
        port = url.port or 443
        if (url.scheme != 'https' or not url.hostname or url.username is not None or url.password is not None
                or url.query or url.fragment or any(ord(c) < 33 or c == '\\' for c in value)
                or not 1 <= port <= 65535):
            raise ValueError
        address = url.hostname.encode('idna').decode('ascii')
        if '%' in address:
            raise ValueError
        return address, port, url.path.rstrip('/')
    except (UnicodeError, ValueError):
        raise DomainError('invalid_clip_service', '服务地址需为公开 HTTPS API 基址。', 422) from None


def _public(address):
    value = ipaddress.ip_address(address)
    if value.version == 6 and value.ipv4_mapped:
        value = value.ipv4_mapped
    return value.is_global and not value.is_multicast and not value.is_reserved


def provider_post(config, suffix, data, timeout, limit):
    host, port, prefix = checked_endpoint(config['base_url'])
    if config.get('site_service'):
        # Operators may use the site's configured HTTPS gateway or network proxy.
        # Only the server-selected default receives this marker in resolve().
        try:
            with httpx.stream('POST', config['base_url'].rstrip('/') + suffix, json=data,
                              headers={'Authorization': 'Bearer ' + config['api_key']},
                              verify=ssl.create_default_context(), timeout=timeout, follow_redirects=False) as response:
                if not 200 <= response.status_code < 300:
                    raise DomainError('clip_provider_error', f'所选服务返回 HTTP {response.status_code}。', 502)
                output = bytearray()
                for chunk in response.iter_bytes(chunk_size=65536):
                    output.extend(chunk)
                    if len(output) > limit:
                        raise DomainError('clip_provider_output', '服务结果超出大小限制。', 502)
                if not output:
                    raise DomainError('clip_provider_output', '服务结果为空。', 502)
                return bytes(output), response.headers.get('Content-Type', '').split(';')[0]
        except httpx.RequestError:
            raise DomainError('clip_provider_unavailable', '无法连接站点配置的服务。', 502) from None
    # Connect to a validated address from this resolution and use the original hostname for TLS.
    addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    if not addresses or any(not _public(entry[4][0]) for entry in addresses):
        raise DomainError('invalid_clip_service', '服务地址必须可从公网访问。', 422)
    context = ssl.create_default_context()
    with closing(HTTPSConnection(host, port, timeout=timeout, context=context)) as con:
        family, kind, proto, _, address = addresses[0]
        raw = socket.socket(family, kind, proto)
        try:
            raw.settimeout(timeout)
            raw.connect(address)
            con.sock = context.wrap_socket(raw, server_hostname=host)
        except BaseException:
            raw.close()
            raise
        con.request('POST', prefix + suffix, json.dumps(data, ensure_ascii=False).encode(),
                    {'Authorization': 'Bearer ' + config['api_key'], 'Content-Type': 'application/json'})
        with con.getresponse() as response:
            if not 200 <= response.status < 300:
                raise DomainError('clip_provider_error', f'所选服务返回 HTTP {response.status}。', 502)
            body = response.read(limit + 1)
            if not body or len(body) > limit:
                raise DomainError('clip_provider_output', '服务结果为空或超出大小限制。', 502)
            return body, response.getheader('Content-Type', '').split(';')[0]


def vault():
    try:
        material = os.environ['GRASPMEMOEDU_CLIPPER_VAULT_KEY']
        key = base64.b64decode(material, validate=True)
        if len(key) != 32:
            raise ValueError
        return AESGCM(key)
    except (KeyError, ValueError):
        raise DomainError('clip_vault_unavailable', '站点尚未配置账号凭据托管。', 503) from None


def account_types(overrides):
    result, excerpts = {}, set()
    for name in ('modes.json', 'image-modes.json', 'excerpt-modes.json', 'chat/question-types.json'):
        if name not in overrides:
            continue
        chat = name.startswith('chat/')
        bundle = json.loads(overrides[name])
        if not isinstance(bundle, dict) or not isinstance(bundle.get('types' if chat else 'modes'), list):
            raise DomainError('invalid_clip_rules', '自定义模式需包含类型列表。', 422)
        for definition in bundle['types' if chat else 'modes']:
            label_key = 'label' if chat else 'name'
            if not isinstance(definition, dict):
                raise DomainError('invalid_clip_rules', '无效的模式定义。', 422)
            key, label = definition.get('id'), definition.get(label_key)
            if not isinstance(key, str) or not 0 < len(key) <= 70 or not isinstance(label, str) or not label.strip():
                raise DomainError('invalid_clip_rules', '模式需要类型标识和名称。', 422)
            result[key] = label
            if name == 'excerpt-modes.json':
                excerpts.add(key)
    return result, excerpts


def validate_preferences(update):
    fields = {field['key']: field for field in catalog()['workflow']['fields']}
    for key, value in update.values.items():
        field = fields.get(key)
        if not field:
            raise DomainError('invalid_clip_setting', '无法识别的剪藏设置。', 422)
        kind = field['kind']
        valid = ((kind == 'boolean' and (type(value) is bool or key == 'originalImageMode' and value is None))
                 or (kind == 'number' and type(value) is int and field['minimum'] <= value <= field['maximum'])
                 or (kind == 'choice' and value in [choice['value'] for choice in field['choices']])
                 or (kind == 'text' and isinstance(value, str) and len(value) <= 160 and
                     (value.isprintable() and bool(value) or field['group'] == 'shortcuts' and value == '')))
        if not valid:
            raise DomainError('invalid_clip_setting', '剪藏设置的值无效。', 422)
    if (len(update.rules) > len(catalog()['rules']) or any(
            name not in catalog()['rules'] or not value.strip() or len(value) > 80000
            for name, value in update.rules.items())):
        raise DomainError('invalid_clip_rules', '规则文件名称或内容无效。', 422)
    for name, value in update.rules.items():
        if name.endswith('.json'):
            try:
                json.loads(value)
            except ValueError:
                raise DomainError('invalid_clip_rules', '规则 JSON 格式无效。', 422) from None
    if len({binding.service for binding in update.bindings}) != len(update.bindings):
        raise DomainError('invalid_clip_service', '同一服务只能设置一次。', 422)
    account_types(update.rules)


class AccountPreferences:
    def __init__(self, access):
        self.access = access
        with closing(access._connect()) as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS clipper_preferences(
                  learner_id TEXT PRIMARY KEY, revision INTEGER NOT NULL, value_json TEXT NOT NULL, rules_json TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS clipper_bindings(
                  learner_id TEXT NOT NULL, service TEXT NOT NULL, active INTEGER NOT NULL, endpoint TEXT NOT NULL,
                  model TEXT NOT NULL, sealed BLOB NOT NULL, PRIMARY KEY(learner_id,service));
            """)

    @staticmethod
    def aad(owner, service, endpoint):
        return json.dumps([owner, service, endpoint], separators=(',', ':')).encode()

    def read(self, owner, con=None):
        if con is None:
            with closing(self.access._connect()) as connection:
                return self.read(owner, connection)
        row = con.execute('SELECT * FROM clipper_preferences WHERE learner_id=?', (owner,)).fetchone()
        bindings = {r['service']: {'active': bool(r['active']), 'bound': True, 'endpoint': r['endpoint'], 'model': r['model']}
                    for r in con.execute('SELECT service, active, endpoint, model FROM clipper_bindings WHERE learner_id=?', (owner,))}
        return {'revision': row['revision'] if row else 0,
                'values': {**catalog()['workflow']['defaults'], **(json.loads(row['value_json']) if row else {})},
                'rules': json.loads(row['rules_json']) if row else {}, 'bindings': bindings}

    def save(self, owner, update):
        validate_preferences(update)
        with closing(self.access._connect()) as con:
            con.execute('BEGIN IMMEDIATE')
            before = self.read(owner, con)
            if before['revision'] != update.revision:
                raise DomainError('stale_clip_settings', '设置已在其他页面更新，请重新打开后再保存。', 409)
            for binding in update.bindings:
                params = (owner, binding.service)
                if binding.mode == 'remove':
                    con.execute('DELETE FROM clipper_bindings WHERE learner_id=? AND service=?', params)
                elif binding.mode == 'site':
                    con.execute('UPDATE clipper_bindings SET active=0 WHERE learner_id=? AND service=?', params)
                else:
                    endpoint = binding.endpoint.strip().rstrip('/')
                    checked_endpoint(endpoint)
                    if not binding.model.strip() or not binding.model.isprintable():
                        raise DomainError('invalid_clip_service', '请填写服务使用的模型。', 422)
                    if binding.secret:
                        nonce = os.urandom(12)
                        sealed = nonce + vault().encrypt(nonce, binding.secret.get_secret_value().encode(),
                                                         self.aad(*params, endpoint))
                        con.execute('INSERT OR REPLACE INTO clipper_bindings VALUES(?,?,1,?,?,?)',
                                    (*params, endpoint, binding.model.strip(), sealed))
                    else:
                        result = con.execute('UPDATE clipper_bindings SET active=1, model=? WHERE learner_id=? AND service=? AND endpoint=?',
                                             (binding.model.strip(), *params, endpoint))
                        if result.rowcount != 1:
                            raise DomainError('clip_service_key_required', '启用新地址需要填写该地址的新凭据。', 422)
            con.execute('INSERT OR REPLACE INTO clipper_preferences VALUES(?,?,?,?)',
                        (owner, update.revision + 1, json.dumps(update.values), json.dumps(update.rules)))
            result = self.read(owner, con)
            con.commit()
            return result

    def resolve(self, owner, service, default):
        with closing(self.access._connect()) as con:
            row = con.execute('SELECT * FROM clipper_bindings WHERE learner_id=? AND service=? AND active=1',
                              (owner, service)).fetchone()
        if row is None:
            return {**default(), 'site_service': True}
        from cryptography.exceptions import InvalidTag
        blob = row['sealed']
        try:
            credential = vault().decrypt(blob[:12], blob[12:], self.aad(owner, service, row['endpoint'])).decode()
        except (ValueError, InvalidTag):
            raise DomainError('clip_vault_mismatch', '凭据无法解密，请检查站点托管配置。', 503) from None
        return {'api_key': credential, 'base_url': row['endpoint'], 'model': row['model']}
