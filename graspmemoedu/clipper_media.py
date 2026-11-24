"""Media is committed in the same SQLite transaction as the confirmed learning item."""
import base64
import hashlib
import io
import json
from functools import lru_cache
from typing import Literal
from zipfile import ZipFile, ZIP_STORED

from pydantic import BaseModel, ConfigDict, Field

from .clipper_gateway import checked_png
from .clipper_settings import catalog
from .service import DomainError


class Attachment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    side: Literal['front', 'back']
    mime: Literal['image/png', 'audio/mpeg']
    hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    data: str = Field(max_length=45 * 1024 * 1024)


@lru_cache(maxsize=1)
def _mode_types():
    types = {}
    files = catalog()['rules']
    for name in ('modes.json', 'image-modes.json', 'excerpt-modes.json'):
        for item in json.loads(files[name])['modes']:
            types.setdefault(item['id'], item['name'])
    return {**types, 'excerpt-manual': '手动摘录', 'excerpt-cloze': '摘录挖空', 'image-excerpt': '原图摘录'}


def study_types(chat_types):
    return {**_mode_types(), **{key: value['label'] for key, value in chat_types.items()}}


def prepare(attachments):
    result, size = [], 0
    for item in attachments:
        raw = checked_png(item.data) if item.mime == 'image/png' else base64.b64decode(item.data, validate=True)
        if item.mime == 'audio/mpeg' and not (raw.startswith(b'ID3') or len(raw) > 2 and raw[0] == 255 and raw[1] & 224 == 224):
            raise ValueError
        size += len(raw)
        if size > 32 * 1024 * 1024 or hashlib.sha256(raw).hexdigest() != item.hash:
            raise ValueError
        result.append((item.side, item.hash, item.mime, raw))
    return result


def initialize(con):
    con.executescript("""
        CREATE TABLE IF NOT EXISTS clipper_media(
          learner_id TEXT NOT NULL, digest TEXT NOT NULL, mime TEXT NOT NULL, data BLOB NOT NULL,
          PRIMARY KEY(learner_id,digest));
        CREATE TABLE IF NOT EXISTS clipper_item_media(
          learner_id TEXT NOT NULL, item_id TEXT NOT NULL, ordinal INTEGER NOT NULL, side TEXT NOT NULL, digest TEXT NOT NULL,
          PRIMARY KEY(learner_id,item_id,ordinal));
    """)


def manifests(con, owner, items):
    result = {}
    for start in range(0, len(items), 500):
        batch = items[start:start + 500]
        placeholders = ','.join('?' for _ in batch)
        records = con.execute(f'''SELECT m.item_id,m.side,m.digest,b.mime FROM clipper_item_media m
            JOIN clipper_media b USING(learner_id,digest) WHERE m.learner_id=? AND m.item_id IN ({placeholders})
            ORDER BY m.item_id,m.ordinal''', (owner, *batch))
        for item, side, digest, mime in records:
            result.setdefault(item, []).append({'side': side, 'hash': digest, 'mime': mime})
    return result


def save(con, owner, item, attachments, new):
    if not new:
        if manifests(con, owner, [item]).get(item, []) != [{'side': side, 'hash': digest, 'mime': mime} for side,digest,mime,_ in attachments]:
            raise DomainError('clip_save_conflict', '附件与已保存的内容不同。', 409)
        return
    for ordinal, (side, digest, mime, data) in enumerate(attachments):
        con.execute('INSERT OR IGNORE INTO clipper_media VALUES(?,?,?,?)', (owner,digest,mime,data))
        con.execute('INSERT INTO clipper_item_media VALUES(?,?,?,?,?)', (owner,item,ordinal,side,digest))


def export(con, owner, rows, outline):
    entries, attached = [], {}
    assets = manifests(con, owner, [row['id'] for row in rows])
    for row in rows:
        names = {}
        for media in assets.get(row['id'], []):
            digest = media['hash']
            filename = 'media/' + digest + ('.png' if media['mime'] == 'image/png' else '.mp3')
            attached[digest] = filename
            names[digest] = filename
        entries.append({**dict(row), 'media': names})
    markdown = outline(entries) if rows else ''
    result = {'markdown': markdown, 'count': len(rows)}
    if attached:
        output = io.BytesIO()
        with ZipFile(output, 'w', ZIP_STORED) as archive:
            archive.writestr('摘录.md', markdown.encode())
            digests = list(attached)
            for start in range(0, len(digests), 500):
                batch = digests[start:start+500]
                placeholders = ','.join('?' for _ in batch)
                for digest, data in con.execute(f'SELECT digest,data FROM clipper_media WHERE learner_id=? AND digest IN ({placeholders})',
                                                (owner, *batch)):
                    archive.writestr(attached[digest], data)
        result['zip'] = base64.b64encode(output.getvalue()).decode()
    return result
