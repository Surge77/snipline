"""Hotkey to region on the clipboard.

Sequences the M3 journey: freeze the desktop, show the overlay, crop what was selected out
of the frozen frame, and hand it to the capture flow.

Freeze happens *before* the overlay is constructed (D5). That ordering is the whole reason
open menus, tooltips, and hover states survive into the capture, and why the overlay's own
dimming can never appear in the output.

Kept separate from ``CaptureFlow`` so that the flow stays Qt-free and testable without a
screen; this class is the Qt-aware sequencer around it.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from snipline.capture.service import CaptureService
from snipline.capture_flow import CaptureFlow
from snipline.overlay.controller import OverlayController
from snipline.platform.geometry import PhysicalRect

__all__ = ["RegionCapture"]


class RegionCapture(QObject):
    """Runs one region capture at a time."""

    finished = Signal()

    selected = Signal(object)  # Frame, cropped out of the frozen desktop

    def __init__(
        self,
        service: CaptureService,
        flow: CaptureFlow,
        parent: QObject | None = None,
        deliver: bool = True,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._flow = flow
        self._deliver = deliver
        self._controller: OverlayController | None = None

    @property
    def is_active(self) -> bool:
        return self._controller is not None

    @property
    def controller(self) -> OverlayController | None:
        """The live overlay, or None when no capture is in progress."""
        return self._controller

    def start(self) -> bool:
        """Freeze the desktop and show the overlay. False if it could not be shown.

        Re-entry is refused rather than queued: a second overlay stacked on the first would
        freeze the desktop again, capturing the first overlay's dimming into the image.
        """
        if self.is_active:
            return False

        try:
            frozen, monitors = self._service.grab_desktop_with_monitors()
        except (RuntimeError, ValueError, OSError) as error:
            self._flow.report_failure(str(error))
            return False

        controller = OverlayController(frozen=frozen, monitors=monitors)
        controller.selected.connect(self._on_selected)
        controller.cancelled.connect(self._on_cancelled)
        self._controller = controller

        if not controller.show():
            self._flow.report_failure("no screen was available for the overlay")
            self._teardown()
            return False
        return True

    def _on_selected(self, region: PhysicalRect) -> None:
        controller = self._controller
        if controller is None:
            return

        try:
            cropped = controller.crop(region)
            # Either straight to the configured sink, or handed to whoever is listening --
            # the editor, when one is wired up. The capture path itself stays unaware of
            # annotations.
            if self._deliver:
                self._flow.deliver(cropped)
            else:
                self.selected.emit(cropped)
        finally:
            # Teardown must happen even if delivery fails, or the next hotkey press is
            # refused as re-entrant and the tool appears dead.
            self._teardown()

    def abort(self) -> None:
        """Close the overlay without capturing. Safe when nothing is open.

        Used on shutdown: an overlay surviving the app would leave a frozen, unclickable
        image covering the screen.
        """
        self._teardown()

    def _on_cancelled(self) -> None:
        # Esc means the user wants nothing captured: no file, no clipboard, no notification.
        self._teardown()

    def _teardown(self) -> None:
        if self._controller is not None:
            self._controller.close()
            self._controller.deleteLater()
            self._controller = None
        self.finished.emit()
