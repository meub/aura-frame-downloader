# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec file for Aura Frame Downloader GUI."""

import sys
from pathlib import Path

block_cipher = None

# Determine platform-specific settings
if sys.platform == 'darwin':
    icon_file = 'aura/gui/resources/icon.icns'
elif sys.platform == 'win32':
    icon_file = 'aura/gui/resources/icon.ico'
else:
    icon_file = None

# Check if icon exists, otherwise set to None
if icon_file and not Path(icon_file).exists():
    icon_file = None

a = Analysis(
    ['aura_gui.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='Aura Downloader',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

# macOS app bundle
if sys.platform == 'darwin':
    app = BUNDLE(
        exe,
        name='Aura Downloader.app',
        icon=icon_file,
        bundle_identifier='com.aura.downloader',
        info_plist={
            'CFBundleName': 'Aura Downloader',
            'CFBundleDisplayName': 'Aura Downloader',
            'CFBundleVersion': '2.0.0',
            'CFBundleShortVersionString': '2.0.0',
            'NSHighResolutionCapable': True,
        },
    )
