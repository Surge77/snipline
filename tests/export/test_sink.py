"""Export sinks."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
from PIL import Image
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from snipline.config import DefaultSink, ExportFormat, Settings
from snipline.export.sink import ClipboardSink, FileSink, Sink, build_sink

FIXED_MOMENT = datetime(2026, 8, 3, 17, 5, 0)


def _image(width: int = 64, height: int = 48) -> QImage:
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#3B82F6"))
    return image


def test_both_sinks_satisfy_the_protocol(qapp: QApplication, tmp_path: Path) -> None:
    assert isinstance(ClipboardSink(), Sink)
    assert isinstance(FileSink(tmp_path), Sink)


def test_the_clipboard_sink_delivers_the_image(qapp: QApplication) -> None:
    result = ClipboardSink().deliver(_image(120, 90))

    pasted = QApplication.clipboard().image()
    assert (pasted.width(), pasted.height()) == (120, 90)
    assert "120 x 90" in result.description
    assert result.path is None


def test_the_file_sink_writes_at_full_resolution(qapp: QApplication, tmp_path: Path) -> None:
    result = FileSink(tmp_path, clock=lambda: FIXED_MOMENT).deliver(_image(320, 240))

    assert result.path is not None
    with Image.open(result.path) as written:
        assert written.size == (320, 240)


def test_the_file_sink_never_overwrites(qapp: QApplication, tmp_path: Path) -> None:
    sink = FileSink(tmp_path, clock=lambda: FIXED_MOMENT)

    first = sink.deliver(_image())
    second = sink.deliver(_image())

    assert first.path != second.path
    assert first.path is not None and first.path.exists()


@pytest.mark.parametrize(
    ("export_format", "expected"),
    [(ExportFormat.PNG, "PNG"), (ExportFormat.WEBP, "WEBP"), (ExportFormat.JPEG, "JPEG")],
)
def test_the_file_sink_honours_the_format(
    qapp: QApplication, tmp_path: Path, export_format: ExportFormat, expected: str
) -> None:
    sink = FileSink(tmp_path, export_format=export_format, clock=lambda: FIXED_MOMENT)

    result = sink.deliver(_image())

    assert result.path is not None
    with Image.open(result.path) as written:
        assert written.format == expected


def test_the_file_sink_raises_rather_than_reporting_failure(
    qapp: QApplication, tmp_path: Path
) -> None:
    # A sink cannot know whether a failure is worth interrupting the user for; that is the
    # caller's decision.
    blocked = tmp_path / "blocked"
    blocked.write_text("not a directory")

    with pytest.raises((OSError, ValueError)):
        FileSink(blocked, clock=lambda: FIXED_MOMENT).deliver(_image())


def test_build_sink_follows_the_configured_destination(
    qapp: QApplication, tmp_path: Path
) -> None:
    clipboard = build_sink(Settings(default_sink=DefaultSink.CLIPBOARD))
    file_sink = build_sink(Settings(default_sink=DefaultSink.FILE, save_directory=tmp_path))

    assert clipboard.name == "clipboard"
    assert file_sink.name == "file"


def test_a_built_file_sink_uses_the_configured_directory(
    qapp: QApplication, tmp_path: Path
) -> None:
    sink = build_sink(
        Settings(
            default_sink=DefaultSink.FILE,
            save_directory=tmp_path,
            export_format=ExportFormat.WEBP,
        )
    )

    result = sink.deliver(_image())

    assert result.path is not None
    assert result.path.parent == tmp_path
    assert result.path.suffix == ".webp"
