# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec file for EtherLog.
#
# Build command (from the project root):
#   pyinstaller etherlog.spec
#
# The output single-file executable appears in dist/.

import sys
from pathlib import Path

block_cipher = None

# ---------------------------------------------------------------------------
# Hidden imports
#
# keyring uses runtime plugin discovery via importlib.metadata entry_points,
# which PyInstaller cannot detect statically.  We list the backends that each
# platform actually ships so the packaged binary can still load them.
#
# platformdirs is pulled in transitively but named explicitly for safety.
# ---------------------------------------------------------------------------

_keyring_hidden = [
    "platformdirs",
    # UI modules imported lazily inside methods (function-level imports),
    # which PyInstaller's static analysis can otherwise miss.
    "ui.label",
    "ui.send_dialog",
    "ui.theme",
    # Windows – uses the Windows Credential Manager
    "keyring.backends.Windows",
    # macOS – uses the macOS Keychain
    "keyring.backends.macOS",
    # Linux – uses the SecretService D-Bus API (GNOME Keyring / KWallet)
    "keyring.backends.SecretService",
    # Fallback file-based backend (always available, no external dependencies)
    "keyring.backends.fail",
    "keyring.backends.null",
]

a = Analysis(
    ["main.py"],
    pathex=[str(Path(".").resolve())],
    binaries=[],
    datas=[],
    hiddenimports=_keyring_hidden,
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
    name="etherlog",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # No console window on Windows / macOS
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # On macOS you can set icon="icon.icns"; on Windows "icon.ico"
)
