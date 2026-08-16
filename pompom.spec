# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ["pompom.py"],
    pathex=[],
    binaries=[],
    datas=[
        ("images/red-card.png", "images"),
        ("images/checkbox_unchecked.png", "images"),
        ("images/checkbox_checked.png", "images"),
        ("images/checkbox_unchecked_disabled.png", "images"),
        ("images/checkbox_checked_disabled.png", "images"),
        ("sounds/ticktock.wav", "sounds"),
        ("sounds/ding.wav", "sounds"),
        ("LICENSE", "."),
    ],
    hiddenimports=["PySide6.QtMultimedia"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="pompom",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="pompom",
)
