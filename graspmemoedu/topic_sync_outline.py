"""Project the learner-facing course text into a stable, editable Topic outline."""
from uuid import NAMESPACE_URL, uuid5

from .lesson_display import LessonDisplay
from .topic_structure import sections


def official_outline(topic, data_dir):
    from bs4 import BeautifulSoup, NavigableString, Tag
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

    def body(fragment, parent, key):
        soup = BeautifulSoup(fragment, 'html.parser')
        # Select the author's TeX before markdownify walks visual and accessibility replicas.
        for element in soup.select('[data-latex], [data-tex], math, .katex, script[type^="math/tex"]'):
            if element.parent is None:
                continue
            annotation = element.select_one('annotation[encoding="application/x-tex"]')
            tex = element.get('data-latex') or element.get('data-tex') or (annotation.get_text() if annotation else '')
            if element.name == 'script':
                tex = element.get_text()
            if tex:
                delimiter = '$$' if element.get('display') == 'block' or 'mode=display' in element.get('type', '') else '$'
                # Use a Tag so underscores, stars and backslashes in TeX survive conversion.
                literal = soup.new_tag('gmeformula')
                literal.string = delimiter + tex + delimiter
                element.replace_with(literal)
        for element in soup.select('script, style, template'):
            element.decompose()

        def markdown(item):
            if isinstance(item, NavigableString):
                return str(item).strip()
            return converter.process_element(item, set()).strip()

        def visit(items, owner, path):
            for i, item in enumerate(items):
                current = f'{path}/{i}'
                if isinstance(item, Tag) and item.name in ('div', 'section', 'article', 'ul', 'ol'):
                    visit(list(item.children), owner, current)
                    continue
                nested = []
                if isinstance(item, Tag) and item.name == 'li':
                    numbered = item.parent.name == 'ol'
                    nested = [child.extract() for child in item.find_all(['ol', 'ul'], recursive=False)]
                    text = ''.join(converter.process_element(child, {'li'}) for child in item.children).strip()
                    kind = 'numbered' if numbered else 'bullet'
                else:
                    text = markdown(item)
                    kind = 'heading' if getattr(item, 'name', '') in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6') else 'bullet'
                if text or nested:
                    node_id = add(current, owner, kind, text)
                    visit(nested, node_id, current + '/list')
        visit(list(soup.children), parent, key)

    display = LessonDisplay(data_dir, topic)
    for section in sections(topic):
        intro = display.introduction(section['introduction'])
        key = 'intro/' + section['id']
        owner = add(key, None, 'heading', intro.get('title') or topic['title'])
        body(intro.get('html', ''), owner, key + '/body')
        for chunk in section['chunks']:
            chunk_key = 'chunk/' + chunk['id']
            node_id = add(chunk_key, owner, 'heading', chunk.get('title') or intro.get('title') or topic['title'])
            body(chunk.get('content_html', ''), node_id, chunk_key + '/body')
            if chunk.get('mnemonic_html'):
                body(chunk['mnemonic_html'], node_id, chunk_key + '/mnemonic')
    return {'format': 'topic-outline-v1', 'title': topic['title'], 'blocks': rows}
