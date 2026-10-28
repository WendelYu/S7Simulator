"""Validate release versions and collect only complete, verified artifacts."""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from s7sim import __version__


def release_version(tag=None):
    if not re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)', __version__):
        raise ValueError(f'版本号必须是 major.minor.patch：{__version__}')
    if any(int(n) > 65535 for n in __version__.split('.')):
        raise ValueError('版本号分段不能超过 Windows 版本资源上限 65535')
    if tag and tag != f'v{__version__}':
        raise ValueError(f'标签 {tag} 与项目版本 {__version__} 不一致；应使用 v{__version__}')
    return __version__


def package_prefix(version, system, machine):
    systems = {'darwin': 'macos', 'win32': 'windows'}
    arches = {'arm64': 'arm64', 'aarch64': 'arm64', 'amd64': 'x64', 'x86_64': 'x64', 'x64': 'x64'}
    if system not in systems or machine.lower() not in arches:
        raise ValueError(f'不支持的构建平台：{system}/{machine}')
    arch = arches[machine.lower()]
    if system == 'win32' and arch != 'x64':
        raise ValueError('当前 Windows 安装包仅支持 x64 构建')
    return f'S7Studio-v{version}-{systems[system]}-{arch}'


def expected_assets(version):
    result = []
    for arch in ('arm64', 'x64'):
        prefix = package_prefix(version, 'darwin', arch)
        result.extend([f'{prefix}.zip', f'{prefix}.dmg'])
    prefix = package_prefix(version, 'win32', 'x64')
    return result + [f'{prefix}.zip', f'{prefix}-setup.exe']


def verify_assets(folder, version):
    """Fail before publication on missing, extra, mismatched or damaged files."""
    folder = Path(folder)
    names = expected_assets(version)
    expected = set(names + [name + '.sha256' for name in names])
    actual = {p.name for p in folder.iterdir() if p.is_file()} - {'SHA256SUMS.txt'}
    if actual != expected:
        raise ValueError(f'发布附件不完整；缺失={sorted(expected - actual)}，额外={sorted(actual - expected)}')
    sums = []
    for name in sorted(names):
        path = folder / name
        if path.stat().st_size == 0:
            raise ValueError(f'附件为空：{name}')
        with path.open('rb') as stream:
            digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        line = f'{digest}  {name}'
        if (folder / f'{name}.sha256').read_text(encoding='utf-8').strip() != line:
            raise ValueError(f'SHA256 校验失败：{name}')
        sums.append(line)
    (folder / 'SHA256SUMS.txt').write_text('\n'.join(sums) + '\n', encoding='utf-8')
    return names


def release_notes(version):
    changelog = (ROOT / 'CHANGELOG.md').read_text(encoding='utf-8')
    match = re.search(rf'^## \[{re.escape(version)}\][^\n]*\n(.*?)(?=^## |\Z)', changelog, re.M | re.S)
    if not match:
        raise ValueError(f'CHANGELOG.md 缺少 {version} 的发布说明')
    template = (ROOT / 'docs/RELEASE_TEMPLATE.md').read_text(encoding='utf-8')
    return template.replace('@VERSION@', version).replace('@CHANGES@', match.group(1).strip())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tag', help='Must exactly match v + s7sim.__version__')
    parser.add_argument('--github-output', type=Path)
    parser.add_argument('--notes', type=Path)
    parser.add_argument('--verify-assets', type=Path)
    args = parser.parse_args()
    version = release_version(args.tag)
    notes = release_notes(version)  # Also require a changelog entry before building.
    if args.github_output:
        with args.github_output.open('a', encoding='utf-8') as stream:
            stream.write(f'version={version}\n')
    if args.notes:
        args.notes.parent.mkdir(parents=True, exist_ok=True)
        args.notes.write_text(notes, encoding='utf-8')
    if args.verify_assets:
        verify_assets(args.verify_assets, version)
    print(f'Release version: {version}')


if __name__ == '__main__':
    main()
