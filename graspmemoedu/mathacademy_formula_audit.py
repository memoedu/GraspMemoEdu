"""Detect source LaTeX still visible in rendered Math Academy fields."""
from html.parser import HTMLParser
import json
from pathlib import Path
import re


ML_COURSES = frozenset({'ma-course-72', 'ma-course-140'})
VERBATIM = {'code', 'pre', 'kbd', 'samp', 'script', 'style', 'textarea', 'math', 'svg', 'mjx-container'}
TEXT_COMMAND = re.compile(
    r'(?<!\\)\\(?:\(|\)|\[|\]|begin\{|end\{|frac\b|dfrac\b|sqrt\b|math(?:bf|bb|rm|cal)\b|'
    r'operatorname\b|left\b|right\b|alpha\b|beta\b|theta\b|lambda\b|eta\b|quad\b|approx\b)'
    r'|\[/?math\]', re.I)
INLINE = re.compile(r'(?<!\\)\$\$?([^\n$]+?)(?<!\\)\$\$?')


class FormulaAudit(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.hidden = []
        self.visible = []
        self.errors = set()
        self.feed(source)
        self.close()
        text = ''.join(self.visible)
        if TEXT_COMMAND.search(text):
            self.errors.add('visible_tex_command')
        if any(re.search(r'[a-zA-Z]\w*\s*(?:[=^<>+]|_[{a-zA-Z0-9])|\\[A-Za-z]', match[1])
               for match in INLINE.finditer(text)):
            self.errors.add('visible_math_delimiters')

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if attributes.get('data-mml-node') == 'merror' or 'data-mjx-error' in attributes:
            self.errors.add('mathjax_error')
        if tag in VERBATIM:
            self.hidden.append(tag)
            self.visible.append('\n')
        elif tag in {'br', 'p', 'li', 'div', 'section', 'hr', 'tr', 'td', 'th'}:
            self.visible.append('\n')

    def handle_endtag(self, tag):
        if self.hidden and self.hidden[-1] == tag:
            self.hidden.pop()
            self.visible.append('\n')

    def handle_data(self, data):
        if not self.hidden:
            self.visible.append(data)


def audit_fields(item, path=()):
    """Yield stable field paths and error codes without copying private prose."""
    if isinstance(item, dict):
        if not path and isinstance(item.get('values'), dict) and isinstance(item.get('tex_repairs'), dict):
            from .lesson_display import display_hash
            repairs = item['tex_repairs']
            values = {key: repairs[key]['html'] if key in repairs
                      and repairs[key].get('before_sha256') == display_hash(value) else value
                      for key, value in item['values'].items()}
            item = {**item, 'values': values}
        for key, value in item.items():
            yield from audit_fields(value, (*path, key))
    elif isinstance(item, list):
        for index, value in enumerate(item):
            yield from audit_fields(value, (*path, str(index)))
    elif isinstance(item, str) and path and (path[-1] == 'html' or path[-1].endswith('_html')
            or len(path) == 2 and path[0] == 'values' and '<' in item):
        if defects := FormulaAudit(item).errors:
            yield {'path': '/'.join(path), 'defects': sorted(defects)}


def main():
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', type=Path, nargs='+')
    args = parser.parse_args()
    fields = []
    for file in args.files:
        source = json.loads(file.read_bytes())
        fields.extend({'file': file.name, **entry} for entry in audit_fields(source))
    print(json.dumps({'files': len(args.files), 'failed_fields': fields}, ensure_ascii=False))
    raise SystemExit(1 if fields else 0)


if __name__ == '__main__':
    main()
