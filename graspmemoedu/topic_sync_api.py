"""Website and companion entry points for a paired learner's Topic documents."""

from typing import Annotated, Literal
from uuid import UUID
import hashlib
import json

from fastapi import Request
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .access import credential_digest
from .topic_sync import TopicSyncStore
from .topic_sync_groups import TopicSyncGroups
from .topic_sync_outline import official_outline
from .service import DomainError


BASE = '/api/topic-sync'
PAIR_TICKET = BASE + '/pair-ticket'
PAIR_DEVICE = BASE + '/pair-device'
DEVICE_STATE = BASE + '/device-state'
DEVICE_BINDING = BASE + '/device-binding'
DEVICE_RESOLVE = BASE + '/device-resolve'
DEVICE_OPEN = BASE + '/device-open'
DEVICE_HYPERSKILL = BASE + '/device-hyperskill'
DEVICE_BODY = BASE + '/device-body'
BODY = BASE + '/body'
BINDING = BASE + '/binding'
OPEN_TICKET = BASE + '/open-ticket'
GROUPS = BASE + '/groups'
GROUP_MEMBER = BASE + '/group-member'
DEVICE_PATHS = {PAIR_DEVICE, DEVICE_BINDING, DEVICE_RESOLVE, DEVICE_BODY, DEVICE_OPEN, DEVICE_HYPERSKILL}
PUBLIC_PATHS = DEVICE_PATHS | {PAIR_TICKET, DEVICE_STATE, BODY, BINDING, OPEN_TICKET, GROUPS, GROUP_MEMBER}
BODY_LIMITS = {path: 2 * 1024 * 1024 + 4096 for path in (BODY, DEVICE_BODY)}
BODY_LIMITS[GROUPS] = 256 * 1024

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


class OpenTicket(Payload):
    topic_id: TopicId
    device_id: UUID


class OpenDocument(Payload):
    ticket: PairSecret


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
    expected_baseline_revision: UUID | None = None
    expected_official_version: Annotated[str, Field(pattern=r'^[0-9a-f]{64}$')] | None = None
    document: Outline


class Group(Payload):
    group_id: UUID
    expected_revision: UUID | None
    revision: UUID
    course_id: TopicId
    name: str = Field(min_length=1, max_length=120, pattern=r'\S')
    editable: bool
    baselines: dict[TopicId, UUID] = Field(default_factory=dict, max_length=2500)


class GroupMember(Payload):
    learner_id: NativeId
    course_id: TopicId
    group_id: UUID | None
    expected_group_id: UUID | None


def register_topic_sync_routes(app, access_store, catalog, subjects, snapshots, limits):
    app.state.topic_sync = None
    if snapshots is None:
        return
    groups = TopicSyncGroups(access_store, catalog)
    store = TopicSyncStore(access_store, snapshots, groups=groups)
    app.state.topic_sync = store
    upstream_topics = {}
    for topic_id, topic in catalog.topics.items():
        source = topic.get('hyperskill')
        if topic.get('source_adapter') == 'hyperskill' and isinstance(source, dict):
            upstream_id = source.get('topic_id')
            if type(upstream_id) is int and upstream_id > 0:
                upstream_topics.setdefault(str(upstream_id), []).append(topic_id)

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

    def course_body(topic_id):
        document = official_outline(catalog.topic(topic_id), access_store.data_dir)
        digest = hashlib.sha256(json.dumps(document, ensure_ascii=False, separators=(',', ':'),
                                            sort_keys=True).encode()).hexdigest()
        return document, digest

    def read_body(access, topic_id):
        state = store.read(access, topic_id)
        state['official_version'] = None
        if state['document'] is None:
            state['document'], state['official_version'] = course_body(topic_id)
        return state

    def write_body(access, payload):
        if payload.expected_official_version and not payload.expected_revision and not payload.expected_baseline_revision:
            if payload.expected_official_version != course_body(payload.topic_id)[1]:
                raise DomainError('topic_sync_baseline_changed', '课程底本已更新，请重新打开正文。', 409)
        return store.write(access, payload.topic_id, str(payload.revision),
                           str(payload.expected_revision) if payload.expected_revision else None,
                           payload.document.model_dump(mode='json'),
                           expected_baseline_revision=str(payload.expected_baseline_revision)
                           if payload.expected_baseline_revision else None)

    @app.get(GROUPS)
    def course_groups(request: Request):
        access, _, _ = browser_access(request)
        return {'groups': groups.list(access)}

    @app.post(GROUPS)
    def save_course_group(payload: Group, request: Request):
        access, _, _ = browser_access(request)
        settings = payload.model_dump(mode='json', exclude={'baselines'})
        settings['name'] = settings['name'].strip()
        return groups.save_group(access, **settings, chosen={topic: str(revision)
                                 for topic, revision in payload.baselines.items()})

    @app.get(GROUP_MEMBER)
    def course_group_member(request: Request, learner_id: NativeId, course_id: TopicId):
        access, _, _ = browser_access(request)
        return {'membership': groups.membership(access, learner_id, course_id)}

    @app.post(GROUP_MEMBER)
    def save_course_group_member(payload: GroupMember, request: Request):
        access, _, _ = browser_access(request)
        return groups.set_membership(access, **payload.model_dump(mode='json'))

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
        _, device, identity = browser_access(request, device_id)
        return {'status': 'paired' if device else 'unpaired',
                'editor': app.state.topic_editor_enabled,
                'reauthorize': bool(device and device['identity_digest'] != credential_digest('identity', identity))}

    @app.post(DEVICE_BINDING)
    def bind(payload: Binding, request: Request):
        access, device = device_access(request)
        topic_for(access, payload.topic_id)
        return store.bind(device, payload.topic_id, payload.kb_id, payload.rem_id)

    @app.get(DEVICE_HYPERSKILL)
    def hyperskill_candidates(request: Request):
        access, _ = device_access(request)
        granted = {topic['id'] for topic in access['topics']}
        return {'topics': {source: matches[0] for source, matches in upstream_topics.items()
                           if len(matches) == 1 and matches[0] in granted}}

    @app.get(DEVICE_RESOLVE)
    def resolve_document(request: Request, kb_id: NativeId, rem_id: NativeId):
        access, device = device_access(request)
        topic_id = store.bound_topic(device, kb_id, rem_id)
        subject_id = topic_for(access, topic_id)
        return {'topic_id': topic_id, 'subject_id': subject_id}

    @app.get(BINDING)
    def resolve_topic(request: Request, topic_id: TopicId, device_id: UUID):
        access, device, _ = browser_access(request, device_id)
        subject_id = topic_for(access, topic_id)
        return {**store.binding(device, topic_id), 'subject_id': subject_id}

    @app.post(OPEN_TICKET)
    def prepare_open(payload: OpenTicket, request: Request):
        access, device, identity = browser_access(request, payload.device_id)
        topic_for(access, payload.topic_id)
        limits.consume(('topic-sync-open', access['learner_id']), 60)
        return store.issue_open_ticket(access, device, payload.topic_id, identity)

    @app.post(DEVICE_OPEN)
    def open_document(payload: OpenDocument, request: Request):
        _, device = device_access(request)
        return store.consume_open_ticket(device, payload.ticket, topic_for)

    @app.get(BODY)
    def website_body(request: Request, topic_id: TopicId, device_id: UUID | None = None):
        access, _, _ = browser_access(request, device_id)
        topic_for(access, topic_id)
        return read_body(access, topic_id)

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
        return read_body(access, topic_id)

    @app.post(DEVICE_BODY)
    def save_companion_body(payload: Write, request: Request):
        access, device = device_access(request)
        topic_for(access, payload.topic_id)
        store.binding(device, payload.topic_id)
        limits.consume(('topic-sync-write', access['learner_id']), 30)
        return write_body(access, payload)
