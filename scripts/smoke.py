"""Start the frozen app, render a real window, and verify native metadata."""
from __future__ import annotations

import os
import plistlib
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from s7sim import __version__


def main():
    if sys.platform == 'darwin':
        bundle = ROOT / 'dist/S7 Studio.app'
        with (bundle / 'Contents/Info.plist').open('rb') as stream:
            info = plistlib.load(stream)
        assert info['CFBundleShortVersionString'] == __version__, info
        assert info['CFBundleVersion'] == __version__, info
        executable = bundle / 'Contents/MacOS/S7 Studio'
    elif sys.platform == 'win32':
        executable = ROOT / 'dist/S7 Studio/S7 Studio.exe'
        version = subprocess.check_output(
            ['powershell', '-NoProfile', '-Command',
             f"(Get-Item -LiteralPath '{executable}').VersionInfo.ProductVersion"],
            text=True,
        ).strip()
        assert version == __version__, version
    else:
        raise SystemExit('Smoke test must run on macOS or Windows')
    image = ROOT / 'build/packaged-smoke.png'
    image.parent.mkdir(parents=True, exist_ok=True)
    image.unlink(missing_ok=True)
    env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
    subprocess.run([str(executable), '--theme', 'light', '--no-motion', '--screenshot', str(image)],
                   env=env, check=True, timeout=60)
    with image.open('rb') as stream:
        header = stream.read(24)
    assert header[:8] == b'\x89PNG\r\n\x1a\n', 'App did not render a PNG'
    width, height = struct.unpack('>II', header[16:24])
    assert width >= 800 and height >= 600, (width, height)
    print(f'Frozen app v{__version__} started and rendered {width}x{height}')


if __name__ == '__main__':
    main()
