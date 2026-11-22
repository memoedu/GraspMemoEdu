"""Compile source-bound MA answer revisions for already installed Topic questions."""
import argparse
from decimal import Decimal
import json
from pathlib import Path
import re
from zipfile import ZipFile

from .mathacademy_import import Assets, Renderer, answer_sections, controls, question_model, file_hash
from .question_bank import digest, source_questions, validate_bank
from .topic_install import encoded


def decimal_answers(value):
    """Accept trailing zeros and the source's displayed precision for a decimal blank."""
    if not re.fullmatch(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)', value) or len(value) > 40:
        raise ValueError('Numeric source answer is not a plain decimal')
    number = Decimal(value)
    canonical = format(number, 'f') if number else '0'
    if '.' in canonical:
        canonical = canonical.rstrip('0').rstrip('.')
    fixed = canonical.partition('.')[0]
    digits = canonical.partition('.')[2]
    return list(dict.fromkeys([value, canonical, *(fixed + '.' + digits.ljust(n, '0')
                                                   for n in range(max(1, len(digits)), 7))]))


def source_variant(topic_question, source, assets, choice_indices=()):
    qid = source['id']
    stem = (source.get('text') or '').strip()
    installed_stem = topic_question['question'].strip()
    if source.get('graphic'):
        installed_stem = re.sub(r'^<img alt="Source diagram" src="data:image/png;base64,[A-Za-z0-9+/=]+">\s*',
                                '', installed_stem, count=1)
    if (topic_question['id'] != f'ma-question-{qid}' or not stem
            or topic_question.get('source_format') != source['format']
            or not (installed_stem == stem or installed_stem.startswith(stem + '\n\n'))
            or topic_question.get('_source', {}).get('parameter_changes')
            or topic_question.get('_source', {}).get('fill_in_adaptation')):
        raise ValueError(f'Question {qid} is not bound to the same source stem')
    gaps = []
    spec = controls(source, assets, gaps)
    if source['format'] == 'MC':
        if (not spec or len(choice_indices) != 1 or type(choice_indices[0]) is not int
                or not 0 <= choice_indices[0] < len(spec['options'])):
            raise ValueError(f'Question {qid} has no verified choice')
        spec['correct_id'] = spec['options'][choice_indices[0]]['id']
    else:
        exact_fill_in(spec, source, choice_indices)
    model = question_model(source, assets, gaps)
    if any(item['code'] == 'image_missing' for item in gaps):
        raise ValueError(f'Question {qid} has missing source graphics')
    spec['grading'] = 'exact'
    return {'source_sha256': digest(topic_question), 'question': model['question'],
            'html': model['html'], 'interaction': spec}


def exact_fill_in(spec, source, choice_indices):
    qid = source['id']
    if source['format'] not in ('FR', 'SS', 'PR', 'DS'):
        raise ValueError(f'Question {qid} has no confirmed fill-in segments')
    inputs = [(key, segment[key]) for part in answer_sections(source) for segment in part or []
              for key in ('textbox', 'select') if key in segment]
    if not spec or len(spec['controls']) != len(inputs) or not all(part['complete'] for part in spec['sections']):
        raise ValueError(f'Question {qid} has incomplete or ambiguous answer controls')
    indices = iter(choice_indices)
    for item, (kind, raw) in zip(spec['controls'], inputs, strict=True):
        if kind == 'select':
            index = next(indices, None)
            if type(index) is not int or not 0 <= index < len(item['options']):
                raise ValueError(f'Question {qid} has no verified answer for a dropdown')
            item['answers'] = [item['options'][index]['id']]
        else:
            answer = raw.get('answer')
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError(f'Question {qid} has no verified answer for a blank')
            item['answers'] = decimal_answers(answer) if raw.get('type') == 'number' else [answer]
    if next(indices, None) is not None:
        raise ValueError(f'Question {qid} has unmatched dropdown answers')


def compile_revisions(snapshot, archive, selection, assets, output):
    source_hash = file_hash(archive)
    output.mkdir(parents=True, exist_ok=True)
    renderer = Renderer()
    try:
        with ZipFile(archive) as originals:
            for tid, evidence_by_id in sorted(selection.items()):
                if not re.fullmatch(r'ma-topic-\d+', tid) or not evidence_by_id:
                    raise ValueError('Selection must name a nonempty Math Academy Topic')
                selected = {int(qid): evidence for qid, evidence in evidence_by_id.items()}
                topic = json.loads((snapshot / 'topics' / f'{tid}.json').read_bytes())
                lesson = json.loads(originals.read(f"topic-json/topic-{tid.removeprefix('ma-topic-')}.json"))['lesson']
                if tid != f"ma-topic-{lesson['topic']['id']}" or topic['id'] != tid:
                    raise ValueError('Source and installed Topic identities differ')
                source = {step['question']['id']: step['question'] for step in lesson['steps'] if step['type'] == 'question'}
                installed = source_questions(topic)
                questions = {f'ma-question-{qid}': source_variant(installed[f'ma-question-{qid}'], source[qid], assets,
                                                                 evidence.get('choice_indices', []))
                             for qid, evidence in selected.items()}
                rendered = renderer.render({'id': tid, 'questions': questions})
                bank = {'schema': 1, 'topic_id': tid, 'course_version': topic['version'],
                        'questions': rendered['questions'], 'math_css': rendered['math_css'],
                        'provenance': {'adapter': 'mathacademy-source-controls', 'archive_sha256': source_hash,
                                       'selection_sha256': digest(selected)}}
                revision = validate_bank(bank, topic)
                path = output / f'{tid}.json'
                with path.open('xb') as stream:
                    stream.write(encoded(bank))
                print(json.dumps({'topic_id': tid, 'questions': len(questions), 'revision': revision}), flush=True)
    finally:
        renderer.close()


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    for arg in ('snapshot', 'archive', 'selection', 'graphics', 'cache', 'output'):
        cli.add_argument('--' + arg, required=True, type=Path)
    args = cli.parse_args()
    assets = Assets(args.cache, json.loads(args.graphics.read_bytes()))
    compile_revisions(args.snapshot, args.archive, json.loads(args.selection.read_bytes()), assets, args.output)


if __name__ == '__main__':
    main()
