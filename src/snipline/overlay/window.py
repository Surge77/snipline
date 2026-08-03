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
    QGuiApplication,
    QKeyEvent,
    QMouseEvent,
    QPainter,
    QPaintEvent,
    QPen,
    QPixmap,
    QScreen,
)
from PySide6.QtWidgets import QWidget

from snipline.overlay.mapping import local_to_physical, physical_to_local
from snipline.overlay.selection import Edge, SelectionModel
from snipline.platform.geometry import MonitorInfo

__all__ = ["OverlayWindow"]

_DIM = QColor(0, 0, 0, 110)
_BORDER = QColor("#3B82F6")
_BORDER_WIDTH = 2
_LABEL_MARGIN = 8
_LABEL_PADDING = 6
_LABEL_BACKGROUND = QColor(17, 24, 39, 220)

# Slack allowed when matching a Qt screen to a Win32 monitor by origin. Wide enough to
# absorb the rounding in Qt's logical-to-physical reconstruction, far narrower than the
# hundreds of pixels separating any two real monitors.
_ORIGIN_TOLERANCE_PX = 4

# How far the chrome -- border and the size label sitting above the selection -- extends
# beyond the selection itself. Used to widen partial repaints so none of it is left stale.
_CHROME_MARGIN = 64

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
    ) -> None:
        super().__init__(None)
        self._monitor = monitor
        self._frozen = frozen
        self._model = model

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

    # -- painting ---------------------------------------------------------------

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt override
        painter = QPainter(self)
        painter.drawPixmap(self.rect(), self._frozen)

        selection = self._local_selection()
        if selection is None:
            painter.fillRect(self.rect(), _DIM)
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
        self._draw_size_label(painter, selection)
        painter.end()

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

        # Physical pixels, not logical: the number shown must be the size of the file the
        # user ends up with.
        text = f"{physical.width} x {physical.height}"
        metrics = painter.fontMetrics()
        box = metrics.boundingRect(text).adjusted(
            -_LABEL_PADDING, -_LABEL_PADDING, _LABEL_PADDING, _LABEL_PADDING
        )

        anchor = QPoint(selection.left(), selection.top() - box.height() - _LABEL_MARGIN)
        if anchor.y() < 0:  # selection is against the top edge; put the label inside it
            anchor.setY(selection.top() + _LABEL_MARGIN)
        box.moveTopLeft(anchor)

        painter.fillRect(box, _LABEL_BACKGROUND)
        painter.setPen(QColor("#FFFFFF"))
        painter.drawText(box, int(Qt.AlignmentFlag.AlignCenter), text)

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
        if not self._model.is_dragging:
            return
        self._model.update(*self._physical_position(event))
        self.selection_changed.emit()

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


def screen_for(monitor: MonitorInfo) -> QScreen | None:
    """Find the QScreen matching a monitor, by physical origin.

    Matched on position rather than index: Qt's screen order and the Win32 enumeration
    order are independently defined and do not have to agree.

    The match is nearest-origin rather than exact. Qt reports logical geometry, so
    reconstructing a physical origin from it rounds, and on a mixed-DPI desktop the rounding
    error accumulates across screens. Demanding an exact hit means one stray pixel drops the
    screen from the overlay -- and if it happens on every screen, the hotkey silently does
    nothing, which is this application's worst failure mode.
    """
    best: QScreen | None = None
    best_distance = _ORIGIN_TOLERANCE_PX
    for screen in QGuiApplication.screens():
        geometry = screen.geometry()
        ratio = screen.devicePixelRatio()
        distance = max(
            abs(round(geometry.left() * ratio) - monitor.bounds.left),
            abs(round(geometry.top() * ratio) - monitor.bounds.top),
        )
        if distance < best_distance:
            best, best_distance = screen, distance
    return best
