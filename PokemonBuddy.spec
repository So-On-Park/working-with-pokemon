# PyInstaller spec for Pokemon Buddy.
# Run: python -m PyInstaller PokemonBuddy.spec --clean
#
# Output: dist/PokemonBuddy.exe — single-file Windows binary that boots
# without a console window. data/ and assets/ are created next to the .exe
# on first launch (see config.py's frozen-mode ROOT detection).

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=[],
    datas=[],  # User data dirs are created at runtime — nothing to bundle.
    hiddenimports=[
        # PySide6 plugins PyInstaller occasionally misses on first scan
        'PySide6.QtSvg',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Trim packages we never touch to keep the .exe small.
        'tkinter',
        'unittest',
        'pydoc',
        'pytest',
        'PIL',  # only used by the offline GIF optimizer (pokemon-maker/),
                # not by the runtime app.
    ],
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
    name='PokemonBuddy',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,           # windowed app — no terminal popup
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icon.ico',  # 메타몽(#0132) 트레이/실행 아이콘
)
