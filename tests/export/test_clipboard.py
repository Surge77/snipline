"""Frame to clipboard.

Qt's offscreen platform provides a real in-process clipboard, so the round trip is tested
rather than mocked. Whether *other applications* then paste it correctly is an OS boundary
and lives in MANUAL_TESTS.md.
"""

from __future__ import annotations

import pytest
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from snipline.capture.fake_backend import FakeBackend, pixel_value
from snipline.capture.frame import Frame
from snipline.export.clipboard import copy_to_clipboard, frame_to_qimage
from snipline.platform.geometry import PhysicalRect


def test_dimensions_match_the_physical_capture(qapp: QApplication) -> None:
    image = frame_to_qimage(FakeBackend().grab(PhysicalRect(0, 0, 640, 480)))

    assert (image.width(), image.height()) == (640, 480)


def test_a_negative_origin_capture_keeps_its_size(qapp: QApplication) -> None:
    image = frame_to_qimage(FakeBackend().grab(PhysicalRect(-1920, -200, 800, 600)))

    assert (image.width(), image.height()) == (800, 600)


def test_pixels_survive_the_bgra_reinterpretation(qapp: QApplication) -> None:
    frame = FakeBackend().grab(PhysicalRect(7, 11, 4, 4))
    blue, green, red, _ = pixel_value(7, 11)

    colour = frame_to_qimage(frame).pixelColor(0, 0)

    assert (colour.red(), colour.green(), colour.blue()) == (red, green, blue)


def test_the_image_owns_its_pixels(qapp: QApplication) -> None:
    # The real backend reuses its buffer on the next grab. If the QImage were a view over
    # the capture buffer, the clipboard would end up holding overwritten or freed memory.
    rect = PhysicalRect(0, 0, 2, 2)
    buffer = bytearray([10, 20, 30, 255] * 4)
    image = frame_to_qimage(Frame(rect=rect, pixels=bytes(buffer)))

    buffer[0:4] = bytes([99, 99, 99, 255])

    assert image.pixelColor(0, 0).blue() == 10


def test_alpha_is_ignored_rather_than_carried(qapp: QApplication) -> None:
    # GDI leaves alpha at zero; honouring it would put a fully transparent image on the
    # clipboard, which pastes as blank or as a black rectangle depending on the receiver.
    rect = PhysicalRect(0, 0, 2, 2)
    frame = Frame(rect=rect, pixels=bytes([10, 20, 30, 0] * 4))

    colour = frame_to_qimage(frame).pixelColor(0, 0)

    assert colour.alpha() == 255
    assert (colour.red(), colour.green(), colour.blue()) == (30, 20, 10)


def test_an_empty_frame_is_rejected(qapp: QApplication) -> None:
    with pytest.raises(ValueError, match="empty"):
        frame_to_qimage(Frame(rect=PhysicalRect(10, 10, 0, 0), pixels=b""))


def test_round_trips_through_the_system_clipboard(qapp: QApplication) -> None:
    frame = FakeBackend().grab(PhysicalRect(100, 50, 32, 16))

    assert copy_to_clipboard(frame)

    pasted = QApplication.clipboard().image()
    assert (pasted.width(), pasted.height()) == (32, 16)
    blue, green, red, _ = pixel_value(100, 50)
    assert (
        pasted.pixelColor(0, 0).red(),
        pasted.pixelColor(0, 0).green(),
        pasted.pixelColor(0, 0).blue(),
    ) == (red, green, blue)


def test_clipboard_content_is_independent_of_the_source_frame(qapp: QApplication) -> None:
    frame = FakeBackend().grab(PhysicalRect(0, 0, 8, 8))
    copy_to_clipboard(frame)

    del frame

    assert not QApplication.clipboard().image().isNull()


def test_a_qimage_of_the_wrong_format_is_never_produced(qapp: QApplication) -> None:
    image = frame_to_qimage(FakeBackend().grab(PhysicalRect(0, 0, 4, 4)))

    assert image.format() == QImage.Format.Format_RGB32
