"""Bind Math Academy question-format decisions to the frozen source."""
import re

from .topic_install import digest, encoded


def inventory_item(question, bodies=()):
    choices = {}
    if question['format'] == 'MC':
        choices = {f'choice{i}': question[f'choice{i}'] for i in range(1, 6)
                   if str(question.get(f'choice{i}') or '').strip()}
    dropdowns = {f's{section}-p{position}': segment['select']['options']
                 for section, body in enumerate(bodies)
                 for position, segment in enumerate(body or [])
                 if segment.get('select', {}).get('options')}
    if not choices and not dropdowns and not any(row.get('options') for row in question.get('selects') or []):
        return None
    return {
        'source_sha256': digest(encoded(question)), 'format': question['format'],
        'stem': question.get('text') or '', 'choices': choices, 'dropdowns': dropdowns,
        'sections': [
            [segment if 'textbox' not in segment else {'textbox': True} for segment in body]
            if body else None for body in bodies
        ],
        'has_graphics': bool(question.get('graphic') or question.get('graphics')),
    }


def revise_stem(stem, edits, *, allow_empty=False):
    for old, new in edits:
        if stem.count(old) != 1:
            raise ValueError('Each prompt edit must match exactly one source passage')
        stem = stem.replace(old, new, 1)
    if not allow_empty and not stem.strip():
        raise ValueError('A fill-in prompt must state the original task')
    return stem


def validate_edits(key, text, edits, *, allow_empty=False):
    if not isinstance(edits, list) or any(
            not isinstance(edit, list) or len(edit) != 2
            or not all(isinstance(part, str) for part in edit) or not edit[0]
            or any(re.search(r'<|>|!\[|\\documentclass|\{\{', part) for part in edit)
            for edit in edits):
        raise ValueError(f'{key}: prompt edits must target text and preserve source markup and figures')
    revise_stem(text, edits, allow_empty=allow_empty)


def validate_plan(inventory, plan):
    if not isinstance(plan, dict) or set(inventory) != set(plan):
        provided = set(plan) if isinstance(plan, dict) else set()
        missing, extra = sorted(set(inventory) - provided), sorted(provided - set(inventory))
        raise ValueError(f'MA question plan must cover the inventory (missing {missing[:8]}, extra {extra[:8]})')
    for key, row in plan.items():
        item = inventory[key]
        if (not isinstance(row, dict)
                or not {'source_sha256', 'mode', 'reason'} <= set(row)
                or row['source_sha256'] != item['source_sha256']
                or not isinstance(row['reason'], str) or not row['reason'].strip()):
            raise ValueError(f'{key}: MA question decision is incomplete or source binding changed')
        mode = row['mode']
        extra = set(row) - {'source_sha256', 'mode', 'reason'}
        if mode == 'keep' and not extra:
            continue
        if mode == 'fill' and item['format'] == 'MC' and extra <= {'edits', 'labels', 'answer_separator'}:
            labels = row.get('labels', [''])
            if (not isinstance(labels, list) or not 1 <= len(labels) <= 20
                    or any(not isinstance(label, str) or len(label) > 80 or '\n' in label
                           or '{{' in label or '<' in label or '>' in label for label in labels)
                    or len(labels) > 1 and (not all(label.strip() for label in labels)
                                            or len(set(labels)) != len(labels))):
                raise ValueError(f'{key}: use distinct, short labels for multiple answer fields')
            if 'answer_separator' in row and (len(labels) < 2 or not isinstance(row['answer_separator'], str)
                                              or not row['answer_separator']):
                raise ValueError(f'{key}: invalid verified answer separator')
        elif mode == 'fill' and item['format'] != 'MC' and extra <= {'edits', 'dropdowns', 'section_edits'}:
            dropdowns = row.get('dropdowns')
            if (not isinstance(dropdowns, list) or not dropdowns
                    or not all(isinstance(value, str) and value in item['dropdowns'] for value in dropdowns)
                    or len(set(dropdowns)) != len(dropdowns)):
                raise ValueError(f'{key}: each converted dropdown must identify a captured control')
            passages = {f's{section}-p{position}': segment['text']
                        for section, body in enumerate(item['sections'])
                        for position, segment in enumerate(body or []) if 'text' in segment}
            section_edits = row.get('section_edits', {})
            if not isinstance(section_edits, dict) or set(section_edits) - set(passages):
                raise ValueError(f'{key}: each section edit must identify a captured text passage')
            for position, edits in section_edits.items():
                validate_edits(key, passages[position], edits, allow_empty=True)
        else:
            raise ValueError(f'{key}: invalid MA question-format decision')
        validate_edits(key, item['stem'], row.get('edits', []),
                       allow_empty=item['format'] != 'MC' and not item['stem'].strip())
