"""Reuse authorized presentation text while always returning fresh learning state.

Clients opt in with content_revision. The normal endpoint and its authorization
still run on every request; there is no content-by-hash endpoint. A bounded
index of fingerprints (never course text) also reuses unchanged blocks on edits.
Old clients keep the original JSON contract.
"""
import hashlib
import json
import re
from collections import OrderedDict
from threading import Lock

from fastapi.responses import JSONResponse, Response

REVISION = re.compile(r"(?:1|[a-f0-9]{64})\Z")
PATHS = {
    "/api/state", "/api/guide", "/api/training/group", "/api/training/state",
    "/api/materials/content",
}
MUTATIONS = {"/api/" + action for action in ("choose", "continue", "select", "reveal", "skip", "submit")}
_revisions = OrderedDict()
_lock = Lock()
READ_PATHS = PATHS | {"/api/access", "/api/subjects", "/api/profile", "/api/catalog",
                     "/api/graphs", "/api/training/catalog", "/api/training/bank"}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def compact_access(value, known):
    """Only omit an access projection after the endpoint has authorized this read."""
    if isinstance(value, list):
        return [compact_access(item, known) for item in value]
    if not isinstance(value, dict):
        return value
    if {"learner_id", "role", "features", "topics"} <= value.keys():
        revision = digest(value)
        return ({"$gme_access": revision} if revision == known else
                {**value, "access_revision": revision})
    return {key: compact_access(item, known) for key, item in value.items()}


def read_fingerprint(value):
    """Clocks still travel on unchanged reads; all authorization/content/state counts."""
    clocks = []

    def visit(item, path=()):
        if isinstance(item, list):
            return [visit(child, (*path, index)) for index, child in enumerate(item)]
        if not isinstance(item, dict):
            return item
        if "access_revision" in item:
            return {"$gme_access": item["access_revision"]}
        result = {}
        for key, child in item.items():
            if key == "server_time":
                clocks.append([list((*path, key)), child])
            else:
                result[key] = visit(child, (*path, key))
        return result

    return digest(visit(value)), clocks


def text_delta(texts, revision, known):
    fingerprints = tuple(hashlib.sha256(text.encode()).digest() for text in texts)
    with _lock:
        previous = _revisions.get(known, ())
        _revisions[revision] = fingerprints
        _revisions.move_to_end(revision)
        while len(_revisions) > 128 or sum(map(len, _revisions.values())) > 8192:
            _revisions.popitem(last=False)
    if known == revision:
        return None
    positions = {digest: index for index, digest in enumerate(previous)}
    return [{"$gme_previous": positions[digest]} if digest in positions else text
            for digest, text in zip(fingerprints, texts)]


def eligible(path, method):
    if method == "POST":
        return path in MUTATIONS or bool(re.fullmatch(
            r"/api/review/(?:begin|sessions/[^/]+/(?:continue|reveal|submit))", path))
    return method == "GET" and (path in PATHS or bool(re.fullmatch(
        r"/api/(?:tasks/[^/]+/answers|submissions/[^/]+|review/(?:sessions|submissions)/[^/]+)", path)))


def pack_content(value, known):
    texts, positions = [], {}

    def visit(item, key=""):
        if isinstance(item, str) and (key == "html" or key.endswith("_html") or key == "math_css"):
            if len(item) < 128:
                return item
            if item not in positions:
                positions[item] = len(texts)
                texts.append(item)
            return {"$gme_text": positions[item]}
        if isinstance(item, dict):
            return {name: visit(child, name) for name, child in item.items()}
        if isinstance(item, list):
            return [visit(child) for child in item]
        return item

    state = visit(value)
    if not texts:
        return value
    encoded = json.dumps(texts, ensure_ascii=False, separators=(",", ":")).encode()
    revision = hashlib.sha256(encoded).hexdigest()
    return {"$gme_content": 1, "state": state, "revision": revision,
            "texts": text_delta(texts, revision, known)}


def compact_options(request):
    known = request.query_params.get("content_revision", "")
    access_known = request.query_params.get("access_revision", "")
    state_known = request.query_params.get("state_revision", "")
    content_opt = eligible(request.url.path, request.method) and REVISION.fullmatch(known)
    access_opt = request.url.path.startswith("/api/") and REVISION.fullmatch(access_known)
    state_opt = (request.method == "GET" and REVISION.fullmatch(state_known)
                 and (request.url.path in READ_PATHS or eligible(request.url.path, "GET")))
    return (known if content_opt else None, access_known if access_opt else None, state_known if state_opt else None)


def compact_value(value, known, access_known, state_known):
    if access_known:
        value = compact_access(value, access_known)
    if state_known:
        revision, clocks = read_fingerprint(value)
        if revision == state_known:
            return {"$gme_state": 1, "revision": revision, "clocks": clocks}
    if known:
        value = pack_content(value, known)
    if state_known:
        value = {"$gme_state": 1, "revision": revision, "value": value}
    return value


def learning_response(request, value):
    # These projections already contain JSON data. Compact the authorized
    # view before encoding, on the same request worker as the projection.
    try:
        response = JSONResponse(compact_value(value, *compact_options(request)))
    except (ValueError, TypeError, RecursionError):
        return value
    request.state.learning_response_encoded = True
    return response


async def compact_response(request, response):
    if getattr(request.state, "learning_response_encoded", False):
        return response
    options = compact_options(request)
    if (not any(options) or response.status_code != 200
            or "application/json" not in response.headers.get("content-type", "")
            or response.headers.get("content-encoding")):
        return response
    body = b"".join([part async for part in response.body_iterator])
    try:
        result = compact_value(json.loads(body), *options)
        body = json.dumps(result, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    except (ValueError, TypeError, RecursionError):
        # A representation optimization must not turn a valid response into an error.
        pass
    headers = dict(response.headers)
    headers.pop("content-length", None)
    return Response(body, status_code=response.status_code, headers=headers,
                    background=response.background)
