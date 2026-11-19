"""Prepare an additive Practice step for a previously installed Hyperskill course."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from graspmemoedu.hyperskill_import import validate_practice_binding, with_practice_group
from graspmemoedu.topic_install import encoded
from graspmemoedu.training_content import validate


def prepare(source, output, course_id):
    source = source.resolve(strict=True)
    original_manifest = json.loads((source / 'manifest.json').read_bytes())
    if original_manifest.get('adapter') != 'hyperskill' or original_manifest.get('topic_format_version') != 2:
        raise ValueError('Expected a frozen Hyperskill Topic v2 package')

    def load(name):
        path = (source / name).resolve(strict=True)
        if not path.is_relative_to(source):
            raise ValueError('Source path leaves its immutable package')
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != original_manifest['files'].get(name):
            raise ValueError(f'Source hash differs: {name}')
        return json.loads(data)

    bank = validate(load('training-banks/hyperskill-practice.json'))
    course = next(c for c in load('catalog.json')['courses'] if c['id'] == course_id)
    topics = {}
    for entry in course['topics']:
        topic = load(entry['path'])
        if topic['id'] != entry['id']:
            raise ValueError('Source Topic differs from the course catalog')
        revised = with_practice_group(topic)
        validate_practice_binding(revised, bank)
        entry['path'] = f"topics/{topic['id']}.json"
        topics[entry['path']] = revised

    output.mkdir(parents=True, exist_ok=False)
    (output / 'topics').mkdir()
    files = {}
    for name, value in {'catalog.json': {'courses': [course]}, **topics}.items():
        data = encoded(value)
        (output / name).write_bytes(data)
        files[name] = hashlib.sha256(data).hexdigest()
    manifest = {'schema': 1, 'adapter': 'hyperskill', 'topic_format_version': 2,
                'subject_id': original_manifest.get('subject_id', 'cs'),
                'hyperskill_practice_revision': True, 'files': files}
    (output / 'manifest.json').write_bytes(encoded(manifest))
    return {'course': course_id, 'topics': len(topics)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--course-id', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output, args.course_id)), flush=True)
