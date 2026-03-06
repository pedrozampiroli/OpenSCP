# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['openscp/main.py'],
    pathex=[],
    binaries=[],
    datas=[('resources/themes', 'resources/themes'), ('resources/locales', 'resources/locales')],
    hiddenimports=['paramiko', 'cryptography', 'cffi', 'nacl'],
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
    name='OpenSCP',
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
    icon=['resources/icon/OpenSCPIcon.jpg'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='OpenSCP',
)
app = BUNDLE(
    coll,
    name='OpenSCP.app',
    icon='resources/icon/OpenSCPIcon.jpg',
    bundle_identifier='com.openscp.app',
)
