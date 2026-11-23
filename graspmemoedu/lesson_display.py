"""Source-bound display changes for imported Math Academy lessons."""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re

from .content_bundle import content_root


DIRECTORY = 'mathacademy-sources/lesson-display'
EDITORIAL = re.compile(r'^\s*\(?(?:old\s+)?(?:notes?|draft)(?=\s|\)|:|$)', re.I)


def display_key(kind, source):
    return hashlib.sha256((kind + '\0' + source).encode()).hexdigest()


def display_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()


def display_fields(row, names):
    return [(row, name, 'title' if name in ('title', 'text') else 'html') for name in names
            if isinstance(row.get(name), str) and row[name].strip()]


def question_fields(question):
    for binding in display_fields(question, ('title', 'html', 'explanation_html')):
        yield binding
    spec = question.get('interaction') or {}
    for section in spec.get('sections', []):
        yield from display_fields(section, ('html',))
    options = list(spec.get('options', []))
    for control in spec.get('controls', []):
        options.extend(control.get('options', []))
    for option in options:
        yield from display_fields(option, ('html',) if option.get('html') else ('text',))


def lesson_fields(topic, active_questions=()):
    for intro in topic['introductions']:
        if not EDITORIAL.match(intro['title']):
            yield from display_fields(intro, ('title', 'html'))
    for module in topic['modules']:
        if not EDITORIAL.match(module['title']):
            yield from display_fields(module, ('title',))
    questions = (question for module in topic['modules'] for question in [module['example'], *module['practices']])
    for question in (*questions, *topic.get('unassigned_questions', []), *active_questions):
        if not EDITORIAL.match(question.get('title', '')):
            yield from question_fields(question)


def read_display(path):
    if not path.is_file():
        return {}
    if path.is_symlink() or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError('Invalid lesson display file')
    document = json.loads(path.read_bytes())
    if not isinstance(document, dict) or document.get('schema') != 1:
        raise ValueError('Invalid lesson display schema')
    return document


cached_display = lru_cache(maxsize=24)(read_display)


class LessonDisplay:
    def __init__(self, data_dir, topic):
        self.preview = False
        self.values = {}
        self.tex_repairs = {}
        tid = topic['id']
        if topic.get('source_adapter') != 'mathacademy' or not re.fullmatch(r'ma-topic-\d+', tid):
            return
        root = content_root(data_dir) / DIRECTORY
        scope = cached_display(root / 'preview.json').get('topics', {})
        self.preview = scope.get(tid) == topic['version']
        localized = cached_display(root / (tid + '.json'))
        if localized.get('topic_id') == tid and localized.get('version') == topic['version']:
            self.values = localized['values']
            self.tex_repairs = localized.get('tex_repairs', {})

    def apply(self, result, bindings):
        for row, field, kind in bindings:
            key = display_key(kind, row[field])
            value = self.values.get(key, row[field])
            repair = self.tex_repairs.get(key) if kind == 'html' else None
            if repair and repair['before_sha256'] == display_hash(value):
                value = repair['html']
            row[field] = value
        return result

    def introduction(self, intro):
        if source := intro.get('_ma_body_source'):
            from .mathacademy_layout import heading_blocks
            localized = self.introduction(source)
            if localized is source:
                return intro
            fragments = heading_blocks(localized['html'])
            title = localized['title'] if intro['title'] == source['title'] else intro['title']
            if len(fragments) == intro['_ma_body_count']:
                return {**intro, 'title': title, 'html': fragments[intro['_ma_body_index']]}
            return {**intro, 'title': title}
        if not (self.values or self.tex_repairs) or EDITORIAL.match(intro['title']):
            return intro
        result = dict(intro)
        return self.apply(result, display_fields(result, ('title', 'html')))

    def module(self, module):
        if not self.values or EDITORIAL.match(module['title']):
            return module
        result = dict(module)
        return self.apply(result, display_fields(result, ('title',)))

    def question(self, question):
        if not (self.values or self.tex_repairs) or EDITORIAL.match(question.get('title', '')):
            return question
        result = deepcopy(question)
        return self.apply(result, question_fields(result))
