"""Publication contract: path-scoped PWA without offline learning mutations."""
import json
import unittest
from pathlib import Path
from urllib.parse import urljoin

WEB = Path(__file__).resolve().parents[1] / 'web'


class PwaTests(unittest.TestCase):
    def test_manifest_under_pages_subdirectory(self):
        manifest = json.loads((WEB / 'manifest.webmanifest').read_text(encoding='utf-8'))
        base = 'https://example.test/GraspMemoEdu-Pages/manifest.webmanifest'
        self.assertEqual(urljoin('https://example.test', manifest['id']), 'https://example.test/')
        self.assertEqual(manifest['start_url'], './')
        self.assertEqual(manifest['scope'], './')
        self.assertEqual(manifest['display'], 'standalone')
        for icon in manifest['icons']:
            path = WEB / icon['src']
            raw = path.read_bytes()
            self.assertEqual(raw[:8], b'\x89PNG\r\n\x1a\n')
            self.assertEqual(int.from_bytes(raw[16:20], 'big'), int(icon['sizes'].split('x')[0]))
        self.assertTrue(any(icon['purpose'] == 'maskable' for icon in manifest['icons']))

    def test_scoped_manifest_ids_and_entries_are_distinct(self):
        root = 'https://example.test/GraspMemoEdu-Pages/'
        ids = {'https://example.test/'}
        for app in ('free-study', 'math-courses'):
            with self.subTest(app=app):
                directory = WEB / f'pwa-{app}'
                base = urljoin(root, f'pwa-{app}/')
                manifest = json.loads((directory / 'manifest.webmanifest').read_text(encoding='utf-8'))
                identity = urljoin('https://example.test', manifest['id'])
                self.assertNotIn(identity, ids)
                ids.add(identity)
                self.assertEqual(urljoin(base, manifest['start_url']), base)
                self.assertEqual(urljoin(base, manifest['scope']), base)
                self.assertEqual(manifest['display'], 'standalone')
                for icon in manifest['icons']:
                    self.assertTrue((directory / icon['src']).is_file())
                for filename in ('index.html', 'install.html'):
                    page = (directory / filename).read_text(encoding='utf-8')
                    self.assertIn(f'data-pwa-app="{app}"', page)
                    self.assertIn('href="./manifest.webmanifest"', page)
                    self.assertIn('src="../pwa.js', page)
                    self.assertIn('href="../icon-180.png"', page)

    def test_entry_and_install_page_are_wired(self):
        for name in ('index.html', 'download.html'):
            text = (WEB / name).read_text(encoding='utf-8')
            self.assertIn('./manifest.webmanifest', text)
            self.assertIn('./pwa.js', text)
            self.assertIn('./icon-180.png', text)
        page = (WEB / 'download.html').read_text(encoding='utf-8')
        for target in ('ios', 'android', 'windows'):
            self.assertIn(f'id="{target}"', page)

