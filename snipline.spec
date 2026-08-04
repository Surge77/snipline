# PyInstaller spec. Build with: pyinstaller snipline.spec
#
# --onedir, not --onefile (D10). A onefile build unpacks itself to a temp directory on every
# launch, adding seconds of startup to a tool whose entire value proposition is responding
# faster than the user can think about it.
#
# Qt module exclusion is not size trimming for its own sake: every excluded module is one
# fewer DLL to load at startup, and startup is on the critical path here.

from PyInstaller.utils.hooks import collect_submodules

APP_NAME = "Snipline"

# Regenerate with: python -m snipline.tools.make_icons
#
# This is a build-time input only. PyInstaller copies it into the executable's resource
# table, so the running application never opens it -- which is why having it does not
# reintroduce the missing-resource failure that every runtime glyph is drawn in code to
# avoid. It is deliberately absent from `datas`: shipping it alongside the exe would make it
# a runtime file again for no benefit.
ICON = "assets/snipline.ico"

# PySide6 pulls in the whole of Qt by default. None of these are imported anywhere in the
# source tree -- verified with grep before excluding them.
EXCLUDED_QT = [
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebChannel",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DRender",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtBluetooth",
    "PySide6.QtNfc",
    "PySide6.QtPositioning",
    "PySide6.QtSql",
    "PySide6.QtTest",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
]

EXCLUDED_OTHER = [
    "tkinter",
    "unittest",
    "pydoc_data",
    "pytest",
    "numpy.testing",
]

a = Analysis(
    ["src/snipline/app.py"],
    pathex=["src"],
    binaries=[],
    datas=[],
    # mss loads its Windows backend dynamically, so PyInstaller's static analysis does not
    # see it and the bundled app fails at the first capture without this.
    hiddenimports=collect_submodules("mss"),
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDED_QT + EXCLUDED_OTHER,
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,  # UPX-packed binaries are a common false positive for endpoint protection
    # console=False: this is a tray application. A console window appearing behind every
    # capture would be worse than useless.
    console=False,
    icon=ICON,
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
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)
