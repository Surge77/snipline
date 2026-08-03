"""Coordinates the per-screen overlay windows.

One ``SelectionModel`` is shared by every window, which is what lets a drag start on one
screen and finish on another: each window converts its own local coordinates into the same
absolute physical space, so the model never learns that more than one window exists.

Windows are closed together. Leaving one behind would cover a monitor with a frozen,
unclickable image of itself -- a failure that looks like the whole machine has hung.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QPixmap

from snipline.capture.frame import Frame
from snipline.export.clipboard import frame_to_qimage
from snipline.overlay.mapping import frame_slice_for
from snipline.overlay.selection import SelectionModel
from snipline.overlay.window import OverlayWindow, screen_for
from snipline.platform.geometry import MonitorInfo, PhysicalRect

__all__ = ["OverlayController"]


class OverlayController(QObject):
    """Shows the frozen desktop across every screen and reports what was selected."""

    selected = Signal(object)  # PhysicalRect
    cancelled = Signal()

    def __init__(
        self,
        frozen: Frame,
        monitors: Sequence[MonitorInfo],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._frozen = frozen
        self._monitors = list(monitors)
        self._model = SelectionModel(desktop=frozen.rect, monitors=self._monitors)
        self._windows: list[OverlayWindow] = []

    @property
    def model(self) -> SelectionModel:
        return self._model

    def build_windows(self) -> list[OverlayWindow]:
        """Create one window per screen. Separated from ``show`` so it is inspectable."""
        desktop_pixmap = QPixmap.fromImage(frame_to_qimage(self._frozen))

        windows: list[OverlayWindow] = []
        for monitor in self._monitors:
            screen = screen_for(monitor)
            if screen is None:
                # Qt and Win32 disagree about the layout, which happens mid-hot-plug.
                # Skipping the screen is better than crashing the capture.
                continue

            slice_rect = frame_slice_for(monitor, self._frozen.rect)
            window = OverlayWindow(
                screen=screen,
                monitor=monitor,
                frozen=desktop_pixmap.copy(
                    slice_rect.left, slice_rect.top, slice_rect.width, slice_rect.height
                ),
                model=self._model,
            )
            window.committed.connect(self.commit)
            window.cancelled.connect(self.cancel)
            window.selection_changed.connect(self._repaint_all)
            windows.append(window)

        self._windows = windows
        return windows

    def show(self) -> bool:
        """Display the overlay. False when no screen could be matched."""
        self._model.reset()
        if not self.build_windows():
            return False

        for window in self._windows:
            window.show_on_screen()
        return True

    def close(self) -> None:
        for window in self._windows:
            window.close()
            window.deleteLater()
        self._windows = []

    def _repaint_all(self) -> None:
        # Every window repaints on any change: a selection spanning two screens must not
        # leave half of itself undrawn on the screen the mouse is not on.
        for window in self._windows:
            window.update()

    def commit(self) -> None:
        """Accept the current selection, close the overlay, and report the result.

        A selection that resolves to nothing -- a click in the dead space of an L-shaped
        arrangement, or a zero-area drag -- is reported as a cancel rather than as an empty
        capture, which would fail later with a much worse message.
        """
        region = self._model.commit()
        self.close()
        if region is None or region.is_empty:
            self.cancelled.emit()
        else:
            self.selected.emit(region)

    def cancel(self) -> None:
        """Abandon the capture. Nothing is written, copied, or reported."""
        self.close()
        self.cancelled.emit()

    def crop(self, region: PhysicalRect) -> Frame:
        """Cut the selection out of the frozen frame.

        No new capture is taken: the pixels are the ones frozen before the overlay existed,
        which is what keeps menus and hover states in the output (D5).
        """
        return self._frozen.crop(region)
