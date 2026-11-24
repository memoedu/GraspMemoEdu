"""Preserve original excerpt material in RemNote's indented Markdown format."""
import re


TOKEN = re.compile(
    r'(?P<code>(?P<ticks>\x60+)(?!\x60)[^\n]*?(?<!\x60)(?P=ticks)(?!\x60))'
    r'|!\[(?P<alt>(?:\\.|[^\]\\])*)\]\(asset:(?P<image>[a-f0-9]{64})\)'
    r'|\\\((?P<inline>[\s\S]*?)\\\)|\\\[(?P<display>[\s\S]*?)\\\]'
    r'|(?<!\\)\$\$(?P<block>[\s\S]*?)\$\$|(?<![\\$])\$(?P<dollar>[^$\n]+?)\$(?!\$)')
FENCE = re.compile(r'^[ ]{0,3}(\x60{3,}|~{3,})(.*)$')


def inline(text, media, used):
    def literal(value):
        return re.sub(r'([\\\x60*_~<>{}\[\]])', r'\\\1', value)

    offset, parts = 0, []
    for token in TOKEN.finditer(text):
        parts.append(literal(text[offset:token.start()]))
        if token['code']:
            parts.append(token['code'])
        elif token['image']:
            digest = token['image']
            if digest in media:
                parts.append('![' + token['alt'] + '](' + media[digest] + ')')
                used.add(digest)
            else:
                parts.append(literal(token['alt']))
        elif token['display'] is not None or token['block'] is not None:
            tex = token['display'] if token['display'] is not None else token['block']
            parts.append('$$\n' + tex.strip() + '\n$$')
        else:
            tex = token['inline'] if token['inline'] is not None else token['dollar']
            parts.append(' $' + tex.strip() + '$ ')
        offset = token.end()
    return ''.join([*parts, literal(text[offset:])])


def material_blocks(text, media, used):
    """Separate Markdown blocks before escaping prose. Fenced code retains all its whitespace."""
    pending, code, fence = [], [], ''

    def prose():
        block = inline('\n'.join(pending), media, used)
        pending.clear()
        display = False
        math = []
        for line in block.splitlines():
            if '$$' in line or display:
                math.append(line.strip())
                if line.count('$$') % 2:
                    display = not display
                if not display:
                    yield math
                    math = []
            elif line.strip():
                yield [line.strip()]
        if math:
            yield math

    for line in text.splitlines():
        if fence:
            code.append(line)
            if re.fullmatch(r' {0,3}' + re.escape(fence[0]) + '{' + str(len(fence)) + r',}\s*', line):
                yield code
                fence, code = '', []
            continue
        match = FENCE.match(line)
        if match:
            yield from prose()
            fence, code = match[1], [line]
        else:
            pending.append(line)
    if code:
        yield code
    yield from prose()


def excerpt_outline(rows):
    lines = ['- 零碎知识剪藏', '  - 摘录']
    day = None
    for row in rows:
        if day != row['day']:
            day = row['day']
            lines.append('    - ' + day)
        media, used = row.get('media', {}), set()
        blocks = list(material_blocks(row['front'], media, used))
        for digest, name in media.items():
            if digest not in used:
                blocks.append([('![]' if name.endswith('.png') else '[录音]') + '(' + name + ')'])
        for index, block in enumerate(blocks or [['图片摘录']]):
            indent = '      ' if index == 0 else '        '
            lines.append(indent + '- ' + block[0])
            lines.extend(indent + '  ' + line for line in block[1:])
    return '\n'.join(lines) + '\n'
