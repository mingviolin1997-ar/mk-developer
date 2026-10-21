#!/usr/bin/env python3
"""Build verified accelerated IPA manifests; keep the source and original route intact."""
import argparse
import datetime
import hashlib
import html
import http.client
from html.parser import HTMLParser
import json
import pathlib
import plistlib
import re
import subprocess
import urllib.parse
import urllib.request

ORIGIN = 'https://dev.mk-musician.com'
PROXY = 'https://gh-proxy.com/'
REPO = 'mingviolin1997-ar/mk-developer'
ANCHOR = re.compile(r'<a\b[^>]*>.*?</a>', re.I | re.S)
COMMIT = re.compile(r'[0-9a-f]{40}')
# Signed IPA exceeds Git's file limit; deployment verifies its pinned SHA-256.
LARGE_RELEASES = {'friends-voplus-1.0.0-47-five-friends.ipa': 'voplus-1.0.0-47', 'friends-voplus-1.0.0-50-five-friends.ipa': 'voplus-1.0.0-50'}


def package_url(name, commit):
    if not COMMIT.fullmatch(commit):
        raise ValueError('invalid immutable source commit')
    if name in LARGE_RELEASES:
        return f'{PROXY}https://github.com/{REPO}/releases/download/{LARGE_RELEASES[name]}/{name}'
    return f'{PROXY}https://raw.githubusercontent.com/{REPO}/{commit}/docs/test/packages/{name}'


class HTTPSRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != 'https' or target.netloc not in ('gh-proxy.com',):
            raise ValueError('accelerator redirected outside its verified HTTPS route')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_download(request, **kwargs):
    return urllib.request.build_opener(HTTPSRedirect()).open(request, **kwargs)


def file_hash(path):
    digest = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def verify_package(package, commit, cache_dir, opener=open_download):
    """Reuse only an exact file's full-hash receipt, with a fresh range probe."""
    expected = file_hash(package)
    size = package.stat().st_size
    key = cache_dir / f'{expected}.json'
    receipt = {}
    if key.exists():
        try:
            receipt = json.loads(key.read_text())
        except (ValueError, OSError):
            pass
    cached = (package.name not in LARGE_RELEASES and receipt.get('sha256') == expected and receipt.get('bytes') == size
              and receipt.get('filename') == package.name
              and COMMIT.fullmatch(str(receipt.get('commit', ''))))
    if cached:
        pinned = receipt['commit']
        count = min(8192, size)
        request = urllib.request.Request(package_url(package.name, pinned), headers={
            'Accept-Encoding': 'identity', 'Range': f'bytes=0-{count-1}',
            'User-Agent': 'MK-Download-Verification/1.0'})
        with opener(request, timeout=20) as response:
            sample = response.read(count + 1)
            if response.status != 206 or response.headers.get('Content-Range') != f'bytes 0-{count-1}/{size}':
                raise ValueError('accelerator did not honor the expected byte range')
        with package.open('rb') as source:
            if sample != source.read(count):
                raise ValueError('accelerator range differs from the signed package')
        return pinned

    digest = hashlib.sha256()
    received = 0
    request = urllib.request.Request(package_url(package.name, commit), headers={
        'Accept-Encoding': 'identity', 'User-Agent': 'MK-Download-Verification/1.0'})
    with opener(request, timeout=60) as response:
        if response.status != 200:
            raise ValueError('full package download did not return HTTP 200')
        for block in iter(lambda: response.read(1024 * 1024), b''):
            received += len(block)
            if received > size:
                raise ValueError('accelerator returned more than the expected package size')
            digest.update(block)
    if received != size or digest.hexdigest() != expected:
        raise ValueError('accelerator package checksum or size mismatch')
    receipt = {'filename': package.name, 'commit': commit, 'sha256': expected,
               'bytes': size, 'verifiedAt': datetime.datetime.now(datetime.timezone.utc).isoformat()}
    cache_dir.mkdir(parents=True, exist_ok=True)
    temporary = key.with_suffix('.tmp')
    temporary.write_text(json.dumps(receipt, sort_keys=True) + '\n')
    temporary.replace(key)
    return commit


class AnchorAttributes(HTMLParser):
    def __init__(self, value):
        super().__init__()
        self.attrs = {}
        self.feed(value)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.attrs = dict(attrs)


def local_package_path(site, url, suffix):
    target = urllib.parse.urlsplit(url)
    if target.scheme != 'https' or target.netloc != urllib.parse.urlsplit(ORIGIN).netloc or target.query or target.fragment:
        raise ValueError('installation resource must stay on the existing source host')
    pattern = r'/test/packages/([A-Za-z0-9_-][A-Za-z0-9_.-]*' + re.escape(suffix) + r')'
    match = re.fullmatch(pattern, target.path)
    if not match:
        raise ValueError('unexpected installation resource path')
    path = site / target.path.lstrip('/')
    if path.is_symlink() or not path.is_file():
        raise ValueError('installation resource is missing or is a symlink')
    return path


def prepare_site(site, commit, verify):
    page_path = site / 'test/index.html'
    page = page_path.read_text()
    manifests = {}
    links = {}
    # Validate every target before writing any generated manifest or HTML.
    for match in ANCHOR.finditer(page):
        attrs = AnchorAttributes(match.group()).attrs
        href = attrs.get('href', '')
        if not href.startswith('itms-services://'):
            continue
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(href).query)
        if query.get('action') != ['download-manifest'] or len(query.get('url', [])) != 1:
            raise ValueError('unexpected install link')
        source = local_package_path(site, query['url'][0], '.plist')
        links[match.group()] = (source, attrs)
        if source in manifests:
            continue
        raw = source.read_bytes()
        manifest = plistlib.loads(raw)
        if len(manifest.get('items', [])) != 1:
            raise ValueError('expected one signed app per installation manifest')
        assets = [asset for asset in manifest['items'][0]['assets'] if asset.get('kind') == 'software-package']
        if len(assets) != 1:
            raise ValueError('expected one signed IPA per installation manifest')
        package = local_package_path(site, assets[0]['url'], '.ipa')
        manifests[source] = (raw, manifest, assets[0], package)

    result = {'accelerated': [], 'direct': []}
    ready = {}
    for source, (raw, manifest, asset, package) in manifests.items():
        try:
            pinned = verify(package, commit)
            url = package_url(package.name, pinned)
        except (OSError, ValueError, http.client.HTTPException) as error:
            result['direct'].append({'manifest': source.name, 'reason': str(error)})
            continue
        asset['url'] = url
        ready[source] = (raw, plistlib.dumps(manifest, sort_keys=False))
        result['accelerated'].append({'manifest': source.name, 'package': package.name,
                                      'sha256': file_hash(package), 'bytes': package.stat().st_size,
                                      'sourceCommit': pinned, 'url': url})

    for source, (raw, accelerated) in ready.items():
        fallback = site / 'test/direct' / source.name
        fallback.parent.mkdir(parents=True, exist_ok=True)
        fallback.write_bytes(raw)
        source.write_bytes(accelerated)

    def add_original(match):
        info = links.get(match.group())
        if not info or info[0] not in ready:
            return match.group()
        source, attrs = info
        label = html.unescape(re.sub('<[^>]+>', '', match.group()))
        fallback = f'{ORIGIN}/test/direct/{source.name}'
        href = 'itms-services://?action=download-manifest&url=' + urllib.parse.quote(fallback, safe='')
        identity = html.escape(attrs.get('id', source.stem) + '-original', quote=True)
        return (match.group() + '<details class="meta download-help">'
                f'<summary aria-label="{html.escape(label + '，下载遇到问题？', quote=True)}">下载遇到问题？</summary>'
                f'<p><a id="{identity}" href="{html.escape(href, quote=True)}" '
                f'aria-label="{html.escape(label + '，原线路备用安装', quote=True)}">使用备用线路安装</a></p></details>')

    if ready:
        page_path.write_text(ANCHOR.sub(add_original, page))
    (site / 'test/download-routes.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=pathlib.Path, default=pathlib.Path('docs'))
    parser.add_argument('--cache-dir', type=pathlib.Path, default=pathlib.Path.home() / '.cache/mk-download-routes')
    args = parser.parse_args()
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    result = prepare_site(args.site, commit, lambda package, source: verify_package(package, source, args.cache_dir))
    print(json.dumps({'accelerated': len(result['accelerated']), 'direct': result['direct']}, ensure_ascii=False))


if __name__ == '__main__':
    main()
