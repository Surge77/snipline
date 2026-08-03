"""Captured frame to the system clipboard.

``QImage.Format_RGB32`` is byte-for-byte the capture's native BGRA on little-endian
machines, so the conversion is a reinterpretation rather than a per-pixel loop -- which
matters on a 4K capture sitting in the hotkey-to-clipboard path.

The buffer is copied deliberately. A ``QImage`` built over a Python ``bytes`` does not own
that memory, and the real backend's buffer belongs to mss and is reused on the next grab;
handing Qt a view of it would put freed or overwritten pixels on the clipboard.

Alpha is ignored rather than carried. GDI leaves the alpha byte at zero, and the standard
Windows ``CF_DIB`` clipboard format discards alpha anyway -- see the M6 note in PLAN.md
about registering PNG as a clipboard format if transparency ever needs to survive.
"""

from __future__ import annotations

from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from snipline.capture.frame import BYTES_PER_PIXEL, Frame

__all__ = ["copy_to_clipboard", "frame_to_qimage"]


def frame_to_qimage(frame: Frame) -> QImage:
    """Wrap a captured BGRA buffer as an owned, opaque QImage."""
    if frame.rect.is_empty:
        raise ValueError(f"cannot convert an empty frame: {frame.rect}")

    view = QImage(
        frame.pixels,
        frame.width,
        frame.height,
        frame.width * BYTES_PER_PIXEL,
        QImage.Format.Format_RGB32,
    )
    # copy() detaches from the Python buffer, which Qt does not keep alive.
    return view.copy()


def copy_to_clipboard(frame: Frame) -> bool:
    """Put the frame on the clipboard. False when no clipboard is available."""
    # Guarding on the application rather than on clipboard(): Qt's own type says the
    # clipboard is never None, but calling it without a running application aborts.
    if QApplication.instance() is None:
        return False

    QApplication.clipboard().setImage(frame_to_qimage(frame))
    return True
