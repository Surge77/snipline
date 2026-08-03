"""Capture to editor to delivery."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from snipline.capture.fake_backend import FakeBackend, pixel_value
from snipline.capture.service import CaptureService
from snipline.capture_flow import CaptureFlow
from snipline.config import ExportFormat, Settings
from snipline.editor_session import EditorSession
from snipline.platform.geometry import MonitorInfo, PhysicalRect

CAPTURE = PhysicalRect(0, 0, 320, 240)
MONITORS = [MonitorInfo(0, CAPTURE, CAPTURE, 1.0, True)]
FIXED_MOMENT = datetime(2026, 8, 3, 16, 15, 0)


class SpyReporter:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, bool]] = []

    def __call__(self, title: str, message: str, is_error: bool) -> None:
        self.messages.append((title, message, is_error))


@pytest.fixture
def reporter() -> SpyReporter:
    return SpyReporter()


def _session(
    tmp_path: Path, reporter: SpyReporter, settings: Settings | None = None
) -> EditorSession:
    backend = FakeBackend()
    resolved = settings or Settings(save_directory=tmp_path)
    flow = CaptureFlow(
        service=CaptureService(backend=backend, monitors_provider=lambda: MONITORS),
        settings=resolved,
        reporter=reporter,
        clock=lambda: FIXED_MOMENT,
    )
    return EditorSession(frame=backend.grab(CAPTURE), settings=resolved, flow=flow)


def _annotate(session: EditorSession) -> None:
    controller = session.window.controller
    controller.press(QPointF(10, 10))
    controller.move(QPointF(200, 180))
    controller.release(QPointF(200, 180))


def test_copy_puts_the_flattened_capture_on_the_clipboard(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter
) -> None:
    session = _session(tmp_path, reporter)

    outcome = session.copy()

    assert outcome.succeeded
    pasted = QApplication.clipboard().image()
    assert (pasted.width(), pasted.height()) == (CAPTURE.width, CAPTURE.height)
    assert reporter.messages[-1][0] == "Copied to clipboard"


def test_the_flattened_image_keeps_the_captures_physical_size(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter
) -> None:
    # The M6 trap: flattening at view resolution would downscale whenever the window is
    # smaller than the capture, which is most of the time.
    session = _session(tmp_path, reporter)
    session.window.resize(120, 90)

    flattened = session.flatten()

    assert (flattened.width(), flattened.height()) == (CAPTURE.width, CAPTURE.height)


def test_annotations_appear_in_the_delivered_image(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter
) -> None:
    session = _session(tmp_path, reporter)
    _annotate(session)

    flattened = session.flatten()

    unannotated = FakeBackend().grab(CAPTURE)
    from snipline.export.clipboard import frame_to_qimage

    assert flattened != frame_to_qimage(unannotated)


def test_an_unannotated_capture_flattens_to_the_original_pixels(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter
) -> None:
    flattened = _session(tmp_path, reporter).flatten()

    blue, green, red, _ = pixel_value(0, 0)
    corner = flattened.pixelColor(0, 0)
    assert (corner.red(), corner.green(), corner.blue()) == (red, green, blue)


def test_save_writes_a_file_at_capture_resolution(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter
) -> None:
    session = _session(tmp_path, reporter)
    _annotate(session)

    outcome = session.save()

    assert outcome.path is not None
    with Image.open(outcome.path) as written:
        assert written.size == (CAPTURE.width, CAPTURE.height)
    assert reporter.messages[-1][0] == "Capture saved"


def test_saving_twice_does_not_overwrite_the_first_file(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter
) -> None:
    # Annotate, save, annotate more, save again is an ordinary editing session, and the
    # clock is the same second throughout.
    session = _session(tmp_path, reporter)

    first = session.save()
    _annotate(session)
    second = session.save()

    assert first.path != second.path
    assert first.path is not None and first.path.exists()
    assert second.path is not None and second.path.exists()


def test_save_honours_the_configured_format(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter
) -> None:
    settings = Settings(save_directory=tmp_path, export_format=ExportFormat.JPEG)

    outcome = _session(tmp_path, reporter, settings).save()

    assert outcome.path is not None
    with Image.open(outcome.path) as written:
        assert written.format == "JPEG"


def test_a_failed_save_is_reported_rather_than_raised(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter
) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    settings = Settings(save_directory=blocked)

    outcome = _session(tmp_path, reporter, settings).save()

    assert not outcome.succeeded
    assert reporter.messages[-1][0] == "Capture failed"


def test_the_window_toolbar_actions_reach_the_session(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter
) -> None:
    # The editor emits signals; the session decides what they mean.
    session = _session(tmp_path, reporter)

    session.window.copy_requested.emit()

    assert reporter.messages[-1][0] == "Copied to clipboard"


def test_undo_removes_an_annotation_from_the_delivered_image(
    qapp: QApplication, tmp_path: Path, reporter: SpyReporter
) -> None:
    session = _session(tmp_path, reporter)
    clean = session.flatten()

    _annotate(session)
    session.window.controller.undo_stack.undo()

    assert session.flatten() == clean
