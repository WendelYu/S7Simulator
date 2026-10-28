"""Build on each target OS: python scripts/build.py.

Produces an application bundle on macOS and a portable folder on Windows,
plus an archive ready to copy to another machine of the same architecture.
"""
from __future__ import annotations

import os
import platform
import hashlib
import shutil
import struct
import subprocess
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QByteArray, QBuffer, QIODevice, QRectF
from PySide6.QtGui import QGuiApplication, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.release import release_version, package_prefix


def make_icon():
    app = QGuiApplication.instance() or QGuiApplication([])
    renderer = QSvgRenderer(str(ROOT / "s7sim/assets/icon.svg"))
    chunks = []
    pngs = {}
    for size in (128, 256, 512, 1024):
        image = QImage(size, size, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        data = QByteArray()
        stream = QBuffer(data)
        stream.open(QIODevice.OpenModeFlag.WriteOnly)
        image.save(stream, "PNG")
        pngs[size] = bytes(data)
    folder = ROOT / "build/icons"
    folder.mkdir(parents=True, exist_ok=True)
    if sys.platform == "darwin":
        for size, tag in ((128, b"ic07"), (256, b"ic08"), (512, b"ic09"), (1024, b"ic10")):
            png = pngs[size]
            chunks.append(tag + struct.pack(">I", len(png) + 8) + png)
        payload = b"".join(chunks)
        path = folder / "S7Studio.icns"
        path.write_bytes(b"icns" + struct.pack(">I", len(payload) + 8) + payload)
    else:
        png = pngs[256]
        path = folder / "S7Studio.ico"
        path.write_bytes(struct.pack("<HHH", 0, 1, 1) + struct.pack("<BBBBHHII", 0, 0, 0, 0, 1, 32, len(png), 22) + png)
    return path


def windows_version_file(version):
    numbers = tuple(int(part) for part in version.split('.')) + (0,)
    contents = f'''VSVersionInfo(
  ffi=FixedFileInfo(filevers={numbers!r}, prodvers={numbers!r}, mask=0x3f,
    flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'WendelYu'),
    StringStruct('FileDescription', 'S7 Studio PLC Simulator'),
    StringStruct('FileVersion', '{version}'),
    StringStruct('InternalName', 'S7 Studio'),
    StringStruct('OriginalFilename', 'S7 Studio.exe'),
    StringStruct('ProductName', 'S7 Studio'),
    StringStruct('ProductVersion', '{version}')
  ])]), VarFileInfo([VarStruct('Translation', [1033, 1200])])]
)'''
    path = ROOT / 'build/windows-version.txt'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(contents, encoding='utf-8')
    return path


def windows_installer(version):
    compiler = shutil.which('ISCC.exe') or shutil.which('iscc')
    if not compiler:
        candidates = []
        for key in ('ProgramFiles(x86)', 'ProgramFiles'):
            base = Path(os.environ.get(key, 'C:/Program Files (x86)'))
            candidates.extend(base.glob('Inno Setup */ISCC.exe'))
        compiler = str(sorted(candidates)[-1]) if candidates else None
    if not compiler:
        raise RuntimeError('Windows 安装包需要 Inno Setup 6：请先安装 Inno Setup 并重试。')
    subprocess.run([compiler, f'/DAppVersion={version}', f'/DProjectRoot={ROOT}',
                    str(ROOT / 'packaging/windows.iss')], check=True)
    return ROOT / 'dist' / f'{package_prefix(version, "win32", "x64")}-setup.exe'


def mac_disk_image(version, prefix):
    stage = ROOT / 'build/dmg' / prefix
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copytree(ROOT / 'dist/S7 Studio.app', stage / 'S7 Studio.app', symlinks=True)
    (stage / 'Applications').symlink_to('/Applications', target_is_directory=True)
    (stage / '安装说明.txt').write_text(
        (ROOT / 'docs/MAC_INSTALL.md').read_text(encoding='utf-8'), encoding='utf-8')
    image = ROOT / 'dist' / f'{prefix}.dmg'
    subprocess.run(['hdiutil', 'create', '-volname', f'S7 Studio {version}',
                    '-srcfolder', str(stage), '-ov', '-format', 'UDZO', str(image)], check=True)
    subprocess.run(['hdiutil', 'verify', str(image)], check=True)
    return image


def write_checksum(path):
    with path.open('rb') as stream:
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    path.with_name(path.name + '.sha256').write_text(f'{digest}  {path.name}\n', encoding='utf-8')


def main():
    if sys.platform not in {"darwin", "win32"}:
        raise SystemExit("Please build on macOS or Windows.")
    tag = os.environ.get('GITHUB_REF_NAME') if os.environ.get('GITHUB_REF_TYPE') == 'tag' else None
    version = release_version(tag)
    prefix = package_prefix(version, sys.platform, platform.machine())
    make_icon()
    if sys.platform == 'win32':
        windows_version_file(version)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean',
               '--distpath', str(ROOT / 'dist'), '--workpath', str(ROOT / 'build/pyinstaller'),
               str(ROOT / 'packaging/S7Studio.spec')]
    environment = dict(os.environ, PYINSTALLER_CONFIG_DIR=str(ROOT / "build/pyinstaller-cache"))
    subprocess.run(command, cwd=ROOT, env=environment, check=True)
    archive = ROOT / 'dist' / f'{prefix}.zip'
    outputs = [archive]
    if sys.platform == "darwin":
        subprocess.run(["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent", str(ROOT / "dist/S7 Studio.app"), str(archive)], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(ROOT / 'dist/S7 Studio.app')], check=True)
        outputs.append(mac_disk_image(version, prefix))
    else:
        shutil.make_archive(str(archive.with_suffix("")), "zip", ROOT / "dist", "S7 Studio")
        outputs.append(windows_installer(version))
    for output in outputs:
        if not output.is_file():
            raise RuntimeError(f'构建产物缺失：{output}')
        write_checksum(output)
        print(f'Build ready: {output}')


if __name__ == "__main__":
    main()
