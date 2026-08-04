"""Render the mark to ``assets/`` for the build.

Run this, not a design tool, when the mark changes::

    python -m snipline.tools.make_icons

**The output is a build-time input, never a runtime one.** PyInstaller embeds the ``.ico``
into the executable's resource table, so the running application never opens it -- which is
what lets the project keep a real icon file without reintroducing the missing-resource
failure that every runtime glyph is drawn in code to avoid. Nothing under ``src/`` reads
``assets/``; the only consumers are ``snipline.spec`` and the README.

The file is committed rather than generated during the build, so that a fresh clone can run
``pyinstaller snipline.spec`` without a Qt display first. Regenerating it is this one
command, and the test suite checks it is not stale.

Qt is used for the drawing and Pillow only to assemble the multi-size container, because
QPixmap cannot write a multi-resolution ``.ico``.
"""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QIODevice
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication

from snipline.ui.mark import ICON_SIZES, app_tile_pixmap

__all__ = ["ICO_PATH", "PREVIEW_PATH", "main", "render_all"]

_REPO_ROOT = Path(__file__).resolve().parents[3]
ASSETS = _REPO_ROOT / "assets"
ICO_PATH = ASSETS / "snipline.ico"
PREVIEW_PATH = ASSETS / "icon-256.png"

_PREVIEW_SIZE = 256

_app: QApplication | None = None


def _png_bytes(pixmap: QPixmap) -> bytes:
    """Serialise a pixmap to PNG without going through the filesystem.

    ``QBuffer()`` with no argument, deliberately. Passing ``QBuffer(QByteArray())`` binds
    the buffer to a temporary that Python frees on the next line, and reading ``data()``
    afterwards segfaults the interpreter.
    """
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    buffer.close()
    return bytes(buffer.data().data())


def render_all(destination: Path = ASSETS) -> list[Path]:
    """Write the icon set. Returns the paths written."""
    from PIL import Image  # imported here: a build-time dependency, not a runtime one

    destination.mkdir(parents=True, exist_ok=True)

    frames = [
        Image.open(io.BytesIO(_png_bytes(app_tile_pixmap(size)))).convert("RGBA")
        for size in ICON_SIZES
    ]
    largest = max(frames, key=lambda image: image.width)
    ico = destination / ICO_PATH.name
    largest.save(ico, format="ICO", sizes=[(size, size) for size in ICON_SIZES])

    preview = destination / PREVIEW_PATH.name
    Image.open(io.BytesIO(_png_bytes(app_tile_pixmap(_PREVIEW_SIZE)))).save(preview)
    return [ico, preview]


def main() -> int:
    # The generator draws with Qt, which needs an application object but no display.
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    # Held, not dropped: destroying the QApplication while Qt still owns objects created
    # under it crashes on interpreter shutdown.
    global _app
    existing = QApplication.instance()
    _app = existing if isinstance(existing, QApplication) else QApplication([])
    for path in render_all():
        print(f"{path} ({path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
