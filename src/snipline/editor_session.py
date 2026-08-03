"""Opens the editor for a capture and delivers what comes out of it.

Sits between ``RegionCapture`` and ``EditorWindow`` so the editor never learns about
clipboards, files, or settings, and the capture path never learns about annotations.

Every delivery flattens the scene first, at the capture's own resolution. Flattening at
*view* resolution -- the obvious mistake -- silently downscales the export whenever the
window is smaller than the capture, which is most of the time.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QImage

from snipline.capture.frame import Frame
from snipline.capture_flow import (
    CaptureFlow,
    CaptureOutcome,
    build_filename,
    default_save_directory,
    unique_path,
)
from snipline.config import Settings
from snipline.editor.window import EditorWindow
from snipline.export.clipboard import copy_image_to_clipboard
from snipline.export.qt_image import save_image

__all__ = ["EditorSession"]


class EditorSession(QObject):
    """One editor window, from capture to delivery."""

    closed = Signal()

    def __init__(
        self,
        frame: Frame,
        settings: Settings,
        flow: CaptureFlow,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._flow = flow
        self._window = EditorWindow(frame)
        self._window.copy_requested.connect(self.copy)
        self._window.export_requested.connect(self.save)
        self._window.closed.connect(self.closed)

    @property
    def window(self) -> EditorWindow:
        return self._window

    def open(self) -> None:
        self._window.fit_to_screen()
        self._window.show()
        self._window.raise_()
        self._window.activateWindow()

    def flatten(self) -> QImage:
        return self._window.controller.scene.flatten()

    def copy(self) -> CaptureOutcome:
        image = self.flatten()
        if not copy_image_to_clipboard(image):
            return self._flow.report_failure("no clipboard is available")

        self._flow.report_success("Copied to clipboard", f"{image.width()} x {image.height()}")
        return CaptureOutcome()

    def save(self) -> CaptureOutcome:
        try:
            directory = self._settings.save_directory or default_save_directory()
            # unique_path, not the bare filename: saving twice from one editor session is
            # normal (annotate, save, annotate more, save again) and would otherwise
            # overwrite the earlier file within the same second.
            written = save_image(
                self.flatten(),
                unique_path(
                    directory / build_filename(self._flow.now(), self._settings.export_format)
                ),
                export_format=self._settings.export_format,
                quality=self._settings.jpeg_quality,
            )
        except (OSError, ValueError) as error:
            return self._flow.report_failure(str(error))

        self._flow.report_success("Capture saved", str(written))
        return CaptureOutcome(path=written)
