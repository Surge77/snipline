"""One overlay window per screen.

**One window per screen, not one spanning the virtual desktop.** Qt applies a single device
pixel ratio to a window, so a window straddling a mixed-DPI seam renders its frozen pixmap
at the wrong scale on one of the screens. Per-screen windows each get their own ratio.

**The window shows a frozen pixmap** captured before any overlay existed (D5). That is why
open menus, tooltips, and hover states survive into the capture, and why the dimming layer
painted here can never appear in the output -- the pixels were read before it was drawn.

All logic lives in ``SelectionModel`` and ``mapping``; this class paints and forwards
events.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import (
    QColor,
    QCursor,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QScreen,
)
from PySide6.QtWidgets import QWidget

from snipline.overlay import chrome
from snipline.overlay.magnifier import LOUPE_SIZE, Magnifier
from snipline.overlay.mapping import local_to_physical, physical_to_local
from snipline.overlay.selection import Edge, SelectionModel
from snipline.platform.geometry import MonitorInfo
from snipline.ui import theme

__all__ = ["OverlayWindow"]

_DIM = QColor(0, 0, 0, 122)
_BORDER = QColor(theme.ACCENT)
_BORDER_WIDTH = 2

# How far the chrome -- border, handles, and the size readout sitting above the selection --
# extends beyond the selection itself. Used to widen partial repaints so none of it is left
# stale.
_CHROME_MARGIN = 64

# The loupe is repainted on every pointer move, so its area is invalidated on its own rather
# than by widening the selection repaint to reach it. Padding covers the readout strip and
# the flip to the opposite side of the cursor.
_LOUPE_MARGIN = LOUPE_SIZE + 64

_NUDGE_STEP_PX = 1
_ARROW_EDGES = {
    Qt.Key.Key_Left: (Edge.RIGHT, -_NUDGE_STEP_PX),
    Qt.Key.Key_Right: (Edge.RIGHT, _NUDGE_STEP_PX),
    Qt.Key.Key_Up: (Edge.BOTTOM, -_NUDGE_STEP_PX),
    Qt.Key.Key_Down: (Edge.BOTTOM, _NUDGE_STEP_PX),
}


class OverlayWindow(QWidget):
    """Frameless, always-on-top window covering exactly one screen."""

    committed = Signal()
    cancelled = Signal()
    selection_changed = Signal()

    def __init__(
        self,
        screen: QScreen,
        monitor: MonitorInfo,
        frozen: QPixmap,
        model: SelectionModel,
        show_magnifier: bool = True,
    ) -> None:
        super().__init__(None)
        self._monitor = monitor
        self._frozen = frozen
        self._model = model
        self._magnifier = Magnifier(frozen) if show_magnifier else None
        self._cursor: QPoint | None = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool  # keeps the overlay out of the taskbar and Alt-Tab
        )
        self.setCursor(Qt.CursorShape.CrossCursor)
        self.setMouseTracking(True)
        self.setScreen(screen)
        self.setGeometry(screen.geometry())
        self._painted: QRect | None = None

    def refresh(self) -> None:
        """Repaint only what the selection change can have altered.

        A full-screen invalidation per mouse-move event costs a whole 4K blit on every
        screen, which is what makes a rubber-band drag feel heavy. The area that can change
        is the old selection, the new one, and the chrome drawn around them.
        """
        current = self._local_selection()
        previous = self._painted
        self._painted = current

        if current is None or previous is None:
            self.update()  # appearing or clearing re-dims the whole screen
            return

        changed = current.united(previous)
        self.update(
            changed.adjusted(
                -_CHROME_MARGIN, -_CHROME_MARGIN, _CHROME_MARGIN, _CHROME_MARGIN
            )
        )

    def show_on_screen(self) -> None:
        self.showFullScreen()
        self.raise_()
        self.activateWindow()
        # Seed the pointer position rather than waiting for the first move event. Without
        # this the hint and the loupe are invisible until the user jiggles the mouse, which
        # is the one moment the hint is meant to be doing its job.
        local = self.mapFromGlobal(QCursor.pos())
        if self.rect().contains(local):
            self._cursor = local

    # -- painting ---------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self._frozen)

        selection = self._local_selection()
        if selection is None:
            painter.fillRect(self.rect(), _DIM)
            # Only the screen the pointer is on gets the hint. Repeating it on all three
            # screens of a multi-monitor desktop is three times the instruction and none of
            # the guidance.
            if self._cursor is not None:
                chrome.paint_hint(painter, self.rect())
            self._paint_magnifier(painter)
            painter.end()
            return

        # Dim everything except the selection, so the selected region shows the true
        # colours the user is about to capture.
        for band in self.surrounding_bands(selection):
            painter.fillRect(band, _DIM)

        # Outside the selection, never on it: a border drawn over the edge hides the very
        # pixels the user is lining the selection up against.
        painter.setPen(QPen(_BORDER, _BORDER_WIDTH))
        painter.drawRect(selection.adjusted(-_BORDER_WIDTH, -_BORDER_WIDTH, 0, 0))
        chrome.paint_handles(painter, selection)
        self._draw_size_label(painter, selection)
        self._paint_magnifier(painter)
        painter.end()

    def _paint_magnifier(self, painter: QPainter) -> None:
        if self._magnifier is None or self._cursor is None:
            return
        width = self.width()
        if width <= 0:
            return
        # Widget coordinates are logical; the frozen pixmap is physical. On a 150% screen
        # those differ by half again, and sampling the loupe at the widget's coordinates
        # would magnify the wrong pixels.
        ratio = self._frozen.width() / width
        self._magnifier.paint(painter, self._cursor, self.rect(), ratio)

    def surrounding_bands(self, selection: QRect) -> list[QRect]:
        """The four dim bands around the selection.

        Public so the tiling can be asserted directly; painting it is the only way it would
        otherwise be observable, and the overlay only renders on a real screen.

        ``QRect.right()`` and ``bottom()`` are the last contained row and column, not one
        past them, so the bands start one pixel further out. Off by one here dims the
        selection's own edge -- a visible lie about what is being captured, in the one
        place this project claims to be pixel-exact.
        """
        full = self.rect()
        band_height = selection.height()
        return [
            QRect(full.left(), full.top(), full.width(), selection.top() - full.top()),
            QRect(
                full.left(),
                selection.bottom() + 1,
                full.width(),
                full.bottom() - selection.bottom(),
            ),
            QRect(full.left(), selection.top(), selection.left() - full.left(), band_height),
            QRect(
                selection.right() + 1,
                selection.top(),
                full.right() - selection.right(),
                band_height,
            ),
        ]

    def _draw_size_label(self, painter: QPainter, selection: QRect) -> None:
        physical = self._model.rect
        if physical is None:
            return
        chrome.paint_size_readout(
            painter, selection, self.rect(), physical.width, physical.height
        )

    def _local_selection(self) -> QRect | None:
        physical = self._model.rect
        if physical is None or physical.is_empty:
            return None

        left, top = physical_to_local(self._monitor, physical.left, physical.top)
        right, bottom = physical_to_local(self._monitor, physical.right, physical.bottom)
        return QRect(left, top, right - left, bottom - top)

    # -- input ------------------------------------------------------------------

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() != Qt.MouseButton.LeftButton:
            return
        self._model.begin(*self._physical_position(event))
        self.selection_changed.emit()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        self._track_cursor(event.position().toPoint())
        if not self._model.is_dragging:
            return
        self._model.update(*self._physical_position(event))
        self.selection_changed.emit()

    def _track_cursor(self, position: QPoint) -> None:
        """Record the pointer and repaint only what the loupe covers.

        Mouse tracking is on, so this runs for every pointer move whether or not a drag is
        in progress. A full-screen invalidation here would blit the whole frozen pixmap on
        each one, which is precisely the cost ``refresh`` exists to avoid.
        """
        previous, self._cursor = self._cursor, position
        if self._magnifier is None:
            return

        stale = QRect(position, position)
        if previous is not None:
            stale = stale.united(QRect(previous, previous))
        self.update(stale.adjusted(-_LOUPE_MARGIN, -_LOUPE_MARGIN, _LOUPE_MARGIN, _LOUPE_MARGIN))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() != Qt.MouseButton.LeftButton or not self._model.is_dragging:
            return
        self._model.update(*self._physical_position(event))
        self.committed.emit()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt override
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self._model.cancel()
            self.cancelled.emit()
            return

        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.committed.emit()
            return

        nudge = _ARROW_EDGES.get(Qt.Key(key))
        if nudge is not None and self._model.rect is not None:
            edge, delta = nudge
            # Shift moves the opposite edge, which is how the top-left corner is adjusted
            # without redrawing the whole selection.
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                edge = Edge.LEFT if edge is Edge.RIGHT else Edge.TOP
            self._model.nudge(edge, delta)
            self.selection_changed.emit()

    def _physical_position(self, event: QMouseEvent) -> tuple[int, int]:
        point = event.position().toPoint()
        return local_to_physical(self._monitor, point.x(), point.y())
