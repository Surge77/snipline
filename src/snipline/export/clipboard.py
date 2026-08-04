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


def frame_to_qimage(frame: Frame, *, copy: bool = True) -> QImage:
    """Wrap a captured BGRA buffer as an opaque QImage.

    With ``copy=False`` the result is a view over the frame's buffer and is only valid while
    that frame is alive -- Qt does not keep the Python object referenced and will read freed
    memory once it goes. Use it when the very next operation copies anyway; on a full desktop
    grab each avoided copy is tens of megabytes on the hotkey path.
    """
    if frame.rect.is_empty:
        raise ValueError(f"cannot convert an empty frame: {frame.rect}")

    view = QImage(
        frame.pixels,
        frame.width,
        frame.height,
        frame.width * BYTES_PER_PIXEL,
        QImage.Format.Format_RGB32,
    )
    return view.copy() if copy else view


def copy_to_clipboard(frame: Frame) -> bool:
    """Put the frame on the clipboard. False when no clipboard is available."""
    # Guarding on the application rather than on clipboard(): Qt's own type says the
    # clipboard is never None, but calling it without a running application aborts.
    if QApplication.instance() is None:
        return False

    QApplication.clipboard().setImage(frame_to_qimage(frame))
    return True


def copy_image_to_clipboard(image: QImage) -> bool:
    """Put an already-rendered image on the clipboard.

    Used for the flattened editor output, which is a QImage rather than a captured Frame.
    """
    if QApplication.instance() is None:
        return False

    QApplication.clipboard().setImage(image)
    return True
