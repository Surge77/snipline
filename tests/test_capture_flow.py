"""The M2 user journey: hotkey pressed, file on disk, user told about it.

No tray and no hotkey here -- CaptureFlow is deliberately Qt-free, so the whole journey is
testable against FakeBackend and a temp directory.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image

from snipline.capture.fake_backend import FakeBackend
from snipline.capture.service import CaptureService
from snipline.capture_flow import CaptureFlow, build_filename, default_save_directory
from snipline.config import DefaultSink, ExportFormat, Settings
from snipline.platform.geometry import MonitorInfo, PhysicalRect

FIXED_MOMENT = datetime(2026, 8, 3, 14, 30, 5)

MONITORS = [
    MonitorInfo(0, PhysicalRect(0, 0, 800, 600), PhysicalRect(0, 0, 800, 600), 1.0, True),
    MonitorInfo(
        1, PhysicalRect(-640, 0, 640, 480), PhysicalRect(-640, 0, 640, 480), 1.0, False
    ),
]


class SpyReporter:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, bool]] = []

    def __call__(self, title: str, message: str, is_error: bool) -> None:
        self.messages.append((title, message, is_error))

    @property
    def last_title(self) -> str:
        return self.messages[-1][0]


@pytest.fixture
def reporter() -> SpyReporter:
    return SpyReporter()


def _flow(
    tmp_path: Path,
    reporter: SpyReporter,
    backend: FakeBackend,
    settings: Settings | None = None,
) -> CaptureFlow:
    resolved = settings or Settings(save_directory=tmp_path)
    return CaptureFlow(
        service=CaptureService(backend=backend, monitors_provider=lambda: MONITORS),
        settings=resolved,
        reporter=reporter,
        clock=lambda: FIXED_MOMENT,
    )


def test_writes_the_whole_virtual_desktop(
    tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    outcome = _flow(tmp_path, reporter, backend).capture_desktop()

    assert outcome.succeeded
    assert outcome.path is not None
    with Image.open(outcome.path) as written:
        # 800 wide primary plus a 640 wide monitor at a negative origin.
        assert written.size == (1440, 600)


def test_reports_the_written_path_on_success(
    tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    outcome = _flow(tmp_path, reporter, backend).capture_desktop()

    assert reporter.last_title == "Capture saved"
    assert reporter.messages[-1][1] == str(outcome.path)
    assert reporter.messages[-1][2] is False


def test_filename_is_timestamped_and_sortable(
    tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    outcome = _flow(tmp_path, reporter, backend).capture_desktop()

    assert outcome.path is not None
    assert outcome.path.name == "Snipline 2026-08-03 143005.png"


def test_creates_the_save_directory_when_missing(
    tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    target = tmp_path / "not" / "yet" / "there"

    outcome = _flow(tmp_path, reporter, backend, Settings(save_directory=target)).capture_desktop()

    assert outcome.succeeded
    assert target.is_dir()


def test_a_second_capture_in_the_same_second_does_not_overwrite_the_first(
    tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    # Trivially reachable by holding the hotkey; overwriting would destroy user data.
    flow = _flow(tmp_path, reporter, backend)

    first = flow.capture_desktop()
    second = flow.capture_desktop()

    assert first.path != second.path
    assert first.path is not None and first.path.exists()
    assert second.path is not None and second.path.name == "Snipline 2026-08-03 143005 (2).png"


def test_honours_the_configured_export_format(
    tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    settings = Settings(save_directory=tmp_path, export_format=ExportFormat.JPEG)

    outcome = _flow(tmp_path, reporter, backend, settings).capture_desktop()

    assert outcome.path is not None
    assert outcome.path.suffix == ".jpeg"
    with Image.open(outcome.path) as written:
        assert written.format == "JPEG"


def test_a_capture_failure_is_reported_rather_than_raised(
    tmp_path: Path, reporter: SpyReporter
) -> None:
    class BrokenBackend(FakeBackend):
        def grab(self, rect: PhysicalRect) -> object:  # type: ignore[override]
            raise RuntimeError("display disconnected")

    # An exception escaping the hotkey handler would take down an app that lives in the
    # tray, so failures must come back as outcomes.
    flow = _flow(tmp_path, reporter, BrokenBackend())
    outcome = flow.capture_desktop()

    assert not outcome.succeeded
    assert outcome.error is not None and "display disconnected" in outcome.error
    assert reporter.last_title == "Capture failed"
    assert reporter.messages[-1][2] is True


def test_an_unwritable_destination_is_reported_rather_than_raised(
    tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    # A file where the save directory should be: mkdir fails with OSError.
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")

    outcome = _flow(tmp_path, reporter, backend, Settings(save_directory=blocked)).capture_desktop()

    assert not outcome.succeeded
    assert reporter.last_title == "Capture failed"


def test_works_without_a_reporter(tmp_path: Path, backend: FakeBackend) -> None:
    flow = CaptureFlow(
        service=CaptureService(backend=backend, monitors_provider=lambda: MONITORS),
        settings=Settings(save_directory=tmp_path),
        clock=lambda: FIXED_MOMENT,
    )

    assert flow.capture_desktop().succeeded


def test_deliver_puts_the_frame_on_the_clipboard_by_default(
    tmp_path: Path, reporter: SpyReporter, backend: FakeBackend, qapp: object
) -> None:
    from PySide6.QtWidgets import QApplication

    frame = backend.grab(PhysicalRect(100, 50, 32, 16))

    outcome = _flow(tmp_path, reporter, backend).deliver(frame)

    assert outcome.succeeded
    assert outcome.path is None  # clipboard, so nothing was written to disk
    assert reporter.last_title == "Copied to clipboard"
    pasted = QApplication.clipboard().image()
    assert (pasted.width(), pasted.height()) == (32, 16)


def test_deliver_writes_a_file_when_the_sink_is_file(
    tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    settings = Settings(save_directory=tmp_path, default_sink=DefaultSink.FILE)
    frame = backend.grab(PhysicalRect(0, 0, 64, 48))

    outcome = _flow(tmp_path, reporter, backend, settings).deliver(frame)

    assert outcome.path is not None
    with Image.open(outcome.path) as written:
        assert written.size == (64, 48)


def test_deliver_reports_a_failure_rather_than_raising(
    tmp_path: Path, reporter: SpyReporter, backend: FakeBackend
) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")
    settings = Settings(save_directory=blocked, default_sink=DefaultSink.FILE)
    frame = backend.grab(PhysicalRect(0, 0, 8, 8))

    outcome = _flow(tmp_path, reporter, backend, settings).deliver(frame)

    assert not outcome.succeeded
    assert reporter.last_title == "Capture failed"


def test_default_save_directory_is_under_pictures() -> None:
    assert default_save_directory().parent.name == "Pictures"


@pytest.mark.parametrize(
    ("export_format", "expected"),
    [
        (ExportFormat.PNG, "Snipline 2026-08-03 143005.png"),
        (ExportFormat.JPEG, "Snipline 2026-08-03 143005.jpeg"),
        (ExportFormat.WEBP, "Snipline 2026-08-03 143005.webp"),
    ],
)
def test_filename_has_no_characters_windows_rejects(
    export_format: ExportFormat, expected: str
) -> None:
    name = build_filename(FIXED_MOMENT, export_format)

    assert name == expected
    assert not set(name) & set(':*?"<>|/\\')
