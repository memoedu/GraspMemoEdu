"""Preserve Machine Learning I tutorial and heading boundaries in the reader."""
from html.parser import HTMLParser
import re


ML1_COURSE = 'ma-course-72'
HEADING = re.compile(r'<h[1-6]\b', re.I)
VOID = frozenset('area base br col embed hr img input link meta param source track wbr'.split())


class _TopLevelHeadings(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.lines = [0, *(match.end() for match in re.finditer('\n', source))]
        self.stack = []
        self.headings = []
        self.balanced = True
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        if not self.stack and tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            line, column = self.getpos()
            self.headings.append((tag, self.lines[line - 1] + column))
        if tag not in VOID:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if not self.stack or self.stack.pop() != tag:
            self.balanced = False

    def handle_startendtag(self, tag, attrs):
        pass


def heading_blocks(source):
    """Return complete, byte-preserving sections, with headings at their start."""
    if not HEADING.search(source):
        return []
    parser = _TopLevelHeadings(source)
    if not parser.balanced or parser.stack or not parser.headings:
        return []
    highest = min(tag for tag, _ in parser.headings)
    starts = [offset for tag, offset in parser.headings if tag == highest]
    if source[:starts[0]].strip():
        starts.insert(0, 0)
    else:
        starts[0] = 0
    return [source[start:end] for start, end in zip(starts, [*starts[1:], len(source)])]


def _split_introduction(intro):
    html = heading_blocks(intro['html'])
    if not html:
        return [intro]
    return [
        {**intro, 'id': intro['id'] if index == 0 else f"{intro['id']}--body-{index + 1}",
         'title': '指导' if HEADING.match(fragment.lstrip()) else intro['title'], 'html': fragment,
         '_ma_body_source': intro, '_ma_body_index': index, '_ma_body_count': len(html)}
        for index, fragment in enumerate(html)
    ]


def source_ordered_topic(topic):
    """Project the installed source without changing Topic, question or source IDs."""
    parts = {row['id']: _split_introduction(row) for row in topic['introductions']}
    order = [
        entry
        for row in topic['content_order']
        for entry in ([{'kind': 'introduction', 'id': part['id']} for part in parts[row['id']]]
                      if row['kind'] == 'introduction' else [row])
    ]
    return {**topic, 'source_ordered_reading': True, 'content_order': order,
            'introductions': [part for group in parts.values() for part in group]}
