"""Start a loopback-only Calculator acceptance site with synthetic content."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import uvicorn
from graspmemoedu.api import create_app
from graspmemoedu.config import Settings
from graspmemoedu.service import create_learning_service
from graspmemoedu.training_content import fingerprint
from tests.fixtures import DeterministicJudge, synthetic_course
from tests.training_fixtures import training_bank


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output', type=Path)
    parser.add_argument('--port', type=int, default=18885)
    args = parser.parse_args()
    root = args.output.resolve()
    if not root.is_relative_to(Path('D:/Artifacts/GraspMemoEdu').resolve()):
        raise ValueError('Use a new GraspMemoEdu artifact directory')
    root.mkdir(parents=True, exist_ok=False)
    topic = synthetic_course(1)
    topic.update(id='calculator-fixture', topic_format_version=2, topic_kind='lesson',
                 content_version=topic['version'], source_adapter='mathacademy',
                 availability={'readable': True, 'trainable': False, 'reasons': []},
                 introductions=[topic['introduction']], content_order=[
                     {'kind': 'introduction', 'id': topic['introduction']['id']},
                     {'kind': 'example', 'id': 'module-1'}],
                 calculate={'level': 'cas', 'enable_modules': ['optimization', 'astronomy'],
                            'disable_modules': ['probability'], 'disable_keys': ['sin']})
    module = topic['modules'][0]
    module['example']['constraints'] = '按题意作答。'
    module['example']['html'] += (
        '<aside class="inline-document-callout callout" data-callout="requirement">'
        '<strong>要求</strong><p>Calculator: Graphing</p></aside>')
    module['practices'] = module['practices'][:4]
    module['practices'][0]['calculate'] = {'level': 'advanced', 'enable_modules': ['machine_learning', 'modular'],
                                          'disable_keys': ['matrix_inverse']}
    module['practices'][1]['calculate'] = 'basic'
    module['practices'][2]['calculate'] = 'none'
    (root / 'topic.json').write_text(json.dumps(topic), encoding='utf-8')
    (root / 'catalog.json').write_text(json.dumps({'courses': [
        {'id': 'calculator-course', 'title': 'Calculator course', 'topics': [
            {'id': topic['id'], 'path': 'topic.json'}]}]}), encoding='utf-8')
    bank = training_bank()
    group = bank['groups'][1]
    group['questions'][0]['calculate'] = {'level': 'scientific', 'enable_modules': ['graph']}
    bank['version'] = fingerprint(bank)
    (root / 'training-banks').mkdir()
    (root / 'training-banks' / 'isolated-bank.json').write_text(json.dumps(bank), encoding='utf-8')
    app = create_app(Settings(data_dir=root, port=args.port), create_learning_service(topic, root, DeterministicJudge()))
    account = app.state.access_store.create_account('Voice input fixture', purpose='test', is_student=True)
    (root / 'fixture-invitation.txt').write_text(account['invitation_code'], encoding='utf-8')
    print('READY calculator fixture', flush=True)
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')


if __name__ == '__main__':
    main()
