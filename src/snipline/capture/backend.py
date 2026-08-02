"""The capture seam.

Every path that reads pixels off the screen goes through this protocol. That is what lets
the geometry, cropping, editor, and export logic run headless in CI against a synthetic
backend, with no real screen access anywhere in the test suite.

See D9 in docs/DECISIONS.md.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from snipline.capture.frame import Frame
from snipline.platform.geometry import PhysicalRect


@runtime_checkable
class CaptureBackend(Protocol):
    """Reads a region of the desktop in physical pixels."""

    def grab(self, rect: PhysicalRect) -> Frame:
        """Capture ``rect``, given in absolute virtual-desktop coordinates.

        Implementations must return a frame whose ``rect`` equals the requested rect. A
        backend that silently returns a differently sized buffer -- because it clamped, or
        because it applied DPI virtualisation behind our back -- is the failure mode this
        contract exists to catch.
        """
        ...

    def close(self) -> None:
        """Release any OS resources. Safe to call more than once."""
        ...
