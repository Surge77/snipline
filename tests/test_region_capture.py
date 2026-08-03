"""Hotkey to region on the clipboard, end to end.

The overlay renders offscreen here, so the selection is driven through the model rather than
through synthetic mouse events -- the mapping from mouse position to model coordinates is
tested separately in tests/overlay/test_mapping.py.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from snipline.capture.fake_backend import FakeBackend, pixel_value
from snipline.capture.service import CaptureService
from snipline.capture_flow import CaptureFlow
from snipline.config import DefaultSink, Settings
from snipline.platform.geometry import MonitorInfo, PhysicalRect
from snipline.region_capture import RegionCapture

DESKTOP = PhysicalRect(0, 0, 800, 600)
MONITORS = [MonitorInfo(0, DESKTOP, DESKTOP, 1.0, True)]


class SpyReporter:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, bool]] = []


    def __call__(self, title: str, message: str, is_error: bool) -> None:
        self.messages.append((title, message, is_error))


@pytest.fixture
def reporter() -> SpyReporter:
    return SpyReporter()


def _region_capture(
    tmp_path: Path, reporter: SpyReporter, backend: FakeBackend, settings: Settings | None = None
) -> RegionCapture:
    service = CaptureService(backend=backend, monitors_provider=lambda: MONITORS)
    flow = CaptureFlow(
        service=service,
        settings=settings or Settings(save_directory=tmp_path),
        reporter=reporter,
    )
    return RegionCapture(service=service, flow=flow)


def _select(capture: RegionCapture, region: PhysicalRect) -> None:
    controller = capture.controller
    assert controller is not None
    controller.model.begin(region.left, region.top)
    controller.model.update(region.right, region.bottom)
    controller.commit()


def test_a_selected_region_lands_on_the_clipboard(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    capture = _region_capture(tmp_path, reporter, backend)
    assert capture.start()

    _select(capture, PhysicalRect(100, 50, 32, 16))

    pasted = QApplication.clipboard().image()
    assert (pasted.width(), pasted.height()) == (32, 16)
    blue, green, red, _ = pixel_value(100, 50)
    corner = pasted.pixelColor(0, 0)
    assert (corner.red(), corner.green(), corner.blue()) == (red, green, blue)


def test_the_desktop_is_frozen_once_and_never_recaptured(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    # The defining guarantee of D5: the delivered pixels are the ones from before the
    # overlay existed, so the overlay's own dimming cannot appear in the output.
    capture = _region_capture(tmp_path, reporter, backend)
    capture.start()

    _select(capture, PhysicalRect(10, 10, 40, 40))

    assert backend.grab_calls == [DESKTOP]


def test_cancelling_delivers_nothing(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    settings = Settings(save_directory=tmp_path, default_sink=DefaultSink.FILE)
    capture = _region_capture(tmp_path, reporter, backend, settings)
    capture.start()

    controller = capture.controller
    assert controller is not None
    controller.cancel()

    assert list(tmp_path.glob("*")) == []
    assert reporter.messages == []


def test_the_overlay_is_torn_down_after_a_capture(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    capture = _region_capture(tmp_path, reporter, backend)
    capture.start()

    _select(capture, PhysicalRect(10, 10, 40, 40))

    assert not capture.is_active


def test_a_second_capture_can_start_after_the_first_finishes(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    capture = _region_capture(tmp_path, reporter, backend)
    capture.start()
    _select(capture, PhysicalRect(10, 10, 40, 40))

    assert capture.start()
    capture.abort()


def test_re_entry_while_the_overlay_is_open_is_refused(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    # A second overlay would freeze the desktop again and capture the first overlay's
    # dimming into the image.
    capture = _region_capture(tmp_path, reporter, backend)
    capture.start()

    assert not capture.start()
    assert backend.grab_calls == [DESKTOP]
    capture.abort()


def test_a_failed_freeze_is_reported_and_leaves_nothing_open(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter
) -> None:
    class BrokenBackend(FakeBackend):
        def grab(self, rect: PhysicalRect) -> object:  # type: ignore[override]
            raise RuntimeError("display disconnected")

    capture = _region_capture(tmp_path, reporter, BrokenBackend())

    assert not capture.start()
    assert not capture.is_active
    assert reporter.messages[-1][0] == "Capture failed"


def test_finished_is_emitted_on_both_capture_and_cancel(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    capture = _region_capture(tmp_path, reporter, backend)
    finished: list[bool] = []
    capture.finished.connect(lambda: finished.append(True))

    capture.start()
    _select(capture, PhysicalRect(10, 10, 40, 40))
    capture.start()
    controller = capture.controller
    assert controller is not None
    controller.cancel()

    assert len(finished) == 2
