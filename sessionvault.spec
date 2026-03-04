# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for SessionVault
#
# Build:
#   pip install pyinstaller
#   pyinstaller sessionvault.spec
#
# Output: dist/SessionVault  (folder)  or  dist/SessionVault.exe  (Windows)

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ["sessionvault.py"],
    pathex=[str(Path(__file__).parent)],
    binaries=[],
    datas=[],
    hiddenimports=[
        # PySide6 plugin modules that PyInstaller may miss
        "PySide6.QtSvg",
        "PySide6.QtXml",
        # paramiko transports
        "paramiko",
        "paramiko.transport",
        "paramiko.auth_handler",
        "paramiko.sftp_client",
        # pykeepass
        "pykeepass",
        "pykeepass.entry",
        "pykeepass.group",
        # cryptography
        "cryptography.hazmat.backends.openssl",
        "cryptography.hazmat.primitives.kdf.pbkdf2",
        "cryptography.hazmat.primitives.kdf.argon2",
        # pynput (auto-type)
        "pynput",
        "pynput.keyboard",
        # application packages
        "app",
        "app.constants",
        "app.models",
        "app.theme",
        "app.managers.keepass",
        "app.managers.session",
        "app.managers.settings",
        "app.dialogs.keepass_open",
        "app.dialogs.keepass_selector",
        "app.dialogs.keepass_editor",
        "app.dialogs.new_session",
        "app.dialogs.settings",
        "app.importers.mobaxterm",
        "app.sftp.browser",
        "app.macros.manager",
        "app.macros.dialog",
        "app.plugins.loader",
        "app.terminal.ansi",
        "app.terminal.widget",
        "app.main",
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
    [],
    exclude_binaries=True,
    name="SessionVault",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,          # no console window on Windows/macOS
    disable_windowed_traceback=False,
    argv_emulation=False,   # macOS: set True if you need argv
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/icon.ico",   # uncomment and set your icon path
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="SessionVault",
)

# ── macOS .app bundle ─────────────────────────────────────────────────────────
if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="SessionVault.app",
        # icon="assets/icon.icns",
        bundle_identifier="com.sessionvault.app",
        info_plist={
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "12.0",
        },
    )
