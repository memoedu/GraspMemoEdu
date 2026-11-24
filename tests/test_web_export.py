import json
import hashlib
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class PublicExportTests(unittest.TestCase):
    def export(self, root, origin):
        output = root / 'web'
        result = subprocess.run(
            [sys.executable, '-m', 'graspmemoedu', '--data-dir', str(root / 'data'),
             'export-web', '--output', str(output), '--api-origin', origin],
            capture_output=True, text=True, encoding='utf-8')
        return result, output

    def test_public_export_has_only_static_assets_and_origin(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, output = self.export(Path(temporary), 'https://example.trycloudflare.com')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue({'training.js', 'training.css', 'training-messages.js', 'learning-ui.js'} <= {p.name for p in output.iterdir()})
            self.assertTrue((output / 'beginner-hints.js').is_file())
            self.assertTrue({'review-papers.js', 'review-paper-messages.js'} <= {p.name for p in output.iterdir()})
            self.assertTrue({'review-directory.js', 'task-tree.js', 'catalog-outline.js', 'content-timer.js'} <= {p.name for p in output.iterdir()})
            self.assertTrue((output / 'catalog-workspace.js').is_file())
            focus_files = {'focus-mode.js', 'focus-mode.css'}
            self.assertTrue(focus_files <= {p.name for p in output.iterdir()})
            pwa_files = {'download.html', 'install.css', 'pwa.css', 'pwa.js', 'sw.js', 'manifest.webmanifest',
                         'icon-180.png', 'icon-192.png', 'icon-512.png', 'icon-maskable-512.png',
                         'pwa-location.js', 'pwa-free-study', 'pwa-math-courses'}
            for directory in ('pwa-free-study', 'pwa-math-courses'):
                self.assertEqual({p.name for p in (output / directory).iterdir()},
                                 {'index.html', 'install.html', 'manifest.webmanifest'})
            pwa_files.update({'restore.html', 'migration-source.html', 'origin-transfer.js'})
            pwa_files.add('beginner-hints.js')
            pwa_files.update({'microphone-recorder.js', 'voice-input.js', 'voice-stream.js', 'voice-pcm.js', 'voice-context.js', 'answer-conversion.js'})
            pwa_files.update({'autocomplete.js', 'autocomplete.css'})
            pwa_files.add('free-study.js')
            pwa_files.update({'topic-sync-navigation.js', 'topic-sync-groups.js', 'topic-body-editor.js', 'remnote-install.html'})
            pwa_files.update({'clipper.js', 'clipper-workspace.js', 'clipper-library.js', 'clipper-selection.js',
                              'clipper-host.js', 'clipper-settings.js', 'clipper.css'})
            clipper = json.loads((Path(__file__).resolve().parents[1] / 'scripts/clipper-assets.json').read_bytes())
            runtime = output / 'vendor/knowledge-clipper'
            self.assertEqual(json.loads((output / 'vendor/clipper-release.json').read_bytes()), clipper)
            self.assertEqual({p.relative_to(runtime).as_posix() for p in runtime.rglob('*') if p.is_file()}, set(clipper['files']))
            for name, expected in clipper['files'].items():
                self.assertEqual(hashlib.sha256((runtime / name).read_bytes()).hexdigest(), expected, name)
            self.assertTrue((output / 'vendor/calculator/completion.mjs').is_file())
            pwa_files.update({'formula-input.js', 'formula-catalog.js', 'formula-input.css'})
            formula_assets = Path(__file__).resolve().parents[1] / 'scripts/formula-assets.json'
            for name, digest in json.loads(formula_assets.read_text(encoding='utf-8'))['files'].items():
                with self.subTest(asset=name):
                    self.assertEqual(hashlib.sha256((output / name).read_bytes()).hexdigest(), digest)
            pwa_files.update({'question-tools.js', 'math-syntax.js', 'calculator.js', 'calculator-panel.js', 'calculator-inputs.js', 'calculator-policy.js',
                              'calculator-engine.js', 'calculator-worker.js', 'calculator.css', 'whiteboard.js',
                              'whiteboard.css', 'whiteboard-archive.js', 'whiteboard-answer.js'})
            self.assertTrue(pwa_files <= {p.name for p in output.iterdir()})
            self.assertEqual({p.name for p in output.iterdir()} - pwa_files - focus_files - {'catalog-workspace.js', 'student-dashboard.js', 'presence.js', 'training.js', 'training.css', 'training-messages.js', 'learning-ui.js', 'review-papers.js', 'review-paper-messages.js', 'review-directory.js', 'task-tree.js', 'catalog-outline.js', 'content-timer.js', 'self-assessment.js', 'academy-messages.js', 'hyperskill.js', 'memory-chunk.js', 'point-assessment.js', 'context-library.js', 'context-library.css', 'context-library-messages.js', 'training-audio.js'},
                             {'.nojekyll', 'app.js', 'deployment.json', 'favicon.svg', 'index.html', 'portal.js', 'review.js', 'atomic.js','learning-cache.js', 'response-cache.js', 'question-input.js', 'composite-input.js', 'math-presentation.js', 'content-report.js', 'help-feedback.js', 'idea-setup.js', 'catalog-picker.js', 'portal.css', 'subjects.js', 'subjects.css', 'styles.css', 'i18n.js', 'reader-messages.js', 'portal-messages.js', 'static-messages.js', 'course-graph.js', 'course-graph.css', 'topic-content.js', 'topic-content.css', 'topic-callouts.css', 'vendor'})
            self.assertEqual(json.loads((output / 'deployment.json').read_text()),
                             {'api_origin': 'https://example.trycloudflare.com'})
            self.assertEqual((output / 'app.js').read_bytes(),
                             (Path(__file__).resolve().parents[1] / 'web/app.js').read_bytes())

    def test_invalid_or_credential_bearing_origins_fail_before_export(self):
        for origin in ['http://localhost:8767', 'https://name:secret@example.com',
                       'https://example.com/path', 'https://example.com?token=secret']:
            with self.subTest(origin=origin), tempfile.TemporaryDirectory() as temporary:
                result, output = self.export(Path(temporary), origin)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(output.exists())

    def test_local_export_has_empty_origin(self):
        with tempfile.TemporaryDirectory() as temporary:
            result, output = self.export(Path(temporary), '')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads((output / 'deployment.json').read_text()), {'api_origin': ''})


if __name__ == '__main__':
    unittest.main()
