import os
import sys

from PyInstaller.utils.hooks import collect_submodules

block_cipher = None

_PROJECT_ROOT = os.path.dirname(os.path.abspath(SPEC))

if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

hidden = []
hidden += collect_submodules("models")
hidden += collect_submodules("common")

a = Analysis(
    ['main.py'],
    pathex=[_PROJECT_ROOT],
    binaries=[],
    datas=[
        ('models/hv/assets/logo.png', 'models/hv/assets'),
        ('models/hv/assets/logo.ico', 'models/hv/assets'),
        ('models/hv/data', 'models/hv/data'),
        ('common/data', 'common/data'),
    ],
    hiddenimports=hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'unittest',
        'setuptools',
        'distutils',
        'tkinter.test',
        'IPython',
        'jupyter',
        'notebook',
        'numpy',
        'pandas',
        'scipy',
        'matplotlib',
        'flask',
        'django',
        'PyQt5',
        'PyQt6',
        'PySide2',
        'PySide6',
        'sphinx',
        'docutils',
    ],
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher
)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='HV Label Printer',
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
    icon='models/hv/assets/logo.ico'
)