"""Synthetic capture backend. Used by every test; never used at runtime.

Produces a deterministic gradient keyed to absolute virtual-desktop coordinates, so a
cropped region's pixel values are predictable from its position alone. That makes it
possible to assert that a crop landed on the right part of the desktop -- a test that a
solid-colour fake could not express, and precisely the class of bug (off-by-one-monitor
crops on negative-coordinate layouts) this project is built to avoid.
"""

from __future__ import annotations

from snipline.capture.frame import BYTES_PER_PIXEL, Frame
from snipline.platform.geometry import PhysicalRect

__all__ = ["BYTES_PER_PIXEL", "FakeBackend", "pixel_value"]

_CHANNEL_MAX = 256


def pixel_value(x: int, y: int) -> tuple[int, int, int, int]:
    """The BGRA value this backend produces at an absolute desktop coordinate.

    Exposed so tests can assert expected values without duplicating the formula.
    Negative coordinates are handled by Python's modulo, which returns a non-negative
    result -- monitors left of or above the primary have negative origins.
    """
    blue = x % _CHANNEL_MAX
    green = y % _CHANNEL_MAX
    red = (x + y) % _CHANNEL_MAX
    return (blue, green, red, 255)


def _gradient_bytes(rect: PhysicalRect) -> bytes:
    """The same formula as ``pixel_value``, vectorised.

    The scalar loop this replaces spent about a minute per full 4K layout in the suite,
    which was enough to discourage running the tests -- the fake being slow is a real cost
    even though it never ships.
    """
    import numpy as np

    xs = np.arange(rect.left, rect.left + rect.width, dtype=np.int64)
    ys = np.arange(rect.top, rect.top + rect.height, dtype=np.int64)
    columns = np.broadcast_to(xs, (rect.height, rect.width))
    rows = ys[:, None]

    buffer = np.empty((rect.height, rect.width, 4), dtype=np.uint8)
    buffer[..., 0] = np.mod(columns, _CHANNEL_MAX)
    buffer[..., 1] = np.mod(rows, _CHANNEL_MAX)
    buffer[..., 2] = np.mod(columns + rows, _CHANNEL_MAX)
    buffer[..., 3] = 255
    return buffer.tobytes()


class FakeBackend:
    """In-memory ``CaptureBackend``."""

    def __init__(self) -> None:
        self.grab_calls: list[PhysicalRect] = []
        self.closed = False

    def grab(self, rect: PhysicalRect) -> Frame:
        self.grab_calls.append(rect)
        return Frame(rect=rect, pixels=_gradient_bytes(rect))

    def close(self) -> None:
        self.closed = True
