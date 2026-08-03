"""Encoding a captured frame to an image file.

The dimension assertions are the point of M1: an exported file whose pixel dimensions do
not equal the requested physical region means the capture path lost a scale factor
somewhere.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from snipline.capture.fake_backend import FakeBackend, pixel_value
from snipline.capture.frame import Frame
from snipline.config import ExportFormat
from snipline.export.encode import frame_to_image, save_frame
from snipline.platform.geometry import PhysicalRect


def _frame(rect: PhysicalRect) -> Frame:
    return FakeBackend().grab(rect)


def test_image_dimensions_equal_the_physical_region() -> None:
    image = frame_to_image(_frame(PhysicalRect(0, 0, 640, 480)))

    assert image.size == (640, 480)


def test_dimensions_are_unaffected_by_a_negative_origin() -> None:
    image = frame_to_image(_frame(PhysicalRect(-1920, -200, 800, 600)))

    assert image.size == (800, 600)


def test_bgra_channels_are_reordered_to_rgb() -> None:
    frame = _frame(PhysicalRect(7, 11, 4, 4))
    blue, green, red, _alpha = pixel_value(7, 11)

    image = frame_to_image(frame)

    assert image.mode == "RGB"
    assert image.getpixel((0, 0)) == (red, green, blue)


def test_alpha_is_dropped_by_default() -> None:
    # GDI BitBlt leaves the alpha byte at zero. Preserving it would export a fully
    # transparent image that renders blank in half of all viewers.
    rect = PhysicalRect(0, 0, 2, 2)
    transparent = Frame(rect=rect, pixels=bytes([10, 20, 30, 0] * 4))

    image = frame_to_image(transparent)

    assert image.mode == "RGB"
    assert image.getpixel((0, 0)) == (30, 20, 10)


def test_alpha_is_preserved_when_explicitly_requested() -> None:
    rect = PhysicalRect(0, 0, 2, 2)
    frame = Frame(rect=rect, pixels=bytes([10, 20, 30, 128] * 4))

    image = frame_to_image(frame, keep_alpha=True)

    assert image.mode == "RGBA"
    assert image.getpixel((0, 0)) == (30, 20, 10, 128)


def test_save_writes_a_png_whose_dimensions_match_the_capture(tmp_path: Path) -> None:
    destination = tmp_path / "shot.png"

    save_frame(_frame(PhysicalRect(100, 100, 320, 240)), destination)

    with Image.open(destination) as written:
        assert written.format == "PNG"
        assert written.size == (320, 240)


@pytest.mark.parametrize(
    ("export_format", "expected"),
    [(ExportFormat.PNG, "PNG"), (ExportFormat.WEBP, "WEBP"), (ExportFormat.JPEG, "JPEG")],
)
def test_every_supported_format_round_trips(
    tmp_path: Path, export_format: ExportFormat, expected: str
) -> None:
    destination = tmp_path / f"shot.{export_format.value}"

    save_frame(_frame(PhysicalRect(0, 0, 64, 48)), destination, export_format=export_format)

    with Image.open(destination) as written:
        assert written.format == expected
        assert written.size == (64, 48)


def test_jpeg_never_receives_an_alpha_channel(tmp_path: Path) -> None:
    # Pillow raises on RGBA -> JPEG. The encoder must resolve this rather than surfacing
    # a Pillow error to the user for a legal combination of settings.
    rect = PhysicalRect(0, 0, 8, 8)
    frame = Frame(rect=rect, pixels=bytes([10, 20, 30, 128] * 64))
    destination = tmp_path / "shot.jpg"

    save_frame(frame, destination, export_format=ExportFormat.JPEG, keep_alpha=True)

    with Image.open(destination) as written:
        assert written.mode == "RGB"


def test_save_creates_missing_parent_directories(tmp_path: Path) -> None:
    destination = tmp_path / "nested" / "deeper" / "shot.png"

    save_frame(_frame(PhysicalRect(0, 0, 8, 8)), destination)

    assert destination.exists()


def test_save_rejects_an_out_of_range_jpeg_quality(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="quality"):
        save_frame(
            _frame(PhysicalRect(0, 0, 8, 8)),
            tmp_path / "shot.jpg",
            export_format=ExportFormat.JPEG,
            quality=0,
        )
