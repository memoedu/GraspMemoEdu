"""Account-locked device pairing and the optimistic Topic revision index."""

from contextlib import closing
import hmac
import re
import secrets
import sqlite3
import time

from .access import credential_digest
from .service import DomainError


PAIR_LIFETIME = 120
OPEN_LIFETIME = 45
DEVICE_SECRET = re.compile(r'[A-Za-z0-9_-]{43}')


def _require_account(access):
    if access['role'] != 'account':
        raise DomainError('topic_sync_login_required', '请登录后使用 Topic 与 RemNote 同步。', 403)
    return access['learner_id']


def account_mismatch():
    return DomainError('topic_sync_account_mismatch', '当前账号与本机绑定不一致。请切换到原绑定的网站账号。', 403)


def _device_missing():
    return DomainError('topic_sync_device_unpaired', '请先将当前网站账号与本机 RemNote 配对。', 403)


def _document_unbound():
    return DomainError('topic_sync_document_unbound', '此 Topic 尚未绑定本地 RemNote Document。', 404)


def _stale_revision():
    return DomainError('topic_sync_stale_revision', '正文已有新版本。请保留当前改动并重新读取后再同步。', 409)


class TopicSyncStore:
    def __init__(self, access_store, snapshots, *, groups=None, clock=time.time):
        self.access_store = access_store
        self.snapshots = snapshots
        self.groups = groups
        self.clock = clock
        with closing(access_store._connect()) as con:
            con.executescript("""
                CREATE TABLE IF NOT EXISTS topic_sync_exclusions (
                    learner_id TEXT PRIMARY KEY REFERENCES access_principals(learner_id));
                CREATE TABLE IF NOT EXISTS topic_sync_pair_tickets (
                    ticket_digest TEXT PRIMARY KEY,
                    identity_digest TEXT NOT NULL,
                    learner_id TEXT NOT NULL REFERENCES access_principals(learner_id),
                    expires_at INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS topic_sync_ticket_expiry ON topic_sync_pair_tickets(expires_at);
                CREATE TABLE IF NOT EXISTS topic_sync_devices (
                    device_id TEXT PRIMARY KEY,
                    learner_id TEXT NOT NULL REFERENCES access_principals(learner_id),
                    kb_id TEXT NOT NULL,
                    secret_digest TEXT NOT NULL,
                    identity_digest TEXT NOT NULL);
                CREATE INDEX IF NOT EXISTS topic_sync_kb_owner ON topic_sync_devices(kb_id, learner_id);
                CREATE TABLE IF NOT EXISTS topic_sync_open_tickets (
                    ticket_digest TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL REFERENCES topic_sync_devices(device_id),
                    topic_id TEXT NOT NULL,
                    identity_digest TEXT NOT NULL,
                    expires_at INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS topic_sync_open_expiry ON topic_sync_open_tickets(expires_at);
                CREATE TABLE IF NOT EXISTS topic_sync_bindings (
                    learner_id TEXT NOT NULL REFERENCES access_principals(learner_id),
                    kb_id TEXT NOT NULL,
                    topic_id TEXT NOT NULL,
                    rem_id TEXT NOT NULL,
                    PRIMARY KEY (learner_id, kb_id, topic_id),
                    UNIQUE (kb_id, rem_id));
                CREATE TABLE IF NOT EXISTS topic_sync_revisions (
                    learner_id TEXT NOT NULL REFERENCES access_principals(learner_id),
                    topic_id TEXT NOT NULL,
                    revision TEXT NOT NULL,
                    parent_revision TEXT,
                    snapshot TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    PRIMARY KEY (learner_id, topic_id, revision));
                CREATE TABLE IF NOT EXISTS topic_sync_heads (
                    learner_id TEXT NOT NULL,
                    topic_id TEXT NOT NULL,
                    revision TEXT NOT NULL,
                    PRIMARY KEY (learner_id, topic_id),
                    FOREIGN KEY (learner_id, topic_id, revision)
                        REFERENCES topic_sync_revisions (learner_id, topic_id, revision));
                """)

    def authorize_account(self, access, con=None):
        learner_id = _require_account(access)
        if con is None:
            with closing(self.access_store._connect()) as connection:
                return self.authorize_account(access, connection)
        if con.execute('SELECT 1 FROM topic_sync_exclusions WHERE learner_id=?', (learner_id,)).fetchone():
            raise DomainError('topic_sync_disabled', '当前账号未开放 Topic 与 RemNote 同步。', 403)
        return learner_id

    def set_excluded(self, learner_id, excluded):
        with self.access_store._transaction() as con:
            self.access_store._account(con, learner_id)
            if excluded:
                con.execute('INSERT OR IGNORE INTO topic_sync_exclusions VALUES (?)', (learner_id,))
            else:
                con.execute('DELETE FROM topic_sync_exclusions WHERE learner_id=?', (learner_id,))

    def issue_pair_ticket(self, access, identity_token):
        ticket = secrets.token_urlsafe(32)
        identity_digest = credential_digest('identity', identity_token)
        now = int(self.clock())
        with self.access_store._transaction() as con:
            learner_id = self.authorize_account(access, con)
            con.execute('DELETE FROM topic_sync_pair_tickets WHERE expires_at<=? OR identity_digest=?',
                        (now, identity_digest))
            con.execute('INSERT INTO topic_sync_pair_tickets VALUES (?, ?, ?, ?)',
                        (credential_digest('topic-sync-ticket', ticket), identity_digest, learner_id, now + PAIR_LIFETIME))
        return {'ticket': ticket, 'expires_in': PAIR_LIFETIME}

    def pair_device(self, ticket, device_id, device_secret, kb_id):
        now = int(self.clock())
        ticket_digest = credential_digest('topic-sync-ticket', ticket)
        secret_digest = credential_digest('topic-sync-device', device_secret)
        with self.access_store._transaction() as con:
            request = con.execute('SELECT * FROM topic_sync_pair_tickets WHERE ticket_digest=? AND expires_at>?',
                                  (ticket_digest, now)).fetchone()
            if not request:
                raise DomainError('topic_sync_ticket_expired', '配对请求已过期或用过，请返回网站重新配对。', 403)
            access = self.access_store.resolve_digest(request['identity_digest'])
            learner_id = self.authorize_account(access, con)
            self._require_kb_owner(con, kb_id, learner_id)
            current = self._find_device(con, device_id)
            if current:
                if not hmac.compare_digest(current['secret_digest'], secret_digest):
                    raise _device_missing()
                if current['learner_id'] != learner_id:
                    raise account_mismatch()
                if current['kb_id'] != kb_id:
                    raise DomainError('topic_sync_knowledge_base_mismatch', '请切换到本机原绑定的 RemNote 知识库。', 403)
                con.execute('UPDATE topic_sync_devices SET identity_digest=? WHERE device_id=?',
                            (request['identity_digest'], device_id))
            else:
                con.execute('INSERT INTO topic_sync_devices VALUES (?, ?, ?, ?, ?)',
                            (device_id, learner_id, kb_id, secret_digest, request['identity_digest']))
            con.execute('DELETE FROM topic_sync_pair_tickets WHERE ticket_digest=?', (ticket_digest,))
        return {'status': 'paired'}

    @staticmethod
    def _find_device(con, device_id):
        return con.execute('SELECT * FROM topic_sync_devices WHERE device_id=?', (device_id,)).fetchone()

    @staticmethod
    def _require_kb_owner(con, kb_id, learner_id):
        if con.execute('SELECT 1 FROM topic_sync_devices WHERE kb_id=? AND learner_id<>? LIMIT 1',
                       (kb_id, learner_id)).fetchone():
            raise account_mismatch()

    def browser_device(self, access, device_id):
        with closing(self.access_store._connect()) as con:
            learner_id = self.authorize_account(access, con)
            device = self._find_device(con, device_id)
            if not device:
                raise _device_missing()
            if device['learner_id'] != learner_id:
                raise account_mismatch()
            self._require_kb_owner(con, device['kb_id'], learner_id)
        return device

    def authenticate_device(self, authorization):
        scheme, sep, value = (authorization or '').partition(' ')
        device_id, dot, device_secret = value.partition('.')
        if scheme != 'TopicSync' or not sep or not dot or len(device_id) != 36 or not DEVICE_SECRET.fullmatch(device_secret):
            raise _device_missing()
        with closing(self.access_store._connect()) as con:
            device = self._find_device(con, device_id)
            if not device or not hmac.compare_digest(device['secret_digest'],
                                                      credential_digest('topic-sync-device', device_secret)):
                raise _device_missing()
            self._require_kb_owner(con, device['kb_id'], device['learner_id'])
        access = self.access_store.resolve_digest(device['identity_digest'])
        if self.authorize_account(access) != device['learner_id']:
            raise account_mismatch()
        return access, device

    def issue_open_ticket(self, access, device, topic_id, identity_token):
        ticket = secrets.token_urlsafe(32)
        now = int(self.clock())
        identity_digest = credential_digest('identity', identity_token)
        with self.access_store._transaction() as con:
            if self.authorize_account(access, con) != device['learner_id']:
                raise account_mismatch()
            self.binding(device, topic_id, con=con)
            con.execute('DELETE FROM topic_sync_open_tickets WHERE expires_at<=?', (now,))
            con.execute('INSERT INTO topic_sync_open_tickets VALUES (?, ?, ?, ?, ?)',
                        (credential_digest('topic-sync-open', ticket), device['device_id'], topic_id,
                         identity_digest, now + OPEN_LIFETIME))
        return {'ticket': ticket, 'expires_in': OPEN_LIFETIME}

    def consume_open_ticket(self, device, ticket, authorize_topic):
        digest = credential_digest('topic-sync-open', ticket)
        with self.access_store._transaction() as con:
            row = con.execute('''SELECT topic_id,identity_digest FROM topic_sync_open_tickets
                WHERE ticket_digest=? AND device_id=? AND expires_at>?''',
                (digest, device['device_id'], int(self.clock()))).fetchone()
            if not row:
                raise DomainError('topic_sync_open_expired', '跳转请求已过期或已使用，请从网站重新打开。', 403)
            access = self.access_store.resolve_digest(row['identity_digest'])
            if self.authorize_account(access, con) != device['learner_id']:
                raise account_mismatch()
            authorize_topic(access, row['topic_id'])
            binding = self.binding(device, row['topic_id'], con=con)
            con.execute('DELETE FROM topic_sync_open_tickets WHERE ticket_digest=?', (digest,))
        return binding

    def bind(self, device, topic_id, kb_id, rem_id):
        if device['kb_id'] != kb_id:
            raise DomainError('topic_sync_knowledge_base_mismatch', '请切换到本机原绑定的 RemNote 知识库。', 403)
        with self.access_store._transaction() as con:
            previous = self.binding(device, topic_id, required=False, con=con)
            if previous:
                if previous['rem_id'] == rem_id:
                    return previous
                raise DomainError('topic_sync_binding_conflict', '此 Topic 已绑定另一个 RemNote Document。', 409)
            try:
                con.execute('INSERT INTO topic_sync_bindings VALUES (?, ?, ?, ?)',
                            (device['learner_id'], kb_id, topic_id, rem_id))
            except sqlite3.IntegrityError:
                raise DomainError('topic_sync_binding_conflict', '此 RemNote Document 已绑定另一个 Topic。', 409) from None
        return {'topic_id': topic_id, 'kb_id': kb_id, 'rem_id': rem_id}

    def binding(self, device, topic_id, *, required=True, con=None):
        if con is None:
            with closing(self.access_store._connect()) as connection:
                return self.binding(device, topic_id, required=required, con=connection)
        row = con.execute('SELECT rem_id FROM topic_sync_bindings WHERE learner_id=? AND kb_id=? AND topic_id=?',
                          (device['learner_id'], device['kb_id'], topic_id)).fetchone()
        if row:
            return {'topic_id': topic_id, 'kb_id': device['kb_id'], 'rem_id': row['rem_id']}
        if required:
            raise _document_unbound()
        return None

    def bound_topic(self, device, kb_id, rem_id):
        if device['kb_id'] != kb_id:
            raise DomainError('topic_sync_knowledge_base_mismatch', '请切换到本机原绑定的 RemNote 知识库。', 403)
        with closing(self.access_store._connect()) as con:
            row = con.execute('SELECT topic_id FROM topic_sync_bindings WHERE learner_id=? AND kb_id=? AND rem_id=?',
                              (device['learner_id'], kb_id, rem_id)).fetchone()
        if not row:
            raise _document_unbound()
        return row['topic_id']

    @staticmethod
    def _head(con, learner_id, topic_id):
        return con.execute('''SELECT r.revision, r.snapshot FROM topic_sync_heads h
            JOIN topic_sync_revisions r USING (learner_id, topic_id, revision)
            WHERE h.learner_id=? AND h.topic_id=?''', (learner_id, topic_id)).fetchone()

    def _policy(self, con, learner_id, topic_id):
        return self.groups.topic_policy(con, learner_id, topic_id) if self.groups else (None, None, True)

    def read(self, access, topic_id):
        learner_id = self.authorize_account(access)
        with closing(self.access_store._connect()) as con:
            head = self._head(con, learner_id, topic_id)
            owner, baseline_revision, editable = self._policy(con, learner_id, topic_id)
            baseline = None
            if not head and baseline_revision:
                baseline = con.execute('''SELECT snapshot FROM topic_sync_revisions
                    WHERE learner_id=? AND topic_id=? AND revision=?''', (owner, topic_id, baseline_revision)).fetchone()
                if not baseline:
                    raise DomainError('topic_sync_baseline_missing', '所分配的基线暂不可用，请联系管理员。', 503)
        document = None
        if head or baseline:
            document = self.snapshots.load(('personal', learner_id if head else owner, topic_id),
                                           (head or baseline)['snapshot'])
        return {'revision': head['revision'] if head else None, 'document': document,
                'baseline_revision': baseline_revision, 'editable': editable}

    def write(self, access, topic_id, revision, expected_revision, document, *, expected_baseline_revision=None):
        learner_id = self.authorize_account(access)
        scope = ('personal', learner_id, topic_id)
        with closing(self.access_store._connect()) as con:
            if self._check_write(con, scope, revision, expected_revision, document, expected_baseline_revision):
                return {'revision': revision}
        snapshot = self.snapshots.save(scope, document)
        with self.access_store._transaction() as con:
            self.authorize_account(access, con)
            if not self._check_write(con, scope, revision, expected_revision, document, expected_baseline_revision):
                con.execute('INSERT INTO topic_sync_revisions VALUES (?, ?, ?, ?, ?, ?)',
                            (learner_id, topic_id, revision, expected_revision, snapshot, int(self.clock())))
                con.execute('''INSERT INTO topic_sync_heads VALUES (?, ?, ?)
                    ON CONFLICT(learner_id, topic_id) DO UPDATE SET revision=excluded.revision''',
                    (learner_id, topic_id, revision))
        return {'revision': revision}

    def _check_write(self, con, scope, revision, expected_revision, document, expected_baseline_revision):
        _, learner_id, topic_id = scope
        _, baseline_revision, editable = self._policy(con, learner_id, topic_id)
        if not editable:
            raise DomainError('topic_sync_edit_disabled', '管理员尚未开放此 Topic 的编辑权限。', 403)
        prior = con.execute('''SELECT parent_revision, snapshot FROM topic_sync_revisions
            WHERE learner_id=? AND topic_id=? AND revision=?''', (learner_id, topic_id, revision)).fetchone()
        if prior:
            if prior['parent_revision'] == expected_revision and prior['snapshot'] == self.snapshots.fingerprint(scope, document):
                return True
            raise DomainError('topic_sync_revision_reused', '此次保存标识已用于另一份正文。请重新保存。', 409)
        head = self._head(con, learner_id, topic_id)
        if (head['revision'] if head else None) != expected_revision:
            raise _stale_revision()
        if not head and baseline_revision != expected_baseline_revision:
            raise DomainError('topic_sync_baseline_changed', '当前基线已有变化，请重新打开正文后再保存。', 409)
        return False
