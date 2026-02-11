# -*- mode: python ; coding: utf-8 -*-
"""
PyInstaller spec file for JustIRC GUI Client
Build with: pyinstaller justirc-gui.spec
"""

block_cipher = None

a = Analysis(
    ['client_gui.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('JUSTIRC-logo.png', '.'),
        ('README.md', '.'),
        ('THEMES.md', '.'),
    ],
    hiddenimports=[],
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
    name='JustIRC-GUI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,  # No console window for GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='JUSTIRC-logo.png' if os.path.exists('JUSTIRC-logo.png') else None,
)
