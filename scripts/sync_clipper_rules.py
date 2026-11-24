"""Build the site prompt bundle from committed KnowledgeClipper sources."""
import argparse
import json
from pathlib import Path
import re
import subprocess


def build(repo, revision):
    def git(*args):
        return subprocess.check_output(['git', '-C', repo, *args]).decode('utf-8')

    commit = git('rev-parse', '--verify', revision + '^{commit}').strip()

    def read(path):
        if not re.fullmatch(r'[\w/.-]+', path) or '..' in path.split('/'):
            raise ValueError('Unsafe prompt path')
        return git('show', f'{commit}:modes/chat/{path}').strip()

    return {
        'commit': commit,
        'system': read('system.md'),
        'integrate': read('actions/integrate.md'),
        'types': {row['id']: {'label': row['label'], 'prompt': read(row['promptFile'])}
                  for row in json.loads(read('question-types.json'))['types']},
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('repo')
    parser.add_argument('revision')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = root / 'graspmemoedu' / 'clipper_catalog.json'
    published = json.loads((root / 'scripts/clipper-assets.json').read_bytes())
    expected = build(args.repo, args.revision)
    if published['revision'] != expected['commit']:
        raise SystemExit('Update the workflow release lock before synchronizing its catalog.')
    import hashlib
    if args.check:
        content = output.read_bytes()
    else:
        from urllib.request import urlopen
        url = ('https://github.com/memoedu/KnowledgeClipper/releases/download/floating-' +
               expected['commit'][:12] + '/clipper_catalog.json')
        with urlopen(url, timeout=90) as response:
            content = response.read(2 * 1024 * 1024)
    if hashlib.sha256(content.replace(b'\r\n', b'\n')).hexdigest() != published['catalog_sha256']:
        raise SystemExit('Clipper catalog differs from the locked upstream artifact.')
    files = json.loads(content)['rules']
    names = subprocess.check_output(['git', '-C', args.repo, 'ls-tree', '-r', '--name-only', '-z',
                                     expected['commit'], '--', 'modes']).decode().split('\0')
    sources = {name[6:]: subprocess.check_output(['git', '-C', args.repo, 'show', expected['commit'] + ':' + name])
               .decode().replace('\r\n', '\n') for name in names if name.endswith(('.json', '.md'))}
    if sources != {name: text.replace('\r\n', '\n') for name, text in files.items()}:
        raise SystemExit('Packaged rule files differ from the upstream Git tree.')
    if not args.check:
        output.write_bytes(content)
