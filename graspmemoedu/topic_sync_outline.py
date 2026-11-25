"""Project the learner-facing course text into a stable, editable Topic outline."""
import re
from uuid import NAMESPACE_URL, uuid5

from .lesson_display import LessonDisplay
from .topic_composition import introduction_html
from .topic_structure import sections


MATH = re.compile(r'\\\((.+?)\\\)|\\\[(.+?)\\\]', re.S)
HEADINGS = ('h1', 'h2', 'h3', 'h4', 'h5', 'h6')
CONTAINERS = ('div', 'section', 'article', 'ul', 'ol', 'figure', 'figcaption')
BLOCK_TAGS = frozenset(HEADINGS + CONTAINERS + ('details', 'li', 'p', 'pre', 'blockquote', 'table', 'hr'))


def official_outline(topic, data_dir):
    from bs4 import BeautifulSoup, Comment, Tag
    from markdownify import MarkdownConverter

    class CourseMarkdown(MarkdownConverter):
        def convert_gmeformula(self, el, text, parent_tags):
            return el.get_text()

    converter = CourseMarkdown(heading_style='ATX', bullets='-', escape_underscores=False,
                               keep_inline_images_in=['p', 'li', 'td', 'a'])
    rows = []

    def add(key, parent, kind, text):
        node_id = str(uuid5(NAMESPACE_URL, 'graspmemoedu/' + topic['id'] + '/' + key))
        rows.append({'id': node_id, 'parent_id': parent, 'kind': kind, 'text': text})
        return node_id

    def body(fragment, parent, key, title=None):
        soup = BeautifulSoup(fragment or '', 'html.parser')

        def formula(tex, display):
            tex = tex.strip()
            for start, end in ((r'\(', r'\)'), (r'\[', r'\]'), ('$$', '$$'), ('$', '$')):
                if tex.startswith(start) and tex.endswith(end) and len(tex) > len(start) + len(end):
                    tex = tex[len(start):-len(end)].strip()
                    display = display or start in (r'\[', '$$')
                    break
            literal = soup.new_tag('gmeformula')
            literal.string = '\n\n$$\n' + tex + '\n$$\n\n' if display else '$' + tex + '$'
            return literal

        # Select the author's TeX before markdownify walks visual and accessibility replicas.
        rendered = 'mjx-container, .mjpage'
        for element in soup.select('[data-latex], [data-tex], math, .katex-display, .katex, '
                                   + rendered + ', script[type^="math/tex"]'):
            if element.parent is None or not element.find_parent('[document]'):
                continue
            if len(element.select(rendered)) > 1:
                continue
            annotation = element.select_one('annotation[encoding="application/x-tex"]')
            title = element.select_one('.mjpage > svg > title')
            tex = element.get('data-latex') or element.get('data-tex') or (annotation or title)
            if isinstance(tex, Tag):
                tex = tex.get_text()
            if element.name == 'script':
                tex = element.get_text()
            if tex:
                displays = '.mathDisplay, .katex-display, .mjpage__block, [display="block"], [display="true"]'
                display = ('mode=display' in element.get('type', '') or
                           element.css.match(displays) or bool(element.select_one(displays)))
                element.replace_with(formula(tex, display))
        for element in soup.select('script, style, template, .katex-html, .katex-mathml, mjx-assistive-mml'):
            element.decompose()
        for item in list(soup.find_all(string=MATH)):
            if item.find_parent(['pre', 'code', 'gmeformula', 'svg', 'math']):
                continue
            start = 0
            for match in MATH.finditer(item):
                item.insert_before(item[start:match.start()])
                item.insert_before(formula(match[1] or match[2], match[2] is not None))
                start = match.end()
            item.replace_with(item[start:])

        def items_with_inline_runs(items):
            run = []
            for i, item in enumerate(items):
                if isinstance(item, Comment):
                    continue
                if getattr(item, 'name', None) not in BLOCK_TAGS:
                    run.append((i, item))
                    continue
                if run:
                    yield run[0][0], [part for _, part in run]
                    run.clear()
                yield i, [item]
            if run:
                yield run[0][0], [part for _, part in run]

        def markdown(items, context=()):
            return ''.join(converter.process_element(item, set(context)) for item in items).strip()

        def visit(items, owner, path):
            headings = []
            for i, parts in items_with_inline_runs(items):
                item = parts[0]
                current = f'{path}/{i}'
                nested = []
                kind = 'bullet'
                parent_id = headings[-1][1] if headings else owner
                tag = getattr(item, 'name', None)
                if tag in HEADINGS:
                    level = int(tag[1])
                    while headings and headings[-1][0] >= level:
                        headings.pop()
                    parent_id = headings[-1][1] if headings else owner
                    text = markdown(parts)
                    if text:
                        matches_title = path == key and rows[-1]['id'] == owner and item.get_text(strip=True) == title
                        headings.append((level, owner if matches_title else add(current, parent_id, 'heading', text)))
                    continue
                if tag == 'details' and (summary := item.find('summary', recursive=False)):
                    text = markdown(summary.children, ('summary',))
                    nested = [child for child in item.children if child is not summary]
                elif tag == 'li' or isinstance(item, Tag) and 'outlineNode' in item.get('class', []):
                    kind = 'numbered' if tag == 'li' and item.parent.name == 'ol' else 'bullet'
                    nested = [child.extract() for child in item.find_all(CONTAINERS + ('details',), recursive=False)]
                    text = markdown(item.children, (tag,))
                elif tag in CONTAINERS:
                    visit(list(item.children), parent_id, current)
                    continue
                else:
                    text = markdown(parts)
                if text or nested:
                    node_id = add(current, parent_id, kind, text)
                    visit(nested, node_id, current + '/list')
        visit(list(soup.children), parent, key)

    display = LessonDisplay(data_dir, topic)
    for section in sections(topic):
        intro = display.introduction(section['introduction'])
        key = 'intro/' + section['id']
        owner = add(key, None, 'heading', intro.get('title') or topic['title'])
        body(introduction_html(intro), owner, key + '/body', intro.get('title'))
        for chunk in section['chunks']:
            chunk_key = 'chunk/' + chunk['id']
            node_id = add(chunk_key, owner, 'heading', chunk.get('title') or intro.get('title') or topic['title'])
            body(chunk.get('content_html', ''), node_id, chunk_key + '/body')
            if chunk.get('mnemonic_html'):
                body(chunk['mnemonic_html'], node_id, chunk_key + '/mnemonic')
    return {'format': 'topic-outline-v1', 'title': topic['title'], 'blocks': rows}
