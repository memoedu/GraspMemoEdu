"""Short-lived, exercise-scoped delegation from the web identity to the IDE."""
from contextlib import closing
from datetime import datetime, timedelta, timezone
import hashlib
import secrets

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field

from .access import credential_digest
from .academy import AcademyLearningService
from .academy_training import AcademyTraining
from .hyperskill_training import external_training
from .training_api import AttemptAction
from .training_content import permission_id
from .service import DomainError

CAPABILITY_PATHS = {'/api/academy/claim', '/api/academy/event'}
PUBLIC_PATHS = CAPABILITY_PATHS | {'/api/academy/launch', '/api/academy/finish',
                                 '/api/academy/training/launch', '/api/academy/training/finish'}


class Finish(BaseModel):
    model_config = ConfigDict(extra='forbid')
    request_id: str
    expected_revision: int
    attempt_id: str
    step_id: str
    rating: int | None = None


class Event(BaseModel):
    model_config = ConfigDict(extra='forbid')
    kind: str
    event: dict | None = None


def uses_idea_plugin(backend):
    if isinstance(backend, AcademyTraining):
        return backend.provider == 'academy' or getattr(backend, 'native_ide', False)
    return backend.course.get('source_adapter') != 'hyperskill'


def record_idea_connection(con, learner, at):
    con.execute('''INSERT INTO academy_idea_setup (learner, connected_at) VALUES (?,?)
        ON CONFLICT(learner) DO UPDATE SET connected_at=excluded.connected_at
        WHERE academy_idea_setup.connected_at IS NULL''', (learner, at))


def offer_idea_setup(access_store, access, at, *, already_open):
    if access['role'] != 'account':
        return False
    learner = access['learner_id']
    with access_store._transaction() as con:
        saved = con.execute('SELECT connected_at FROM academy_idea_setup WHERE learner=?', (learner,)).fetchone()
        if saved and (saved['connected_at'] or not already_open):
            return False
        # Older native bank rounds also prove the plugin opened a task. The
        # official Hyperskill relay sends "opened" before it contacts IDEA.
        prior = already_open or con.execute('''SELECT 1 FROM training_attempts a
            JOIN training_external_rounds r ON r.attempt=a.id WHERE a.learner=?
            AND json_extract(r.body, '$.opened_at') IS NOT NULL
            AND (json_type(a.snapshot, '$.academy')='object' OR json_type(r.body, '$.code_judge')='object')
            LIMIT 1''', (learner,)).fetchone()
        if prior:
            record_idea_connection(con, learner, at)
            return False
        con.execute('INSERT INTO academy_idea_setup (learner, guided_at) VALUES (?,?)', (learner, at))
        return True


def register_academy_routes(app, settings, access_store, service_for, identity, public_state, Action, dependencies, clock=None):
    now = clock or (lambda: datetime.now(timezone.utc))
    with closing(access_store._connect()) as con:
        con.execute('''CREATE TABLE IF NOT EXISTS academy_capabilities (
            digest TEXT PRIMARY KEY, identity_digest TEXT NOT NULL, preview_scope TEXT NOT NULL,
            learner TEXT NOT NULL, topic TEXT NOT NULL, version TEXT NOT NULL,
            step TEXT NOT NULL, round TEXT NOT NULL, expires TEXT NOT NULL, claimed INTEGER NOT NULL DEFAULT 0)''')
        con.execute('''CREATE TABLE IF NOT EXISTS academy_idea_setup (
            learner TEXT PRIMARY KEY REFERENCES access_principals(learner_id),
            guided_at TEXT, connected_at TEXT)''')
        con.commit()

    def require_service(backend):
        if not isinstance(backend, AcademyLearningService):
            raise DomainError('not_academy', '本题未绑定 JetBrains Academy。', 422)

    def capability(request, *, claim=False):
        auth = request.headers.get('authorization', '')
        if not auth.startswith('Bearer ') or not 40 <= len(auth) <= 150:
            raise DomainError('invalid_academy_ticket', 'IDEA 连接授权无效，请从网页重新打开。', 401)
        digest = hashlib.sha256(auth[7:].encode()).hexdigest()
        with closing(access_store._connect()) as con:
            row = con.execute('SELECT * FROM academy_capabilities WHERE digest=?', (digest,)).fetchone()
        if not row or row['expires'] < now().isoformat() or not claim and not row['claimed']:
            raise DomainError('expired_academy_ticket', 'IDEA 连接授权已到期，请从网页重新打开。', 401)
        access = access_store.resolve_digest(row['identity_digest'])
        access_store.authorize(access, row['topic'], 'submit_answer')
        if row['topic'].startswith('training.'):
            backend = external_training(app.state.training_backend_for(access, row['preview_scope']), row['step'])
            if (access['learner_id'] != row['learner'] or backend.version != row['version']
                    or permission_id(backend.bank_id) != row['topic']):
                raise DomainError('stale_academy_ticket', '题库已更新，请从网页重新打开。', 409)
            with closing(backend.training._connect()) as con:
                attempt = backend.training._attempt(con, row['step'])
                backend.training.require_group(backend.bank_id, attempt['group_id'], con=con)
            return row, backend
        if row['topic'] in app.state.training_catalog.topic_redirects:
            raise DomainError('stale_academy_ticket', '本题已移入题库，请从题库重新打开。', 409)
        dependencies.require(access, row['topic'])
        backend = service_for(access['learner_id'], row['topic'], scope_digest=row['preview_scope'])
        require_service(backend)
        if access['learner_id'] != row['learner'] or backend.course['version'] != row['version']:
            raise DomainError('stale_academy_ticket', '课程已更新，请从网页重新打开。', 409)
        return row, backend

    def grant(request, access, container, run):
        token = secrets.token_urlsafe(32)
        identity_token = request.headers.get('x-learning-identity')
        with closing(access_store._connect()) as con:
            con.execute('DELETE FROM academy_capabilities WHERE expires<?', (now().isoformat(),))
            con.execute('INSERT INTO academy_capabilities VALUES (?,?,?,?,?,?,?,?,?,0)',
                        (hashlib.sha256(token.encode()).hexdigest(), credential_digest('identity', identity_token),
                         credential_digest('preview', identity_token), access['learner_id'], container,
                         run['version'], run['step_id'], run['round_id'], (now() + timedelta(minutes=10)).isoformat()))
            con.commit()
        return token

    @app.post('/api/academy/training/launch')
    def training_launch(payload: AttemptAction, request: Request, guide: bool = False):
        access, training = app.state.training_attempt_context(request, payload.attempt_id, 'submit_answer')
        backend = external_training(training, payload.attempt_id)
        run = backend.launch()
        state = app.state.training_public_state(request, access, training, payload.attempt_id)
        native = uses_idea_plugin(backend)
        binding = state.get('academy') or (state.get('hyperskill') or {}).get('local_ide') or {}
        if guide and native and offer_idea_setup(access_store, access, now().isoformat(),
                                                 already_open=bool(binding.get('opened'))):
            return {'setup_required': True, 'state': state}
        token = grant(request, access, permission_id(backend.bank_id), run)
        return {**({'url': 'graspmemoedu://academy/open?ticket=' + token} if native else {'ticket': token}),
                'state': state}

    class TrainingFinish(AttemptAction):
        rating: int | None = Field(default=None, strict=True, ge=1, le=4)

    @app.post('/api/academy/training/finish')
    def training_finish(payload: TrainingFinish, request: Request):
        access, training = app.state.training_attempt_context(request, payload.attempt_id, 'submit_answer')
        external_training(training, payload.attempt_id).finish(payload.rating)
        return app.state.training_public_state(request, access, training, payload.attempt_id)

    @app.post('/api/academy/launch')
    def launch(payload: Action, request: Request, guide: bool = False):
        access, backend = identity(request, 'submit_answer')
        require_service(backend)
        dependencies.require(access, backend.topic_id)
        run = backend.launch(payload.model_dump())
        result = {'state': public_state(backend.state(), access, backend)}
        native = uses_idea_plugin(backend)
        binding = (result['state'].get('current') or {}).get('academy') or {}
        if guide and native and offer_idea_setup(access_store, access, now().isoformat(),
                                                 already_open=bool(binding.get('opened'))):
            return {**result, 'setup_required': True}
        token = grant(request, access, backend.topic_id, run)
        if native:
            result['url'] = 'graspmemoedu://academy/open?ticket=' + token
        else:
            result['ticket'] = token
        return result

    @app.post('/api/academy/claim')
    def claim(request: Request):
        row, backend = capability(request, claim=True)
        if isinstance(backend, AcademyTraining):
            binding = backend.claim(row['round'])
        else:
            with closing(backend._connect()) as con:
                state = backend._load(con)
                run = backend._run(state, row['round'], row['step'])
                if state['phase'] != 'answer':
                    raise DomainError('academy_round_closed', '此轮已经完成，请回到网页继续。', 409)
            binding = {**backend.binding(state['active']), 'version': backend.course['version'], 'round_id': row['round'],
                       'next_sequence': len(run['events']) + 1, 'mode': state['mode'], 'reset_policy': 'archive_then_template'}
        with closing(access_store._connect()) as con:
            con.execute('UPDATE academy_capabilities SET claimed=1,expires=? WHERE digest=? AND claimed=0',
                        ((now() + timedelta(days=7)).isoformat(), row['digest']))
            con.commit()
        return binding

    @app.post('/api/academy/event')
    def event(payload: Event, request: Request):
        row, backend = capability(request)
        if payload.kind == 'opened' and payload.event is None:
            result = backend.opened(row['round'], row['step'])
            if uses_idea_plugin(backend):
                with access_store._transaction() as con:
                    if con.execute("SELECT 1 FROM access_principals WHERE learner_id=? AND role='account'",
                                   (row['learner'],)).fetchone():
                        record_idea_connection(con, row['learner'], now().isoformat())
            return result
        if payload.kind == 'check' and payload.event is not None:
            return backend.check_event(row['round'], row['step'], payload.event)
        raise DomainError('invalid_academy_event', '未知的 IDEA 回传类型。', 422)

    @app.post('/api/academy/finish')
    def finish(payload: Finish, request: Request):
        access, backend = identity(request, 'submit_answer')
        require_service(backend)
        dependencies.require(access, backend.topic_id)
        return public_state(backend.finish(payload.model_dump(exclude_none=True)), access, backend)
