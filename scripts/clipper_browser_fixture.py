"""Serve an isolated, synthetic topic and deterministic clipper responses."""
import argparse
import json
from pathlib import Path
import sys
from unittest.mock import patch

import uvicorn

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from graspmemoedu.api import create_app
from graspmemoedu.clipper import register_clipper_routes
from graspmemoedu.config import Settings
from graspmemoedu.service import LearningService
from tests.fixtures import DeterministicJudge, synthetic_course


def model(instructions, source, **_):
    if 'allowedTypes' in source:
        return json.dumps({'cards': [{'front': 'Fixture generated front', 'back': 'Fixture generated back',
                                     'typeId': 'fast-answer'}]})
    return 'Fixture meaning: sequence' if '解释所选词' in instructions else 'Fixture response: ' + source['question']


def clipper(app, access, profile, dictionary):
    register_clipper_routes(app, access, profile, dictionary, generate=model)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('root', type=Path)
    parser.add_argument('--port', type=int, default=18891)
    args = parser.parse_args()
    args.root.mkdir(parents=True, exist_ok=False)
    course = synthetic_course()
    course['modules'][0]['example']['html'] = (
        '<p id="clip-fixture">Capture the sequence <span data-tex="x^2">x²</span> on this line.</p>'
        '<p id="clip-formulas">Inline \\(\\frac{a}{b}\\) and display $$y^3=z$$.</p>'
        '<p>Legacy SVG <mjx-container jax="SVG"><svg width="40" height="34" viewBox="0 0 40 34">'
        '<defs><path id="MJX-1-TEX-N-31" d="M1 1V9"/><path id="MJX-1-TEX-N-32" d="M1 1H6V9H1"/></defs>'
        '<g data-mml-node="math"><g data-mml-node="mfrac"><g data-mml-node="mn"><use href="#MJX-1-TEX-N-31"/></g>'
        '<g data-mml-node="mn" transform="translate(0 20)"><use href="#MJX-1-TEX-N-32"/></g>'
        '<rect width="16" height="1" y="14"/></g></g></svg></mjx-container></p>'
        '<p>Native MathML <math><msup><mi>m</mi><mn>3</mn></msup></math></p>'
        '<details><summary>Optional</summary><p>PRIVATE_HIDDEN_FIXTURE</p></details>'
    )
    settings = Settings(data_dir=args.root, port=args.port)
    with patch('graspmemoedu.api.register_clipper_routes', clipper):
        app = create_app(settings, LearningService(course, args.root, DeterministicJudge()))
    accounts = [app.state.access_store.create_account(name, purpose='test', is_student=True)['invitation_code']
                for name in ['Clipper A', 'Clipper B']]
    (args.root / 'browser-fixtures.json').write_text(json.dumps(accounts), encoding='utf-8')
    print('READY clipper fixture', flush=True)
    uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')


if __name__ == '__main__':
    main()
