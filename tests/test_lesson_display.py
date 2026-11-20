import json
from pathlib import Path
import tempfile
import unittest

from graspmemoedu.lesson_display import DIRECTORY, LessonDisplay, display_key
from graspmemoedu.lesson_display_install import MarkupSignature


class LessonDisplayTests(unittest.TestCase):
    def test_student_display_binds_to_exact_source_without_changing_controls(self):
        topic = {'id': 'ma-topic-89', 'version': 'original', 'source_adapter': 'mathacademy'}
        question = {'title': 'Pick a shape', 'html': '<p>Choose one.</p>', 'interaction': {'type': 'choice',
            'options': [{'id': 'square', 'text': 'Square', 'html': '<p>Square</p>'}], 'correct_id': 'square'}}
        values = {display_key('html', '<p>Choose one.</p>'): '<p>选一种。</p>',
                  display_key('html', '<p>Square</p>'): '<p>正方形</p>',
                  display_key('html', '<p>Editor text</p>'): '<p>编辑文本</p>'}
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            directory = root / DIRECTORY
            directory.mkdir(parents=True)
            (directory / 'preview.json').write_text(json.dumps({'schema': 1, 'topics': {topic['id']: topic['version']}}))
            (directory / (topic['id'] + '.json')).write_text(json.dumps({'schema': 1, 'topic_id': topic['id'],
                'version': topic['version'], 'values': values}))
            display = LessonDisplay(root, topic)
            self.assertTrue(display.preview)
            self.assertEqual(display.question(question)['interaction']['correct_id'], 'square')
            self.assertEqual(display.question(question)['interaction']['options'][0]['html'], '<p>正方形</p>')
            self.assertEqual(display.question(question)['html'], '<p>选一种。</p>')
            self.assertEqual(question['html'], '<p>Choose one.</p>')
            editorial = {'title': '(Draft) Notes', 'html': '<p>Editor text</p>'}
            self.assertIs(display.introduction(editorial), editorial)
            newer = LessonDisplay(root, {**topic, 'version': 'newer'})
            self.assertFalse(newer.preview)
            self.assertIs(newer.question(question), question)

    def test_markup_binding_ignores_punctuation_changes_but_protects_attributes_and_formulas(self):
        source = '<p>See <span data-tex="x">x</span><img alt="shape" src="data:image/png;base64,WA=="></p>'
        signature = MarkupSignature(source).signature()
        self.assertEqual(signature, MarkupSignature(source.replace('See', '见')).signature())
        for changed in (source.replace('>x<', '>y<'), source.replace('src=', 'onerror='), source + '<script>alert(1)</script>'):
            self.assertNotEqual(signature, MarkupSignature(changed).signature())

    def test_ignores_svg_indentation_but_preserves_math_text_and_code(self):
        source = '<svg>\n  <path d></path> <text> </text></svg><pre>x\n  y</pre>'
        signature = MarkupSignature(source).signature()
        normalized = source.replace('\n  <path d>', '\n<path d="">')
        self.assertEqual(signature, MarkupSignature(normalized).signature())
        self.assertNotEqual(signature, MarkupSignature(normalized.replace('<text> </text>', '<text></text>')).signature())
        self.assertNotEqual(signature, MarkupSignature(normalized.replace('x\n  y', 'x\ny')).signature())
