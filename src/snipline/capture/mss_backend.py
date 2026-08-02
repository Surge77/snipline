"""Real screen capture, via mss (GDI BitBlt under the hood).

Landing properly in M1. The implementation below is deliberately minimal and unproven --
what M1 adds is the DPI-awareness precondition, verification that returned dimensions match
the request in physical pixels, and the zero-copy path into QImage.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from snipline.capture.frame import Frame
from snipline.platform.geometry import PhysicalRect

if TYPE_CHECKING:
    from mss.base import MSSBase


class MssBackend:
    """Captures via mss. One instance owns one mss context.

    mss contexts are not thread-safe and must be used on the thread that created them.
    """

    def __init__(self) -> None:
        self._mss: MSSBase | None = None

    def _context(self) -> MSSBase:
        if self._mss is None:
            import mss  # imported lazily so tests never load the GDI bindings

            self._mss = mss.mss()
        return self._mss

    def grab(self, rect: PhysicalRect) -> Frame:
        if rect.is_empty:
            raise ValueError(f"cannot capture an empty region: {rect}")

        region: dict[str, Any] = {
            "left": rect.left,
            "top": rect.top,
            "width": rect.width,
            "height": rect.height,
        }
        shot = self._context().grab(region)

        # If these disagree, DPI awareness was not declared before the first Win32 call and
        # Windows handed back virtualised coordinates. Failing loudly here is the point:
        # silently accepting the mismatch produces captures that are wrong only on
        # high-DPI monitors, which is the hardest kind of bug to notice.
        if (shot.width, shot.height) != (rect.width, rect.height):
            raise RuntimeError(
                f"backend returned {shot.width}x{shot.height} for a "
                f"{rect.width}x{rect.height} request; DPI awareness is likely not set"
            )

        return Frame(rect=rect, pixels=bytes(shot.raw))

    def close(self) -> None:
        if self._mss is not None:
            self._mss.close()
            self._mss = None
