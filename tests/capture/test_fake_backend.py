"""The fake backend is test infrastructure, so its own correctness needs pinning.

``pixel_value`` is the readable definition of the gradient and what other tests assert
against; ``grab`` produces the same values through a vectorised path. If those two ever
drift, every crop-position assertion in the suite quietly stops meaning anything.
"""

from __future__ import annotations

from snipline.capture.fake_backend import BYTES_PER_PIXEL, FakeBackend, pixel_value
from snipline.platform.geometry import PhysicalRect


def _pixel_at(frame_pixels: bytes, rect: PhysicalRect, x: int, y: int) -> tuple[int, ...]:
    offset = ((y - rect.top) * rect.width + (x - rect.left)) * BYTES_PER_PIXEL
    return tuple(frame_pixels[offset : offset + BYTES_PER_PIXEL])


def test_vectorised_grab_matches_the_scalar_formula_including_negative_origins() -> None:
    rect = PhysicalRect(-5, -3, 11, 7)
    frame = FakeBackend().grab(rect)

    for y in range(rect.top, rect.bottom):
        for x in range(rect.left, rect.right):
            assert _pixel_at(frame.pixels, rect, x, y) == pixel_value(x, y)


def test_grab_records_every_requested_rect() -> None:
    backend = FakeBackend()
    first = PhysicalRect(0, 0, 4, 4)
    second = PhysicalRect(10, 10, 2, 2)

    backend.grab(first)
    backend.grab(second)

    assert backend.grab_calls == [first, second]


def test_pixels_are_fully_opaque() -> None:
    frame = FakeBackend().grab(PhysicalRect(0, 0, 3, 3))

    assert frame.pixels[3::BYTES_PER_PIXEL] == bytes([255] * 9)
