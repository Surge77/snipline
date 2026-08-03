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
from snipline.capture_flow import CaptureFlow, CaptureOutcome
from snipline.config import Settings
from snipline.editor.window import EditorWindow
from snipline.export.sink import ClipboardSink, FileSink, Sink

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
        return self._deliver(ClipboardSink(), "Copied to clipboard")

    def save(self) -> CaptureOutcome:
        # A FileSink per save rather than one per session, because the settings it reads --
        # directory, format, quality -- can change between saves.
        sink = FileSink(
            directory=self._settings.save_directory,
            export_format=self._settings.export_format,
            quality=self._settings.jpeg_quality,
            clock=self._flow.now,
        )
        return self._deliver(sink, "Capture saved")

    def _deliver(self, sink: Sink, title: str) -> CaptureOutcome:
        """Hand the flattened scene to a sink and turn the result into a report.

        Sinks raise; the decision about whether a failure is worth interrupting the user
        for belongs here, not in the sink.
        """
        try:
            result = sink.deliver(self.flatten())
        except (OSError, ValueError, RuntimeError) as error:
            return self._flow.report_failure(str(error))

        self._flow.report_success(title, result.description)
        return CaptureOutcome(path=result.path)
