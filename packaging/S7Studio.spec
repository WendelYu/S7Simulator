# -*- mode: python ; coding: utf-8 -*-
"""Native PyInstaller build; the app name stays stable across upgrades."""
import sys
from pathlib import Path

root = Path(SPECPATH).parent
sys.path.insert(0, str(root))
from s7sim import __version__

is_mac = sys.platform == 'darwin'
icon = str(root / 'build/icons' / ('S7Studio.icns' if is_mac else 'S7Studio.ico'))
a = Analysis(
    [str(root / 'run.py')],
    pathex=[str(root)],
    datas=[(str(root / 's7sim/assets'), 's7sim/assets')],
    excludes=['PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtQml', 'PySide6.QtQuick', 'pytest'],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [], exclude_binaries=True, name='S7 Studio',
    console=False, upx=False, icon=icon,
    version=str(root / 'build/windows-version.txt') if not is_mac else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name='S7 Studio', upx=False)
if is_mac:
    app = BUNDLE(
        coll, name='S7 Studio.app', icon=icon,
        bundle_identifier='studio.s7sim.desktop',
        info_plist={
            'CFBundleShortVersionString': __version__,
            'CFBundleVersion': __version__,
            'NSHighResolutionCapable': True,
            'LSMinimumSystemVersion': '14.0',
        },
    )
