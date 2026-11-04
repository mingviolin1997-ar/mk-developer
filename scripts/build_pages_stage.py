#!/usr/bin/env python3
"""Build a bounded Pages artifact without modifying source files or signed IPAs."""
import argparse
from html.parser import HTMLParser
import json
import pathlib
import plistlib
import re
import shutil
import subprocess
import urllib.parse

import prepare_download_routes as routes

MAX_BYTES = 1_000_000_000


class HTMLResources(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.values = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.values.extend(value for key, value in attrs if value is not None)


def json_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from json_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from json_strings(item)


def archive_url(name, commit):
    # Reuse the exact release/tag mapping, dropping only the optional proxy.
    return routes.package_url(name, commit).removeprefix(routes.PROXY)


def checked_paths(source, output):
    source, output = source.absolute(), output.absolute()
    for path in (source, output):
        if any(part.is_symlink() for part in (path, *path.parents)):
            raise ValueError('source and output paths must not contain symlinks')
    source, output = source.resolve(), output.resolve()
    if not source.is_dir():
        raise ValueError('source must be an existing directory')
    if source == output or source in output.parents or output in source.parents:
        raise ValueError('output must be separate from source and its ancestors')
    if output.exists():
        raise ValueError('output must be a new directory; existing data is never removed')
    return source, output


def active_resources(source, files):
    active = set()
    for path in files:
        if path.suffix.lower() not in ('.html', '.json'):
            continue
        text = path.read_text()
        candidates = HTMLResources(text).values if path.suffix.lower() == '.html' else json_strings(json.loads(text))
        base = routes.ORIGIN + '/' + path.relative_to(source).as_posix()
        for value in candidates:
            candidate = urllib.parse.unquote(value)
            if not re.search(r'\.(?:ipa|plist)(?:[?#].*)?$', candidate, re.I):
                continue
            if candidate.startswith('itms-services://'):
                query = urllib.parse.parse_qs(urllib.parse.urlsplit(candidate).query)
                if query.get('action') != ['download-manifest'] or len(query.get('url', [])) != 1:
                    raise ValueError('invalid current installation link')
                candidate = query['url'][0]
            if '..' in urllib.parse.urlsplit(candidate).path.split('/'):
                raise ValueError('installation resource path traversal is not allowed')
            url = urllib.parse.urljoin(base, candidate)
            target = urllib.parse.urlsplit(url)
            if target.netloc != urllib.parse.urlsplit(routes.ORIGIN).netloc:
                continue  # Existing external download links are preserved verbatim.
            suffix = pathlib.PurePosixPath(target.path).suffix.lower()
            resource = routes.local_package_path(source, url, suffix)
            active.add(resource.name)
    return active


def tree_bytes(root):
    return sum(path.stat().st_size for path in root.rglob('*') if path.is_file())


def assert_budget(root, max_bytes=MAX_BYTES):
    root = pathlib.Path(root).absolute()
    if not root.is_dir() or any(part.is_symlink() for part in (root, *root.parents)):
        raise ValueError('Pages artifact must be an existing directory without symlinks')
    if any(path.is_symlink() for path in root.rglob('*')):
        raise ValueError('Pages artifact must not contain symlinks')
    size = tree_bytes(root)
    if size > max_bytes:
        raise ValueError(f'Pages artifact exceeds byte budget: {size} > {max_bytes}')
    return size


def build_stage(source, output, commit, verify, max_bytes=MAX_BYTES):
    source, output = checked_paths(pathlib.Path(source), pathlib.Path(output))
    if not routes.COMMIT.fullmatch(commit):
        raise ValueError('invalid immutable source commit')
    files = []
    for path in source.rglob('*'):
        if path.is_symlink():
            raise ValueError('source contains a symlink')
        if path.is_file():
            files.append(path)
            if path.suffix.lower() == '.ipa':
                if path.parent != source / 'test/packages':
                    raise ValueError('IPA outside the supported package directory')
                routes.local_package_path(source, routes.ORIGIN + '/test/packages/' + path.name, '.ipa')
    active = active_resources(source, files)
    manifests = {}
    for path in sorted((source / 'test/packages').glob('*.plist')):
        routes.local_package_path(source, routes.ORIGIN + '/test/packages/' + path.name, '.plist')
        manifest = plistlib.loads(path.read_bytes())
        if len(manifest.get('items', [])) != 1:
            raise ValueError('expected one app in source manifest')
        assets = [asset for asset in manifest['items'][0]['assets'] if asset.get('kind') == 'software-package']
        if len(assets) != 1:
            raise ValueError('expected one signed package in source manifest')
        package = routes.local_package_path(source, assets[0]['url'], '.ipa')
        manifests[path.name] = (manifest, assets[0], package.name)
        if path.name in active:
            active.add(package.name)
    copied = [path for path in files if path.suffix.lower() != '.ipa' or path.name in active]
    planned_bytes = sum(path.stat().st_size for path in copied)
    if planned_bytes > max_bytes:
        raise ValueError(f'Pages artifact exceeds byte budget before copying: {planned_bytes} > {max_bytes}')
    # No mutation of source, no replacing/deleting an existing stage. A failed
    # stage is retained for diagnosis and can never reach the upload step.
    output.mkdir(parents=True, exist_ok=False)
    for path in copied:
        target = output / path.relative_to(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    route_result = routes.prepare_site(output, commit, verify, package_source=source)
    mapping = {}
    for path in files:
        if path.suffix.lower() == '.ipa' and path.name not in active:
            mapping['/test/packages/' + path.name] = archive_url(path.name, commit)
    for name, (manifest, asset, package_name) in manifests.items():
        if package_name in active:
            continue
        asset['url'] = archive_url(package_name, commit)
        raw = plistlib.dumps(manifest, sort_keys=False)
        (output / 'test/packages' / name).write_bytes(raw)
        (output / 'test/direct' / name).write_bytes(raw)
    (output / 'test/historical-packages.json').write_text(json.dumps(mapping, ensure_ascii=False, indent=2) + '\n')
    custom_404 = (output / '404.html').exists()
    if not custom_404:
        (output / '404.html').write_text('''<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>查找下载文件</title><main><h1>查找下载文件</h1>
<p id="status" role="status">正在查找原下载地址。</p>
<p><a id="download" hidden>下载原安装包</a></p>
<p>旧安装包可通过此浏览器页面下载。安装应用请使用朋友测试页面中的安装按钮。</p>
<p><a href="/test/">返回朋友测试页面</a></p></main>
<script>
fetch('/test/historical-packages.json').then(r => { if (!r.ok) throw Error(); return r.json(); }).then(map => {
  const url = map[location.pathname];
  if (!url) throw Error();
  const a = document.getElementById('download'); a.href = url; a.hidden = false;
  document.getElementById('status').textContent = '已找到原安装包，请使用下面的下载链接。';
}).catch(() => { document.getElementById('status').textContent = '未找到此文件，请返回朋友测试页面。'; });
</script></html>
''')
    result = {'sourceCommit': commit, 'activePackages': sorted(name for name in active if name.endswith('.ipa')),
              'historicalPackages': len(mapping), 'preservedCustom404': custom_404,
              'accelerated': len(route_result['accelerated']), 'bytes': assert_budget(output, max_bytes)}
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=pathlib.Path, default=pathlib.Path('docs'))
    parser.add_argument('--output', type=pathlib.Path, default=pathlib.Path('work/pages-site'))
    parser.add_argument('--cache-dir', type=pathlib.Path, default=pathlib.Path.home() / '.cache/mk-download-routes')
    parser.add_argument('--check-size', type=pathlib.Path)
    args = parser.parse_args()
    if args.check_size:
        print(json.dumps({'bytes': assert_budget(args.check_size), 'maxBytes': MAX_BYTES}))
        return
    commit = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    result = build_stage(args.source, args.output, commit,
                         lambda p, c: routes.verify_package(p, c, args.cache_dir))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
