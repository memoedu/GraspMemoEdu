"""Serve an isolated, synthetic topic and deterministic clipper responses."""
import argparse
import json
from pathlib import Path
import sys
import os
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


def provider(config, path, payload, timeout, limit):
    messages = payload['messages']
    last = messages[-1]['content']
    if payload.get('stream'):
        delta = json.dumps({'choices': [{'delta': {'content': '测试回答：保留题干条件。'}, 'finish_reason': None}]})
        done = json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}]})
        return ('data: ' + delta + '\n\ndata: ' + done + '\n\ndata: [DONE]\n\n').encode(), 'text/event-stream'
    try:
        source = json.loads(last) if isinstance(last, str) else {}
    except ValueError:
        source = {}
    if 'sentence' in source and 'target' in source:
        data = {'meaning_zh': '条件满足', 'pronunciation': 'chéng lì'}
    elif 'question' in source:
        data = {'answer_state': 'answered', 'answer_text': '条件满足。', 'unresolved_reasons': []}
    else:
        data = {'status': 'ready', 'pronunciation': 'chéng lì', 'meaning': '条件满足', 'generatedSentence': None,
                'generatedTargetStart': None, 'unresolvedReasons': []}
    response = {'choices': [{'message': {'content': json.dumps(data, ensure_ascii=False)}, 'finish_reason': 'stop'}]}
    return json.dumps(response, ensure_ascii=False).encode(), 'application/json'


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
        '<p id="clip-archived">Stored formula <span class="mathInline" data-tex="a+b+c">'
        '<mjx-container jax="SVG"><svg width="20" height="16"><path d="M2 2H16"/></svg></mjx-container></span>.</p>'
        '<p id="clip-fragment">Formula fragment \\(a+b+c+\\frac{x+1}{y-2}\\) in a sentence.</p>'
        '<p id="clip-sentence">前一句。若 <span data-tex="x&gt;0">x&gt;0</span>，结论成立。若 '
        '<span data-tex="x^2=0.25">x²=0.25</span>，另一结论成立。后一段。</p>'
        '<section id="clip-mixed"><p>比较 <span data-tex="a^2+b^2">a²+b²</span> 与下方代码。</p>'
        '<pre><code class="language-python">if x &gt; 0:\n    print(x)</code></pre>'
        '<p>见图 <img alt="方块" width="16" height="16" '
        'src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAQAAAAECAIAAAAmkwkpAAAAE0lEQVR4nGNkYGhggAEmOAsvBwAZhACIfojS8QAAAABJRU5ErkJggg=="></p></section>'
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
    # Only this synthetic process routes services to fixtures. The production gateway is unchanged.
    def record(config, path, payload, timeout, limit):
        with (args.root / 'provider-inputs.jsonl').open('a', encoding='utf-8') as receipt:
            receipt.write(json.dumps({'path': path, 'payload': payload}, ensure_ascii=False) + '\n')
        if path == '/audio/speech':
            return (args.root / 'speech.mp3').read_bytes(), 'audio/mpeg'
        return provider(config, path, payload, timeout, limit)
    import subprocess
    subprocess.run(['ffmpeg', '-nostdin', '-loglevel', 'error', '-f', 'lavfi', '-i', 'sine=frequency=440:duration=0.15',
                    '-codec:a', 'libmp3lame', str(args.root / 'speech.mp3')], check=True)
    env = {f'GRASPMEMOEDU_CLIPPER_{prefix}{key}': value for prefix in ('', 'SPEECH_', 'OCR_')
           for key, value in [('MODEL', 'fixture-model'), ('BASE_URL', 'https://example.invalid/v1'), ('API_KEY', 'test')]}
    with patch.dict(os.environ, env), patch('graspmemoedu.clipper_gateway.provider_post', record), \
            patch('graspmemoedu.clipper_gateway.reference_read', return_value={'status': 200, 'content': '{}', 'mime': 'application/json'}):
        uvicorn.run(app, host='127.0.0.1', port=args.port, log_level='warning')


if __name__ == '__main__':
    main()
