"""Synthetic capture backend. Used by every test; never used at runtime.

Produces a deterministic gradient keyed to absolute virtual-desktop coordinates, so a
cropped region's pixel values are predictable from its position alone. That makes it
possible to assert that a crop landed on the right part of the desktop -- a test that a
solid-colour fake could not express, and precisely the class of bug (off-by-one-monitor
crops on negative-coordinate layouts) this project is built to avoid.
"""

from __future__ import annotations

from snipline.capture.frame import Frame
from snipline.platform.geometry import PhysicalRect

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


class FakeBackend:
    """In-memory ``CaptureBackend``."""

    def __init__(self) -> None:
        self.grab_calls: list[PhysicalRect] = []
        self.closed = False

    def grab(self, rect: PhysicalRect) -> Frame:
        self.grab_calls.append(rect)
        buffer = bytearray(rect.width * rect.height * 4)
        offset = 0
        for row in range(rect.height):
            y = rect.top + row
            for column in range(rect.width):
                buffer[offset : offset + 4] = bytes(pixel_value(rect.left + column, y))
                offset += 4
        return Frame(rect=rect, pixels=bytes(buffer))

    def close(self) -> None:
        self.closed = True
