from __future__ import annotations

import pytest

from snipline.capture.backend import CaptureBackend
from snipline.capture.fake_backend import FakeBackend, pixel_value
from snipline.capture.frame import Frame
from snipline.platform.geometry import PhysicalRect


def pixel_at(frame: Frame, x: int, y: int) -> tuple[int, ...]:
    """Read one BGRA pixel using absolute virtual-desktop coordinates."""
    local_x = x - frame.rect.left
    local_y = y - frame.rect.top
    offset = (local_y * frame.width + local_x) * 4
    return tuple(frame.pixels[offset : offset + 4])


class TestFakeBackendContract:
    def test_satisfies_the_capture_protocol(self, backend: FakeBackend) -> None:
        assert isinstance(backend, CaptureBackend)

    def test_returns_a_frame_matching_the_requested_rect(self, backend: FakeBackend) -> None:
        rect = PhysicalRect(10, 20, 64, 32)
        frame = backend.grab(rect)
        assert frame.rect == rect
        assert len(frame.pixels) == 64 * 32 * 4

    def test_pixels_encode_absolute_position(self, backend: FakeBackend) -> None:
        frame = backend.grab(PhysicalRect(100, 200, 4, 4))
        assert pixel_at(frame, 100, 200) == pixel_value(100, 200)
        assert pixel_at(frame, 103, 203) == pixel_value(103, 203)

    def test_captures_from_negative_coordinates(self, backend: FakeBackend) -> None:
        frame = backend.grab(PhysicalRect(-1920, -200, 8, 8))
        assert pixel_at(frame, -1920, -200) == pixel_value(-1920, -200)

    def test_records_calls_for_assertion(self, backend: FakeBackend) -> None:
        rect = PhysicalRect(0, 0, 2, 2)
        backend.grab(rect)
        assert backend.grab_calls == [rect]


class TestFrameValidation:
    def test_rejects_a_buffer_of_the_wrong_size(self) -> None:
        with pytest.raises(ValueError, match="expected"):
            Frame(rect=PhysicalRect(0, 0, 10, 10), pixels=b"\x00" * 4)


class TestCrop:
    def test_extracts_the_requested_region(self, backend: FakeBackend) -> None:
        frame = backend.grab(PhysicalRect(0, 0, 100, 100))
        cropped = frame.crop(PhysicalRect(10, 20, 30, 40))
        assert cropped.rect == PhysicalRect(10, 20, 30, 40)
        assert len(cropped.pixels) == 30 * 40 * 4

    def test_cropped_pixels_come_from_the_right_place(self, backend: FakeBackend) -> None:
        # The core correctness property: a crop must carry the pixels that were at those
        # absolute coordinates, not pixels offset by the frame's origin.
        frame = backend.grab(PhysicalRect(0, 0, 200, 200))
        cropped = frame.crop(PhysicalRect(50, 60, 10, 10))
        assert pixel_at(cropped, 50, 60) == pixel_value(50, 60)
        assert pixel_at(cropped, 59, 69) == pixel_value(59, 69)

    def test_crops_correctly_from_a_negative_origin_frame(self, backend: FakeBackend) -> None:
        # The whole-monitor-offset bug: cropping a selection out of a desktop that starts
        # at a negative x. If the origin is not rebased, this reads the wrong monitor.
        frame = backend.grab(PhysicalRect(-1920, 0, 3840, 1080))
        cropped = frame.crop(PhysicalRect(-1820, 100, 20, 20))
        assert cropped.rect.left == -1820
        assert pixel_at(cropped, -1820, 100) == pixel_value(-1820, 100)

    def test_clamps_a_region_extending_past_the_frame(self, backend: FakeBackend) -> None:
        frame = backend.grab(PhysicalRect(0, 0, 100, 100))
        cropped = frame.crop(PhysicalRect(90, 90, 50, 50))
        assert cropped.rect == PhysicalRect(90, 90, 10, 10)

    def test_a_full_frame_crop_is_a_no_op(self, backend: FakeBackend) -> None:
        rect = PhysicalRect(5, 5, 16, 16)
        frame = backend.grab(rect)
        assert frame.crop(rect).pixels == frame.pixels

    def test_rejects_a_region_outside_the_frame(self, backend: FakeBackend) -> None:
        frame = backend.grab(PhysicalRect(0, 0, 10, 10))
        with pytest.raises(ValueError, match="does not overlap"):
            frame.crop(PhysicalRect(500, 500, 10, 10))
