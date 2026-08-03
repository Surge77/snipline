"""Frame to image file.

Pillow rather than Qt for the file path: this runs with no ``QApplication``, which keeps
the capture CLI usable headlessly and keeps encoding out of the GUI thread later.

Two rules are enforced here rather than left to call sites:

- Alpha is dropped by default. GDI ``BitBlt`` -- what the real backend uses -- leaves the
  alpha byte at zero, so preserving it exports a fully transparent image. D8 already says
  export is flattened, so dropping alpha is the decision record, not a workaround.
- JPEG never receives an alpha channel, because Pillow raises on that combination and the
  user picking "JPEG" plus a capture with alpha is a legal pair of settings, not an error.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from snipline.capture.frame import Frame
from snipline.config import ExportFormat

__all__ = ["frame_to_image", "save_frame"]

DEFAULT_QUALITY = 92

# Pillow's raw decoder reorders the capture's native BGRA in C, avoiding a Python-level
# channel shuffle over several million pixels.
_RAW_MODE_WITH_ALPHA = "BGRA"
_RAW_MODE_OPAQUE = "BGRX"

_PILLOW_FORMAT = {
    ExportFormat.PNG: "PNG",
    ExportFormat.WEBP: "WEBP",
    ExportFormat.JPEG: "JPEG",
}


def frame_to_image(frame: Frame, *, keep_alpha: bool = False) -> Image.Image:
    """Wrap a captured BGRA buffer as a Pillow image in RGB (or RGBA) order."""
    if frame.rect.is_empty:
        raise ValueError(f"cannot encode an empty frame: {frame.rect}")

    mode = "RGBA" if keep_alpha else "RGB"
    raw_mode = _RAW_MODE_WITH_ALPHA if keep_alpha else _RAW_MODE_OPAQUE
    return Image.frombytes(
        mode,
        (frame.width, frame.height),
        frame.pixels,
        "raw",
        raw_mode,
        0,
        1,
    )


def save_frame(
    frame: Frame,
    destination: Path,
    *,
    export_format: ExportFormat = ExportFormat.PNG,
    quality: int = DEFAULT_QUALITY,
    keep_alpha: bool = False,
) -> Path:
    """Encode ``frame`` to ``destination``. Returns the path actually written."""
    if not 1 <= quality <= 100:
        raise ValueError(f"quality out of range: {quality}")

    image = frame_to_image(frame, keep_alpha=keep_alpha and export_format.supports_alpha)

    destination.parent.mkdir(parents=True, exist_ok=True)
    options: dict[str, object] = {}
    if export_format is not ExportFormat.PNG:
        options["quality"] = quality

    image.save(destination, format=_PILLOW_FORMAT[export_format], **options)
    return destination

