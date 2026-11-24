"""Package an exact AnnotationCapture whiteboard build as a sandboxed document."""

import argparse
import base64
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def integrity(source):
    return 'sha256-' + base64.b64encode(hashlib.sha256(source.encode()).digest()).decode()


def read_asset(html, pattern, root):
    reference, = re.findall(pattern, html)
    return (root / 'assets' / reference).read_text(encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('build', type=Path)
    parser.add_argument('licenses', type=Path)
    parser.add_argument('source', help='The exact AnnotationCapture source commit')
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{40}', args.source):
        parser.error('Use an exact 40-character source commit')
    html = (args.build / 'whiteboard.html').read_text(encoding='utf-8')
    js = r'<script type="module" crossorigin src="\./assets/(whiteboard-[\w-]+\.js)"></script>'
    css = r'<link rel="stylesheet" crossorigin href="\./assets/(whiteboard-[\w-]+\.css)">'
    script = read_asset(html, js, args.build)
    style = read_asset(html, css, args.build)
    if '</script' in script.lower() or '</style' in style.lower():
        raise ValueError('An asset contains an HTML raw-text closing tag')
    script_hash = integrity(script)
    policy = f"default-src 'none'; script-src '{script_hash}'; style-src '{integrity(style)}'; img-src data: blob:"
    html, count = re.subn(r'(<meta http-equiv="Content-Security-Policy" content=")[^"]+', lambda match: match[1] + policy, html)
    if count != 1 or html.count('<html lang="zh-CN">') != 1:
        raise ValueError('Unexpected whiteboard document')
    html = re.sub(js, lambda _: '<script type="module">' + script + '</script>', html)
    html = re.sub(css, lambda _: '<style>' + style + '</style>', html)
    source = 'https://github.com/Rowan-memoedu/AnnotationCapture/tree/' + args.source
    module = f'// Editor script integrity: {script_hash}\n// Corresponding GPLv3 source: {source}\n'
    module += 'export const whiteboardDocument = ' + json.dumps(html, ensure_ascii=False) + ';\n'
    license_files = ('COPYING.txt', 'LICENSE-fabric.txt', 'LICENSE-perfect-freehand.txt', 'THIRD_PARTY_NOTICES.md')
    notices = '\n\n'.join((args.licenses / name).read_text(encoding='utf-8') for name in license_files)
    for name, contents in [('whiteboard-editor.js', module), ('whiteboard-license.txt', source + '\n\n' + notices)]:
        (ROOT / 'web' / name).write_text(contents, encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
