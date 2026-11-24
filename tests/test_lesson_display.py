import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from graspmemoedu.lesson_display import DIRECTORY, LessonDisplay, display_hash, display_key
from graspmemoedu.lesson_display_install import MarkupSignature, repair_assets, validate_legacy_repairs, verify_topic
from graspmemoedu.mathacademy_formula_audit import audit_fields, validate_enrichment_rendering


class LessonDisplayTests(unittest.TestCase):
    def test_tex_repair_is_bound_to_the_exact_localized_field(self):
        topic = {'id': 'ma-topic-89', 'version': 'original', 'source_adapter': 'mathacademy'}
        source = r'<p>Vector $\mathbf x=</p>'
        translation = r'<p>向量 $\mathbf x=</p>'
        restored = '<p>向量 <span data-tex="x=2"><mjx-container></mjx-container></span></p>'
        key = display_key('html', source)
        question = {'title': 'Vector', 'html': source, 'reference_answer': 'preserve'}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / DIRECTORY / 'ma-topic-89.json'
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({'schema': 1, 'topic_id': topic['id'], 'version': topic['version'],
                'values': {key: translation}, 'tex_repairs': {key: {'before_sha256': display_hash(translation),
                    'html': restored}}}), encoding='utf-8')
            display = LessonDisplay(root, topic)
            self.assertEqual(display.question(question), {**question, 'html': restored})
            display.values = {key: translation.replace('向量', '初始向量')}
            self.assertEqual(display.question(question)['html'], display.values[key])
            self.assertEqual(question['html'], source)

    def test_formula_audit_visits_nested_html_and_preserves_literal_examples(self):
        structured = {'parts': [{'html': r'<p>代入 $\mathbf{x}_1=</p><span>随后</span>'},
            {'explanation_html': r'<pre>[math]a[/math] \frac</pre><p>Price $5 and $10.</p>'},
            {'html': r'<span data-tex="\frac{1}{2}"><mjx-container><svg></svg></mjx-container></span>'},
            {'html': '<svg><g data-mml-node="merror"></g></svg>'}]}
        self.assertEqual(list(audit_fields(structured)), [
            {'path': 'parts/0/html', 'defects': ['visible_tex_command']},
            {'path': 'parts/3/html', 'defects': ['mathjax_error']}])
        protected = '<aside><img src="x"></aside><span data-control="q1"></span><code>code</code>'
        self.assertEqual(repair_assets(protected + '<p>formula</p>'), repair_assets(protected))
        self.assertNotEqual(repair_assets(protected.replace('q1', 'q2')), repair_assets(protected))

    def test_tex_repair_can_carry_identical_archived_translation(self):
        tid = 'ma-topic-89'
        broken = r'<p>$\mathbf{x}=</p>'
        repair = '<p><span data-tex="x=2"><mjx-container></mjx-container></span></p>'
        key = display_key('html', broken)
        archived = display_key('html', 'Old question-bank revision')
        previous = {'schema': 1, 'topic_id': tid, 'version': 'same', 'values': {archived: '<p>旧的题型译文</p>'}}
        candidate = {**previous, 'tex_repairs': {key: {
            'before_sha256': display_hash(broken), 'markdown': '$x=2$', 'html': repair}}}
        catalog = SimpleNamespace(topics={tid: {'id': tid, 'version': 'same', 'modules': [],
            'introductions': [{'html': broken, 'title': 'Introduction'}]}})
        with tempfile.TemporaryDirectory() as directory, patch(
                'graspmemoedu.lesson_display_install.QuestionBank') as bank, patch(
                'graspmemoedu.mathacademy_import.Renderer') as renderer:
            bank.return_value.active_revision.return_value = None
            renderer.return_value.render.return_value = {'field': repair}
            path = Path(directory) / 'display.json'
            path.write_text(json.dumps(candidate), encoding='utf-8')
            verify_topic(path, tid, catalog, Path(directory), previous=previous)
            candidate['values'] = {archived: '<p>未经验证的覆盖</p>'}
            path.write_text(json.dumps(candidate), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'invalid source bindings'):
                verify_topic(path, tid, catalog, Path(directory), previous=previous)

    def test_activation_only_carries_identical_legacy_repairs_for_the_same_version(self):
        spec = {'topic_id': 'ma-topic-89', 'version': 'same', 'tex_repairs': {'old': {'html': '<p>archive</p>'}}}
        validate_legacy_repairs(spec, spec)
        for before in ({}, {**spec, 'version': 'other'}, {**spec, 'tex_repairs': {}}):
            with self.subTest(before=before), self.assertRaisesRegex(ValueError, 'read-only'):
                validate_legacy_repairs(spec, before)
        with self.assertRaisesRegex(ValueError, 'read-only'):
            validate_legacy_repairs({**spec, 'tex_repairs': {}}, spec)

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

    def test_new_revision_display_keeps_only_unchanged_archived_values(self):
        tid = 'ma-topic-90'
        archived = display_key('html', '<p>Old revision.</p>')
        source = '<p>Current revision.</p>'
        active = display_key('html', source)
        catalog = SimpleNamespace(topics={tid: {'id': tid, 'version': 'v1', 'modules': [],
            'introductions': [{'title': 'Lesson', 'html': source}]}})
        previous = {'schema': 1, 'topic_id': tid, 'version': 'v1', 'values': {archived: '<p>旧题。</p>'}}
        with tempfile.TemporaryDirectory() as directory, patch('graspmemoedu.lesson_display_install.QuestionBank') as bank:
            bank.return_value.active_revision.return_value = None
            path = Path(directory) / 'display.json'
            candidate = {**previous, 'values': {**previous['values'], active: '<p>新题。</p>'}}
            path.write_text(json.dumps(candidate), encoding='utf-8')
            verify_topic(path, tid, catalog, Path(directory), previous=previous)
            for invalid in (None, {**previous, 'version': 'v0'}, {**previous, 'values': {archived: '<p>异文。</p>'}}):
                with self.subTest(previous=invalid), self.assertRaisesRegex(ValueError, 'invalid source bindings'):
                    verify_topic(path, tid, catalog, Path(directory), previous=invalid)
            candidate['values'][active] = r'<p>\mathbf x</p>'
            path.write_text(json.dumps(candidate), encoding='utf-8')
            with self.assertRaisesRegex(ValueError, 'Unrendered math'):
                verify_topic(path, tid, catalog, Path(directory), previous=previous)

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

    def test_rejects_uncompiled_ma_diagrams_in_source_and_localization(self):
        code = '<pre><code class="language-mermaid">A --&gt; B</code></pre>'
        text = '<pre><code class="language-text">A --&gt; B</code></pre>'
        topic = {'id': 'ma-topic-1', 'introductions': [{'title': 'Example', 'html': text}], 'modules': []}
        key = display_key('html', text)
        validate_enrichment_rendering(topic, {'values': {}})
        with self.assertRaisesRegex(ValueError, 'uncompiled_diagram'):
            validate_enrichment_rendering(topic, {'values': {key: code.replace('mermaid', 'ma-drawing')}})
        topic['introductions'][0]['html'] = code
        with self.assertRaisesRegex(ValueError, 'uncompiled_diagram'):
            validate_enrichment_rendering(topic, {'values': {}})

    def test_rejects_variant_calculator_metadata_before_installation(self):
        variant = {'id': 'example-variant-1', 'answer_type': 'source-mathacademy-variant', 'html': '<p>Find x.</p>'}
        intro = {'title': 'Example', 'html': '<p>Calculator: None</p>'}
        topic = {'id': 'ma-topic-1', 'introductions': [intro],
                 'modules': [{'title': 'Example', 'example': {}, 'practices': [variant]}]}
        key = display_key('html', variant['html'])
        validate_enrichment_rendering(topic, {'values': {}})
        with self.assertRaisesRegex(ValueError, 'Calculator metadata'):
            validate_enrichment_rendering(topic, {'values': {key: '<p>求 x。</p><p>Calculator: 无</p>'}})
        variant['html'] += '<p>Calculator: None</p>'
        with self.assertRaisesRegex(ValueError, 'Calculator metadata'):
            validate_enrichment_rendering(topic, {'values': {}})
