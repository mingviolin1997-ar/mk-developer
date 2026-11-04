"""Release routing must never change the app, device edition, or fallback bytes."""
import hashlib
import http.client
import io
import importlib.util
import pathlib
import plistlib
import tempfile
import unittest
from urllib.parse import quote

SPEC = importlib.util.spec_from_file_location('download_routes', pathlib.Path(__file__).with_name('prepare_download_routes.py'))
MODULE = importlib.util.module_from_spec(SPEC) if SPEC else None
if SPEC and SPEC.loader and pathlib.Path(SPEC.origin).exists():
    SPEC.loader.exec_module(MODULE)

COMMIT = '1' * 40
ORIGIN = 'https://dev.mk-musician.com'


def package_response(request, package):
    class Response(io.BytesIO):
        status = 200
        headers = {}
    data = package.read_bytes()
    response = Response(data[:8192] if 'Range' in request.headers else data)
    if 'Range' in request.headers:
        response.status = 206
        response.headers = {'Content-Range': f'bytes 0-{min(8192, len(data))-1}/{len(data)}'}
    return response

class DownloadRouteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.site = pathlib.Path(self.tmp.name) / 'docs'
        self.packages = self.site / 'test/packages'
        self.packages.mkdir(parents=True)
        self.originals = {}
        anchors = []
        for role in ('owner', 'friend'):
            (self.packages / f'{role}-7.ipa').write_bytes((role + '-signed-package').encode())
            manifest = {'items': [{'assets': [{'kind': 'software-package', 'url': f'{ORIGIN}/test/packages/{role}-7.ipa'}], 'metadata': {'bundle-identifier': f'test.{role}', 'bundle-version': '7', 'title': role, 'kind': 'software'}}]}
            raw = plistlib.dumps(manifest)
            self.originals[role] = raw
            (self.packages / f'{role}-7.plist').write_bytes(raw)
            href = 'itms-services://?action=download-manifest&url=' + quote(f'{ORIGIN}/test/packages/{role}-7.plist', safe='')
            anchors.append(f'<a id="{role}-install" href="{href.replace("&", "&amp;")}">安装 {role}</a>')
        self.page = '<html><body>' + ''.join(anchors) + '<form id="registration">registration unchanged</form></body></html>'
        (self.site / 'test/index.html').write_text(self.page)

    def build(self, verify):
        self.assertTrue(hasattr(MODULE, 'prepare_site'), '缺少经过校验且保留原线路的发布生成器')
        return MODULE.prepare_site(self.site, COMMIT, verify)

    def test_verified_routes_preserve_owner_friend_metadata_and_exact_fallback(self):
        verified = []
        def verify(path, commit):
            verified.append(path.name)
            return commit
        result = self.build(verify)
        self.assertEqual(len(result['accelerated']), 2)
        self.assertCountEqual(verified, ['owner-7.ipa', 'friend-7.ipa'])
        for role in ('owner', 'friend'):
            original = plistlib.loads(self.originals[role])
            self.assertEqual((self.packages / f'{role}-7.plist').read_bytes(), self.originals[role])
            routed = plistlib.loads((self.site / f'test/accelerated/{role}-7.plist').read_bytes())
            url = routed['items'][0]['assets'][0].pop('url')
            original['items'][0]['assets'][0].pop('url')
            self.assertEqual(routed, original)
            self.assertIn(f'/{COMMIT}/docs/test/packages/{role}-7.ipa', url)
            self.assertEqual((self.site / f'test/direct/{role}-7.plist').read_bytes(), self.originals[role])
        html = (self.site / 'test/index.html').read_text()
        self.assertIn('registration unchanged', html)
        self.assertIn('owner-install-accelerated', html)
        self.assertIn('friend-install-accelerated', html)
        self.assertIn('备用加速线路', html)
        self.assertNotIn('<details', html)
        for anchor in MODULE.ANCHOR.findall(self.page):
            self.assertIn(anchor, html)

    def test_failed_hash_verification_keeps_original_install_usable(self):
        def reject(path, commit):
            raise ValueError('checksum mismatch')
        result = self.build(reject)
        self.assertEqual(result['accelerated'], [])
        self.assertEqual(len(result['direct']), 2)
        for role, raw in self.originals.items():
            self.assertEqual((self.packages / f'{role}-7.plist').read_bytes(), raw)
            self.assertEqual((self.site / f'test/direct/{role}-7.plist').read_bytes(), raw)
        self.assertFalse((self.site / 'test/accelerated').exists())
        self.assertEqual((self.site / 'test/index.html').read_text(), self.page)

    def test_new_release_is_verified_and_never_reuses_old_package_mapping(self):
        old = plistlib.loads(self.originals['friend'])
        old['items'][0]['assets'][0]['url'] = f'{ORIGIN}/test/packages/friend-8.ipa'
        old['items'][0]['metadata']['bundle-version'] = '8'
        (self.packages / 'friend-8.ipa').write_bytes(b'new signed release')
        (self.packages / 'friend-7.plist').write_bytes(plistlib.dumps(old))
        visited = []
        self.build(lambda path, commit: visited.append(path.name) or commit)
        self.assertIn('friend-8.ipa', visited)
        routed = plistlib.loads((self.packages / 'friend-7.plist').read_bytes())
        self.assertTrue(routed['items'][0]['assets'][0]['url'].endswith('/friend-8.ipa'))
        self.assertEqual(routed['items'][0]['metadata']['bundle-version'], '8')

    def test_truncated_chunked_response_falls_back_without_blocking_publish(self):
        class Socket:
            def makefile(self, *args, **kwargs):
                return io.BytesIO(b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n10\r\nabc')
        def interrupted_response(*args, **kwargs):
            response = http.client.HTTPResponse(Socket())
            response.begin()
            return response
        cache = pathlib.Path(self.tmp.name) / 'cache'
        result = self.build(lambda path, commit: MODULE.verify_package(
            path, commit, cache, opener=interrupted_response))
        self.assertEqual(result['accelerated'], [])
        self.assertEqual(len(result['direct']), 2)
        self.assertTrue((self.site / 'test/download-routes.json').is_file())
        self.assertEqual(list(cache.glob('*.json')), [])
        for role, raw in self.originals.items():
            self.assertEqual((self.packages / f'{role}-7.plist').read_bytes(), raw)
            self.assertEqual((self.site / f'test/direct/{role}-7.plist').read_bytes(), raw)
        self.assertFalse((self.site / 'test/accelerated').exists())
        self.assertEqual((self.site / 'test/index.html').read_text(), self.page)

    def test_external_or_traversal_package_is_rejected_before_any_publish_write(self):
        for url in ('https://attacker.invalid/a.ipa', ORIGIN + '/test/packages/../../private.ipa',
                    ORIGIN + '/test/packages/%2e%2e/private.ipa', ORIGIN + '/test/packages/friend-7.ipa?x=1'):
            with self.subTest(url=url):
                original = plistlib.loads(self.originals['friend'])
                original['items'][0]['assets'][0]['url'] = url
                (self.packages / 'friend-7.plist').write_bytes(plistlib.dumps(original))
                self.assertTrue(hasattr(MODULE, 'prepare_site'), '缺少下载路由安全校验')
                with self.assertRaises(ValueError):
                    MODULE.prepare_site(self.site, COMMIT, lambda p, c: c)
                self.assertEqual((self.packages / 'owner-7.plist').read_bytes(), self.originals['owner'])
                self.assertFalse((self.site / 'test/direct').exists())
                self.assertFalse((self.site / 'test/accelerated').exists())
                self.assertEqual((self.site / 'test/index.html').read_text(), self.page)

    def test_corrupt_download_is_never_cached_as_verified(self):
        self.assertTrue(hasattr(MODULE, 'verify_package'), '缺少完整安装包校验')
        class Response(io.BytesIO):
            status = 200
        cache = pathlib.Path(self.tmp.name) / 'cache'
        with self.assertRaises(ValueError):
            MODULE.verify_package(self.packages / 'friend-7.ipa', COMMIT, cache,
                                  opener=lambda *a, **k: Response(b'corrupt bytes'))
        self.assertEqual(list(cache.glob('*.json')), [])

    def test_changed_package_requires_fresh_full_verification(self):
        self.assertTrue(hasattr(MODULE, 'verify_package'), '缺少新版本重新校验')
        package = self.packages / 'friend-7.ipa'
        cache = pathlib.Path(self.tmp.name) / 'cache'
        requests = []
        def open_package(request, **kwargs):
            requests.append(request)
            return package_response(request, package)
        MODULE.verify_package(package, COMMIT, cache, opener=open_package)
        package.write_bytes(b'changed release with same filename')
        fresh = '2' * 40
        self.assertEqual(MODULE.verify_package(package, fresh, cache, opener=open_package), fresh)
        self.assertEqual(len(requests), 4)
        self.assertNotIn('Range', requests[2].headers)
        self.assertIn('/' + fresh + '/', requests[-1].full_url)

    def test_historical_direct_link_survives_without_current_button(self):
        historical = self.packages / 'friend-6.plist'
        historical.write_bytes(self.originals['friend'])
        self.build(lambda path, commit: (_ for _ in ()).throw(OSError('offline')))
        self.assertEqual((self.site / 'test/direct/friend-6.plist').read_bytes(), self.originals['friend'])

    def test_partial_proxy_failure_keeps_every_default_and_only_verified_acceleration(self):
        def verify(path, commit):
            if path.name.startswith('friend'):
                raise OSError('offline')
            return commit
        self.build(verify)
        for role, raw in self.originals.items():
            self.assertEqual((self.packages / f'{role}-7.plist').read_bytes(), raw)
            self.assertEqual((self.site / f'test/direct/{role}-7.plist').read_bytes(), raw)
        self.assertTrue((self.site / 'test/accelerated/owner-7.plist').exists())
        self.assertFalse((self.site / 'test/accelerated/friend-7.plist').exists())
        page = (self.site / 'test/index.html').read_text()
        self.assertIn('owner-install-accelerated', page)
        self.assertNotIn('friend-install-accelerated', page)

    def test_first_full_hash_also_requires_range_before_receipt(self):
        package = self.packages / 'friend-7.ipa'
        cache = pathlib.Path(self.tmp.name) / 'cache'
        class NoRange(io.BytesIO):
            status = 200
            headers = {}
        with self.assertRaises(ValueError):
            MODULE.verify_package(package, COMMIT, cache,
                                  opener=lambda *a, **k: NoRange(package.read_bytes()))
        self.assertEqual(list(cache.glob('*')), [])

    def test_cached_hash_requires_fresh_valid_range(self):
        package = self.packages / 'friend-7.ipa'
        cache = pathlib.Path(self.tmp.name) / 'cache'
        MODULE.verify_package(package, COMMIT, cache, opener=lambda req, **kw: package_response(req, package))
        class BadRange(io.BytesIO):
            status = 206
            headers = {'Content-Range': 'bytes 0-3/4'}
        with self.assertRaises(ValueError):
            MODULE.verify_package(package, '2' * 40, cache, opener=lambda *a, **k: BadRange(b'bad!'))

    def test_parent_symlink_cannot_escape_stage(self):
        external = pathlib.Path(self.tmp.name) / 'external'
        self.packages.rename(external)
        self.packages.symlink_to(external, target_is_directory=True)
        with self.assertRaises(ValueError):
            self.build(lambda path, commit: commit)
        self.assertFalse((self.site / 'test/direct').exists())

class LargeReleaseTests(unittest.TestCase):
    def test_exact_large_release_route_only(self):
        name = 'friends-voplus-1.0.0-47-five-friends.ipa'
        self.assertEqual(MODULE.package_url(name, COMMIT), MODULE.PROXY + 'https://github.com/' + MODULE.REPO + '/releases/download/voplus-1.0.0-47/' + name)
        self.assertIn('/' + COMMIT + '/docs/', MODULE.package_url('friends-voplus-1.0.0-48-five-friends.ipa', COMMIT))

    def test_large_release_always_full_hash_checks(self):
        with tempfile.TemporaryDirectory() as d:
            p = pathlib.Path(d) / 'friends-voplus-1.0.0-47-five-friends.ipa'
            p.write_bytes(b'signed package')
            cache = pathlib.Path(d) / 'cache'
            calls = []
            class Response(io.BytesIO):
                status = 200
            def opener(req, **kwargs):
                calls.append(req)
                return package_response(req, p) if len(calls) <= 2 else Response(b'bad replacement')
            MODULE.verify_package(p, COMMIT, cache, opener=opener)
            with self.assertRaises(ValueError):
                MODULE.verify_package(p, COMMIT, cache, opener=opener)
            self.assertNotIn('Range', calls[-1].headers)

if __name__ == '__main__':
    unittest.main()
