"""Project existing structured grading answers only when the answer side is visible."""
from functools import lru_cache
from html import escape
import json
from pathlib import Path
import re
import subprocess

from .question_types import demo_answer, display_answer


def choice_feedback(question):
    """Answer-side metadata identifying the expected choices."""
    spec = question.get('interaction') or {}
    kind = spec.get('type')
    if kind in ('composite', 'fill_blank'):
        rows = spec['controls' if kind == 'composite' else 'blanks']
        items = []
        for row in rows:
            if not row.get('answers'):
                continue
            item = {'id': row['id'], 'answer': row['answers'][0]}
            if row.get('type') == 'select':
                item['correct_ids'] = list(row['answers'])
            items.append(item)
        return {'items': items} if items else None
    if kind == 'matching':
        side = spec.get('fixed_side')
        if side not in ('left', 'right'):
            return None
        other = 'right' if side == 'left' else 'left'
        return {'items': [{'id': pair[side], 'correct_ids': [pair[other]]} for pair in spec['pairs']]}
    if spec.get('type') != 'choice' or not (spec.get('correct_id') or spec.get('correct_ids')):
        return None
    return {'correct_ids': list(spec['correct_ids']) if spec.get('multiple') else [spec['correct_id']]}


@lru_cache(maxsize=256)
def _render_values(values):
    fallback = tuple(escape(text).replace('\n', '<br>') for text in values)
    if not any(re.search(r'[$\\^_=<>≤≥≠*/×÷+\-\[({]|[Α-Ωα-ω]', text) for text in values):
        return fallback, ''
    try:
        from .guide import GuideReader
        rendered = GuideReader(Path())._compile('', answer_values=values)
        answers = rendered.get('answer_html')
        if isinstance(answers, list) and len(answers) == len(values) and all(isinstance(x, str) for x in answers):
            return tuple(answers), rendered['math_css']
    except (ValueError, OSError, subprocess.SubprocessError):
        pass
    return fallback, ''


def _render_items(rows, *, paragraphs=True):
    rendered, css = _render_values(tuple(item['text'] for item in rows if not item.get('html')))
    plain = iter('<p>' + value + '</p>' if paragraphs else value for value in rendered)
    return [item.get('html') or next(plain) for item in rows], css


def _render_blanks(spec, demo):
    submitted = json.loads(demo)
    if spec['type'] == 'composite':
        values = submitted['values']
        labels = [f"{control.get('label', control['id'])}: " for control in spec['controls']]
        rows = [next((option for option in control.get('options', []) if option['id'] == values[control['id']]),
                     {'text': values[control['id']]}) for control in spec['controls']]
    else:
        labels = [f'{index + 1}. ' for index, _ in enumerate(spec['blanks'])]
        rows = [{'text': submitted[blank['id']]} for blank in spec['blanks']]
    cells, css = _render_items([{'text': label} for label in labels] + rows, paragraphs=False)
    return ''.join('<div>' + label + answer + '</div>'
                   for label, answer in zip(cells[:len(labels)], cells[len(labels):])), css


def reference_fields(question, visible=False, *, answer=None):
    spec = question.get('interaction') or {}
    if not visible or spec.get('type', 'text') == 'text' or spec.get('grading') == 'unavailable':
        return {}
    submitted = answer
    demo = demo_answer(question)
    answer = display_answer(question, demo)
    if spec['type'] == 'choice':
        ids = set(spec['correct_ids']) if spec.get('multiple') else {spec['correct_id']}
        rows = [item for item in spec['options'] if item['id'] in ids]
        rendered, css = _render_items(rows)
        html = ''.join(rendered)
    elif spec['type'] == 'matching':
        labels = {side: {item['id']: item for item in spec[side]} for side in ('left', 'right')}
        arrow = '↔' if spec.get('direction') == 'both' else '→'
        rendered, css = _render_items([labels[side][pair[side]] for pair in spec['pairs'] for side in ('left', 'right')])
        pairs = zip(rendered[::2], rendered[1::2])
        html = ''.join(f'<div class="referencePair"><div>{left}</div><span>{arrow}</span><div>{right}</div></div>'
                       for left, right in pairs)
    elif spec['type'] in ('composite', 'fill_blank') and demo:
        html, css = _render_blanks(spec, demo)
    else:
        rendered, css = _render_values((answer,))
        html = '<p>' + rendered[0] + '</p>'
    fields = {'reference_answer': answer, 'reference_answer_html': html, 'reference_math_css': css}
    feedback = choice_feedback(question)
    if feedback:
        if submitted and feedback.get('items') and spec.get('grading') not in ('semantic', 'unavailable'):
            from .point_assessment import item_results
            results = item_results(question, submitted)
            if spec['type'] == 'matching' and spec.get('fixed_side') == 'right':
                results = {pair['right']: results[pair['left']] for pair in spec['pairs']}
            for item in feedback['items']:
                if item['id'] in results:
                    item['correct'] = results[item['id']]
        fields['choice_feedback'] = feedback
    return fields
