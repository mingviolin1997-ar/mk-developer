"""Pages staging preserves current installs and never mutates its inputs."""
import hashlib
import json
import pathlib
import plistlib
import tempfile
import unittest

import prepare_download_routes as routes
try:
    import build_pages_stage as stage
except ModuleNotFoundError:
    stage = None

COMMIT = '1' * 40


class PagesStageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # macOS exposes its default temporary path through /var -> /private/var.
        # Resolve the fixture root; production still rejects supplied symlinks.
        self.root = pathlib.Path(self.tmp.name).resolve()
        self.source = self.root / 'docs'
        self.packages = self.source / 'test/packages'
        self.packages.mkdir(parents=True)
        self.output = self.root / 'work/pages-site'
        self.raw = {}
        for name in ('owner', 'friend', 'old'):
            (self.packages / f'{name}.ipa').write_bytes((name + '-signed-package').encode())
            manifest = {'items': [{'assets': [{'kind': 'software-package', 'url': f'{routes.ORIGIN}/test/packages/{name}.ipa'}], 'metadata': {'bundle-identifier': 'test.' + name, 'bundle-version': '7', 'kind': 'software', 'title': name}}]}
            self.raw[name] = plistlib.dumps(manifest)
            (self.packages / f'{name}.plist').write_bytes(self.raw[name])
        (self.source / 'test/index.html').write_text('<a id="friend" href="itms-services://?action=download-manifest&amp;url=https%3A%2F%2Fdev.mk-musician.com%2Ftest%2Fpackages%2Ffriend.plist">安装friend</a><form>register</form>')
        (self.source / 'test/owner-releases.json').write_text(json.dumps({'manifest': routes.ORIGIN + '/test/packages/owner.plist'}))
        (self.source / 'index.html').write_text('home preserved')

    def build(self, **kwargs):
        self.assertIsNotNone(stage, 'missing isolated Pages stage builder')
        return stage.build_stage(self.source, self.output, COMMIT, lambda p, c: c, **kwargs)

    def inventory(self):
        return {str(p.relative_to(self.source)): hashlib.sha256(p.read_bytes()).hexdigest()
                for p in self.source.rglob('*') if p.is_file()}

    def test_active_manifests_keep_bytes_history_keeps_paths_and_source_is_unchanged(self):
        before = self.inventory()
        result = self.build()
        self.assertEqual(self.inventory(), before)
        self.assertEqual((self.output / 'index.html').read_text(), 'home preserved')
        for name in ('owner', 'friend'):
            self.assertEqual((self.output / f'test/packages/{name}.plist').read_bytes(), self.raw[name])
            self.assertEqual((self.output / f'test/direct/{name}.plist').read_bytes(), self.raw[name])
            self.assertEqual((self.output / f'test/packages/{name}.ipa').read_bytes(), (self.packages / f'{name}.ipa').read_bytes())
        self.assertFalse((self.output / 'test/packages/old.ipa').exists())
        old = plistlib.loads((self.output / 'test/packages/old.plist').read_bytes())
        self.assertEqual(old['items'][0]['metadata'], plistlib.loads(self.raw['old'])['items'][0]['metadata'])
        self.assertEqual(old['items'][0]['assets'][0]['url'], f'https://raw.githubusercontent.com/mingviolin1997-ar/mk-developer/{COMMIT}/docs/test/packages/old.ipa')
        self.assertEqual((self.output / 'test/direct/old.plist').read_bytes(), (self.output / 'test/packages/old.plist').read_bytes())
        self.assertLessEqual(result['bytes'], 1_000_000_000)

    def test_relative_html_and_json_direct_ipa_links_stay_on_pages(self):
        (self.source / 'test/legacy.html').write_text('<a href="packages/old.ipa">download</a>')
        (self.source / 'test/direct-download.json').write_text(json.dumps({'ipa': '/test/packages/old.ipa'}))
        self.build()
        self.assertTrue((self.output / 'test/packages/old.ipa').exists())
        self.assertEqual((self.output / 'test/packages/old.plist').read_bytes(), self.raw['old'])

    def test_css_plist_class_is_not_an_installation_resource(self):
        (self.source / 'index.html').write_text('<style>h2{font-size:64px}.plist{color:red}</style>')
        self.build()
        self.assertEqual((self.output / 'index.html').read_bytes(), (self.source / 'index.html').read_bytes())

    def test_current_link_path_traversal_is_rejected(self):
        (self.source / 'test/link.html').write_text('<a href="/test/packages/../packages/old.ipa">install</a>')
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.output.exists())

    def test_output_cannot_overwrite_source_ancestor_existing_directory_or_symlink(self):
        before = self.inventory()
        for target in (self.source, self.root, self.source / 'nested', self.packages):
            self.output = target
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.build()
        link = self.root / 'link'
        link.symlink_to(self.root, target_is_directory=True)
        self.output = link / 'elsewhere'
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(self.inventory(), before)
        self.assertFalse((self.root / 'elsewhere').exists())
        self.output = self.root / 'existing'
        self.output.mkdir()
        (self.output / 'receipt.txt').write_text('keep')
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual((self.output / 'receipt.txt').read_text(), 'keep')

    def test_external_and_traversal_source_manifests_fail_before_stage_creation(self):
        for url in ('https://untrusted.invalid/private.ipa', routes.ORIGIN + '/test/packages/../private.ipa'):
            manifest = plistlib.loads(self.raw['old'])
            manifest['items'][0]['assets'][0]['url'] = url
            (self.packages / 'old.plist').write_bytes(plistlib.dumps(manifest))
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.build()
            self.assertFalse(self.output.exists())

    def test_over_budget_refuses_before_copy_and_preserves_source(self):
        before = self.inventory()
        with self.assertRaisesRegex(ValueError, 'budget'):
            self.build(max_bytes=10)
        self.assertFalse(self.output.exists())
        self.assertEqual(self.inventory(), before)

    def test_upload_size_gate_rejects_missing_or_symlinked_artifact(self):
        self.assertIsNotNone(stage)
        with self.assertRaises(ValueError):
            stage.assert_budget(self.output)
        self.build()
        (self.output / 'escape').symlink_to(self.packages / 'old.ipa')
        with self.assertRaises(ValueError):
            stage.assert_budget(self.output)

    def test_source_symlink_refused_before_copy(self):
        (self.source / 'escape').symlink_to(self.root, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.output.exists())

    def test_legacy_bare_download_map_and_browser_only_404_preserve_custom_page(self):
        (self.source / '404.html').write_text('existing custom error page')
        result = self.build()
        mapping = json.loads((self.output / 'test/historical-packages.json').read_text())
        self.assertEqual(mapping['/test/packages/old.ipa'], f'https://raw.githubusercontent.com/mingviolin1997-ar/mk-developer/{COMMIT}/docs/test/packages/old.ipa')
        self.assertEqual((self.output / '404.html').read_text(), 'existing custom error page')
        self.assertTrue(result['preservedCustom404'])

    def test_generated_404_provides_browser_compatibility_without_ipa_html_files(self):
        self.build()
        page = (self.output / '404.html').read_text()
        self.assertIn('historical-packages.json', page)
        self.assertIn('浏览器', page)
        self.assertFalse((self.output / 'test/packages/old.ipa').exists())

    def test_large_release_history_uses_official_asset_without_proxy(self):
        name = 'friends-voplus-1.0.0-70-five-friends.ipa'
        (self.packages / name).write_bytes(b'signed release')
        manifest = plistlib.loads(self.raw['old'])
        manifest['items'][0]['assets'][0]['url'] = routes.ORIGIN + '/test/packages/' + name
        (self.packages / 'old.plist').write_bytes(plistlib.dumps(manifest))
        self.build()
        old = plistlib.loads((self.output / 'test/packages/old.plist').read_bytes())
        self.assertEqual(old['items'][0]['assets'][0]['url'], 'https://github.com/mingviolin1997-ar/mk-developer/releases/download/voplus-1.0.0-70/' + name)


if __name__ == '__main__':
    unittest.main()
