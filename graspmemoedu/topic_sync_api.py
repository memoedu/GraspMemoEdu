"""Website and companion entry points for a paired learner's Topic documents."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .topic_sync import TopicSyncStore


BASE = '/api/topic-sync'
PAIR_TICKET = BASE + '/pair-ticket'
PAIR_DEVICE = BASE + '/pair-device'
DEVICE_STATE = BASE + '/device-state'
DEVICE_BINDING = BASE + '/device-binding'
DEVICE_RESOLVE = BASE + '/device-resolve'
DEVICE_BODY = BASE + '/device-body'
BODY = BASE + '/body'
BINDING = BASE + '/binding'
DEVICE_PATHS = {PAIR_DEVICE, DEVICE_BINDING, DEVICE_RESOLVE, DEVICE_BODY}
PUBLIC_PATHS = DEVICE_PATHS | {PAIR_TICKET, DEVICE_STATE, BODY, BINDING}
BODY_LIMITS = {path: 2 * 1024 * 1024 + 4096 for path in (BODY, DEVICE_BODY)}

NativeId = Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{1,120}$')]
TopicId = Annotated[str, Field(pattern=r'^[A-Za-z0-9_.-]{1,180}$')]
PairSecret = Annotated[str, Field(pattern=r'^[A-Za-z0-9_-]{43}$')]


class Payload(BaseModel):
    model_config = ConfigDict(extra='forbid')


class PairDevice(Payload):
    ticket: PairSecret
    device_id: UUID
    device_secret: PairSecret
    kb_id: NativeId


class Binding(Payload):
    topic_id: TopicId
    kb_id: NativeId
    rem_id: NativeId


class Block(Payload):
    id: NativeId
    parent_id: NativeId | None = None
    kind: Literal['bullet', 'numbered', 'heading', 'code', 'quote', 'formula'] = 'bullet'
    text: str = Field(max_length=100000)


class Outline(Payload):
    format: Literal['topic-outline-v1'] = 'topic-outline-v1'
    title: str = Field(min_length=1, max_length=500)
    blocks: list[Block] = Field(max_length=12000)

    @model_validator(mode='after')
    def valid_tree(self):
        seen = set()
        for block in self.blocks:
            if block.id in seen or block.parent_id is not None and block.parent_id not in seen:
                raise ValueError('Each node must follow its parent and appear once')
            seen.add(block.id)
        return self


class Write(Payload):
    topic_id: TopicId
    revision: UUID
    expected_revision: UUID | None
    document: Outline


def register_topic_sync_routes(app, access_store, catalog, subjects, snapshots, limits):
    store = TopicSyncStore(access_store, snapshots) if snapshots is not None else None
    app.state.topic_sync = store
    if store is None:
        return

    def browser_access(request, device_id=None):
        identity = request.headers.get('x-learning-identity')
        access = access_store.resolve(identity)
        store.authorize_account(access)
        device = store.browser_device(access, str(device_id)) if device_id is not None else None
        return access, device, identity

    def device_access(request):
        return request.state.topic_sync_device

    def topic_for(access, topic_id):
        topic = catalog.topic(topic_id)
        subject_id = topic.get('subject_id') or min(subjects.course_subjects[course]
                                                    for course in catalog.topic_courses[topic_id])
        subjects.authorize_subject(access, subject_id)
        access_store.authorize(access, topic_id)
        return subject_id

    def write_body(access, payload):
        return store.write(access, payload.topic_id, str(payload.revision),
                               str(payload.expected_revision) if payload.expected_revision else None,
                               payload.document.model_dump(mode='json'))

    @app.post(PAIR_TICKET)
    def pair_ticket(request: Request):
        access, _, identity = browser_access(request)
        limits.consume(('topic-sync-pair', access['learner_id']), 8)
        return store.issue_pair_ticket(access, identity)

    @app.post(PAIR_DEVICE)
    def pair_device(payload: PairDevice, request: Request):
        host = request.client.host if request.client else ''
        limits.consume(('topic-sync-companion', host), 90)
        return store.pair_device(payload.ticket, str(payload.device_id), payload.device_secret, payload.kb_id)

    @app.get(DEVICE_STATE)
    def device_state(request: Request, device_id: UUID | None = None):
        _, device, _ = browser_access(request, device_id)
        return {'status': 'paired' if device else 'unpaired'}

    @app.post(DEVICE_BINDING)
    def bind(payload: Binding, request: Request):
        access, device = device_access(request)
        topic_for(access, payload.topic_id)
        return store.bind(device, payload.topic_id, payload.kb_id, payload.rem_id)

    @app.get(DEVICE_RESOLVE)
    def resolve_document(request: Request, kb_id: NativeId, rem_id: NativeId):
        access, device = device_access(request)
        topic_id = store.bound_topic(device, kb_id, rem_id)
        subject_id = topic_for(access, topic_id)
        return {'topic_id': topic_id, 'subject_id': subject_id}

    @app.get(BINDING)
    def resolve_topic(request: Request, topic_id: TopicId, device_id: UUID):
        access, device, _ = browser_access(request, device_id)
        topic_for(access, topic_id)
        return store.binding(device, topic_id)

    @app.get(BODY)
    def website_body(request: Request, topic_id: TopicId, device_id: UUID | None = None):
        access, _, _ = browser_access(request, device_id)
        topic_for(access, topic_id)
        return store.read(access, topic_id)

    @app.post(BODY)
    def save_website_body(payload: Write, request: Request, device_id: UUID | None = None):
        access, _, _ = browser_access(request, device_id)
        topic_for(access, payload.topic_id)
        limits.consume(('topic-sync-write', access['learner_id']), 30)
        return write_body(access, payload)

    @app.get(DEVICE_BODY)
    def companion_body(request: Request, topic_id: TopicId):
        access, device = device_access(request)
        topic_for(access, topic_id)
        store.binding(device, topic_id)
        return store.read(access, topic_id)

    @app.post(DEVICE_BODY)
    def save_companion_body(payload: Write, request: Request):
        access, device = device_access(request)
        topic_for(access, payload.topic_id)
        store.binding(device, payload.topic_id)
        limits.consume(('topic-sync-write', access['learner_id']), 30)
        return write_body(access, payload)
