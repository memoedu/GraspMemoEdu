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
    output = Path(__file__).resolve().parents[1] / 'graspmemoedu' / 'clipper_rules.json'
    content = json.dumps(build(args.repo, args.revision), ensure_ascii=False, indent=2) + '\n'
    if args.check:
        if output.read_text(encoding='utf-8') != content:
            raise SystemExit('Clipper rules differ from the specified source revision')
    else:
        output.write_text(content, encoding='utf-8')
