"""Activate source-bound Math Academy display files using the content generation pointer."""
import argparse
from collections import Counter
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import shutil
import uuid

from .catalog import Catalog
from .config import Settings
from .content_bundle import POINTER
from .lesson_display import DIRECTORY, display_key, lesson_fields, read_display
from .question_bank import QuestionBank
from .test_materials import TestMaterials
from .topic_install import digest, encoded, import_lock


class MarkupSignature(HTMLParser):
    """Bind translated HTML to the renderer's tags, attributes and protected nodes."""

    PROTECTED = {'code', 'pre', 'svg', 'math', 'mjx-container'}

    def __init__(self, source):
        super().__init__()
        self.tags, self.protected, self.open = Counter(), Counter(), []
        self.feed(source)
        self.close()
        if self.open:
            raise ValueError('Unclosed protected HTML')

    def record(self, item):
        self.tags[item] += 1
        for _, nodes in self.open:
            nodes.append(item)

    def handle_starttag(self, tag, attrs):
        item = ('start', tag, tuple(sorted(attrs, key=lambda pair: pair[0])))
        self.record(item)
        if tag in self.PROTECTED or 'data-tex' in dict(attrs):
            self.open.append((tag, [item]))

    def handle_startendtag(self, tag, attrs):
        if tag in self.PROTECTED or 'data-tex' in dict(attrs):
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)
        else:
            self.record(('start', tag, tuple(sorted(attrs, key=lambda pair: pair[0]))))

    def handle_endtag(self, tag):
        self.record(('end', tag))
        if self.open and self.open[-1][0] == tag:
            self.protected[tuple(self.open.pop()[1])] += 1

    def handle_data(self, value):
        for _, nodes in self.open:
            nodes.append(value)

    def handle_comment(self, content):
        self.record(('comment', content))

    def handle_decl(self, content):
        self.record(('declaration', content))

    def handle_pi(self, content):
        self.record(('instruction', content))

    def signature(self):
        return self.tags, self.protected


def link_or_copy(source, destination):
    try:
        return os.link(source, destination)
    except OSError:
        return shutil.copy2(source, destination)


def verify_topic(path, tid, catalog, data):
    topic = catalog.topics[tid]
    spec = read_display(path)
    if set(spec) != {'schema', 'topic_id', 'version', 'values'} or spec['topic_id'] != tid or spec['version'] != topic['version']:
        raise ValueError(f'Localized Topic version differs: {tid}')
    bank = QuestionBank(topic, data)
    active = bank.active_revision()
    variants = [bank.question(qid, active) for qid in bank.load(active)['questions']] if active else []
    source = {display_key(kind, row[name]): (kind, row[name]) for row, name, kind in lesson_fields(topic, variants)}
    if not isinstance(spec['values'], dict) or not spec['values'] or not spec['values'].keys() <= source.keys():
        raise ValueError(f'Localization contains invalid source bindings: {tid}')
    for key, value in spec['values'].items():
        if not isinstance(value, str) or not value.strip() or '\x00' in value or len(value) > 2_000_000:
            raise ValueError(f'Invalid lesson display value: {tid}')
        kind, original = source[key]
        if kind == 'title' and ('<' in value or '>' in value):
            raise ValueError(f'Expected plain text: {tid}')
        if kind == 'html' and MarkupSignature(value).signature() != MarkupSignature(original).signature():
            raise ValueError(f'Changed protected HTML: {tid}/{key}')


def install(package, data):
    package, data = Path(package).resolve(), Path(data).resolve()
    raw = (package / 'manifest.json').read_bytes()
    manifest = json.loads(raw)
    if set(manifest) != {'schema', 'courses', 'files'} or manifest['schema'] != 1 or not manifest['files']:
        raise ValueError('Invalid lesson display manifest')
    if (data / 'cloud-authoritative.json').exists():
        raise ValueError('The local rollback snapshot cannot receive releases')
    with import_lock(data):
        settings = Settings.load(data)
        root = settings.content_dir
        pointer = data / POINTER
        previous = pointer.read_bytes()
        catalog = Catalog.load(settings)
        policy = TestMaterials(data, catalog)
        selected = {row['id'] for cid in manifest['courses'] for row in catalog.course(cid)['topics']}
        allowed = {tid for tid in selected & policy.topics if catalog.topics[tid].get('source_adapter') == 'mathacademy'}
        for name, checksum in manifest['files'].items():
            path = package / name
            if (not re.fullmatch(r'(?:preview|ma-topic-\d+)\.json', name) or path.is_symlink()
                    or digest(path.read_bytes()) != checksum):
                raise ValueError('Unexpected lesson display package member')
            if name == 'preview.json':
                config = read_display(path)
                if (set(config) != {'schema', 'topics'} or not config['topics'].keys() <= allowed
                        or any(catalog.topics[tid]['version'] != version for tid, version in config['topics'].items())):
                    raise ValueError('Practice preview exceeds the explicit course and content versions')
            else:
                if path.stem not in allowed:
                    raise ValueError('Localized Topic exceeds the explicit course scope')
                verify_topic(path, path.stem, catalog, data)
        if all((root / DIRECTORY / name).is_file() and digest((root / DIRECTORY / name).read_bytes()) == checksum
               for name, checksum in manifest['files'].items()):
            return {'status': 'unchanged', 'generation': json.loads(previous)['generation']}
        generation = digest(previous + raw + uuid.uuid4().bytes)
        batch = data / 'content-batches' / generation
        shutil.copytree(root, batch, copy_function=link_or_copy)
        target = batch / DIRECTORY
        target.mkdir(parents=True, exist_ok=True)
        for name in manifest['files']:
            staged = target / ('.' + name)
            shutil.copyfile(package / name, staged)
            os.replace(staged, target / name)
        readback = {name: digest((target / name).read_bytes()) for name in manifest['files']}
        if readback != manifest['files'] or pointer.read_bytes() != previous:
            raise ValueError('Staged bytes or active generation changed')
        history = data / 'content-activation-history'
        history.mkdir(exist_ok=True)
        (history / (generation + '.json')).write_bytes(encoded({'previous': json.loads(previous), 'generation': generation,
                                                                'kind': 'mathacademy-lesson-display'}))
        pending = pointer.with_name('.lesson-display-' + generation)
        with pending.open('xb') as stream:
            stream.write(encoded({'schema': 1, 'generation': generation}))
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(pending, pointer)
        return {'status': 'installed', 'generation': generation, 'topics': len(manifest['files']) - ('preview.json' in manifest['files'])}


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument('--package', required=True, type=Path)
    cli.add_argument('--data-dir', required=True, type=Path)
    args = cli.parse_args()
    print(json.dumps(install(args.package, args.data_dir), ensure_ascii=False))
