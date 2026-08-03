"""Where a finished capture goes.

The same seam as ``CaptureBackend``: an interface plus a fake, so every path that delivers a
capture is testable without a real clipboard or filesystem.

Sinks take a ``QImage`` rather than a ``Frame`` because everything that reaches them has
already been flattened -- the editor renders annotations over the capture exactly once, at
export (D8). A sink that accepted raw frames would invite a second flattening path that
could disagree with the first.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from PySide6.QtGui import QImage

from snipline.capture_flow import build_filename, default_save_directory, unique_path
from snipline.config import ExportFormat, Settings
from snipline.export.clipboard import copy_image_to_clipboard
from snipline.export.qt_image import save_image

__all__ = ["ClipboardSink", "FileSink", "Sink", "SinkResult", "build_sink"]


class SinkResult:
    """What a sink did. ``path`` is None for destinations that are not files."""

    __slots__ = ("description", "path")

    def __init__(self, description: str, path: Path | None = None) -> None:
        self.description = description
        self.path = path


@runtime_checkable
class Sink(Protocol):
    """Accepts one flattened capture."""

    name: str

    def deliver(self, image: QImage) -> SinkResult:
        """Send the image on. Raises OSError or ValueError on failure.

        Failures raise rather than return, because a sink cannot know whether a failure is
        worth interrupting the user for -- that is the caller's decision.
        """
        ...


class ClipboardSink:
    name = "clipboard"

    def deliver(self, image: QImage) -> SinkResult:
        if not copy_image_to_clipboard(image):
            raise RuntimeError("no clipboard is available")
        return SinkResult(f"{image.width()} x {image.height()} copied to clipboard")


class FileSink:
    """Writes to the configured directory with a timestamped, non-colliding name."""

    name = "file"

    def __init__(
        self,
        directory: Path | None = None,
        export_format: ExportFormat = ExportFormat.PNG,
        quality: int = 92,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._directory = directory or default_save_directory()
        self._format = export_format
        self._quality = quality
        self._clock = clock

    def deliver(self, image: QImage) -> SinkResult:
        destination = unique_path(
            self._directory / build_filename(self._clock(), self._format)
        )
        written = save_image(
            image, destination, export_format=self._format, quality=self._quality
        )
        return SinkResult(str(written), path=written)


def build_sink(settings: Settings) -> Sink:
    """The sink the settings ask for."""
    from snipline.config import DefaultSink

    if settings.default_sink is DefaultSink.CLIPBOARD:
        return ClipboardSink()
    return FileSink(
        directory=settings.save_directory,
        export_format=settings.export_format,
        quality=settings.jpeg_quality,
    )
