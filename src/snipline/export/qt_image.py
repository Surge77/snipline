"""Saving Qt-rendered images.

Separate from ``encode.py`` because the two carry different payloads. A captured Frame is
raw BGRA and goes through Pillow; the flattened editor output is already a QImage, and
routing it back through raw bytes would cost a full copy of a 4K image for nothing.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import cast

from PySide6.QtGui import QImage

from snipline.config import ExportFormat
from snipline.export.encode import DEFAULT_QUALITY

__all__ = ["save_image"]

_QT_FORMAT = {
    ExportFormat.PNG: "PNG",
    ExportFormat.WEBP: "WEBP",
    ExportFormat.JPEG: "JPEG",
}


def save_image(
    image: QImage,
    destination: Path,
    *,
    export_format: ExportFormat = ExportFormat.PNG,
    quality: int = DEFAULT_QUALITY,
) -> Path:
    """Encode a rendered image to ``destination``. Returns the path written."""
    if not 1 <= quality <= 100:
        raise ValueError(f"quality out of range: {quality}")
    if image.isNull():
        raise ValueError("cannot save a null image")

    destination.parent.mkdir(parents=True, exist_ok=True)
    # PySide6 6.11's stub types `format` as bytes, but the runtime rejects bytes and
    # accepts str. Following the stub here produces a ValueError on every save.
    save = cast("Callable[[str, str, int], bool]", image.save)
    saved = save(str(destination), _QT_FORMAT[export_format], quality)
    if not saved:
        # Qt reports failure as a bool; without this the caller gets a silent no-op and a
        # success notification naming a file that does not exist.
        raise OSError(f"could not write {destination}")
    return destination
