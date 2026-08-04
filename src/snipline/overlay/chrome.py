"""Selection chrome: handles, the size readout, and the hint.

Split from ``window.py`` so that window stays a window -- it owns events and the frozen
pixmap, this owns what the selection looks like.

The geometry functions take and return plain rectangles and hold no Qt widget state, which
is what makes the handle placement assertable in a test. Painting a selection is otherwise
only observable on a real screen, and this application has exactly one screen to test on.

**Nothing here is ever drawn over the selection.** The border, the handles, and the readout
all sit outside it. That is not a style preference: the user is lining an edge up against
pixels underneath, and chrome covering those pixels is a lie about what is being captured,
in the one place this project claims to be exact.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen

from snipline.ui import theme

__all__ = [
    "HANDLE_GAP",
    "HANDLE_SIZE",
    "handle_rects",
    "hint_rect",
    "paint_handles",
    "paint_hint",
    "paint_size_readout",
]

HANDLE_SIZE = 9
# The clear space between a handle and the selection edge. One pixel, so the handles read as
# touching the frame while leaving every selected pixel visible.
HANDLE_GAP = 1

_HANDLE_FILL = QColor(theme.ACCENT)
_HANDLE_EDGE = QColor("#FFFFFF")
_HANDLE_EDGE_WIDTH = 1.4
_HANDLE_RADIUS = 2.0

# Below this, eight handles around the selection is more chrome than selection.
_MIN_SIZE_FOR_HANDLES = 28

_PILL_RADIUS = 7.0
_PILL_PAD_X = 10
_PILL_PAD_Y = 6
_PILL_MARGIN = 10
_PILL_BACKGROUND = QColor(11, 14, 20, 235)
_PILL_BORDER = QColor(255, 255, 255, 26)

_HINT_TEXT = "Drag to select    ·    Esc to cancel"
_HINT_BOTTOM_MARGIN = 56


def handle_rects(selection: QRect) -> list[QRectF]:
    """The eight grips, all outside ``selection``.

    Corners first, then edge midpoints. Empty when the selection is too small to carry them
    without burying itself.
    """
    if selection.width() < _MIN_SIZE_FOR_HANDLES or selection.height() < _MIN_SIZE_FOR_HANDLES:
        return []

    half = HANDLE_SIZE / 2.0
    offset = half + HANDLE_GAP

    # QRect.right() is the last contained column, not one past it, so the outer edge is
    # right() + 1. Off by one here is the difference between handles that hug the frame and
    # handles that sit a pixel inside it.
    left, top = float(selection.left()), float(selection.top())
    right, bottom = float(selection.right() + 1), float(selection.bottom() + 1)
    middle_x, middle_y = (left + right) / 2.0, (top + bottom) / 2.0

    centres = (
        (left - offset, top - offset),
        (right + offset, top - offset),
        (left - offset, bottom + offset),
        (right + offset, bottom + offset),
        (middle_x, top - offset),
        (middle_x, bottom + offset),
        (left - offset, middle_y),
        (right + offset, middle_y),
    )
    return [QRectF(x - half, y - half, HANDLE_SIZE, HANDLE_SIZE) for x, y in centres]


def paint_handles(painter: QPainter, selection: QRect) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(_HANDLE_FILL)
    painter.setPen(QPen(_HANDLE_EDGE, _HANDLE_EDGE_WIDTH))
    for rect in handle_rects(selection):
        painter.drawRoundedRect(rect, _HANDLE_RADIUS, _HANDLE_RADIUS)
    painter.restore()


def _pill_rect(metrics: QFontMetrics, text: str) -> QRectF:
    bounds = metrics.boundingRect(text)
    return QRectF(
        0.0,
        0.0,
        float(bounds.width() + _PILL_PAD_X * 2),
        float(metrics.height() + _PILL_PAD_Y * 2),
    )


def _paint_pill(painter: QPainter, rect: QRectF, text: str, colour: QColor) -> None:
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(_PILL_BACKGROUND)
    painter.setPen(QPen(_PILL_BORDER, 1.0))
    painter.drawRoundedRect(rect, _PILL_RADIUS, _PILL_RADIUS)
    painter.setPen(colour)
    painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), text)
    painter.restore()


def size_readout_rect(painter: QPainter, selection: QRect, bounds: QRect) -> QRectF:
    """Where the dimensions pill goes: above the selection, inside it when there is no room.

    Kept separate from the painting so the placement rule is assertable.
    """
    rect = _pill_rect(painter.fontMetrics(), "0000 x 0000")
    x = float(selection.left())
    y = float(selection.top()) - rect.height() - _PILL_MARGIN

    if y < bounds.top():
        y = float(selection.top()) + _PILL_MARGIN
    # Keep it on screen when the selection starts near the right edge.
    if x + rect.width() > bounds.right():
        x = float(bounds.right()) - rect.width()
    rect.moveTopLeft(QPointF(max(x, float(bounds.left())), y))
    return rect


def paint_size_readout(
    painter: QPainter, selection: QRect, bounds: QRect, width: int, height: int
) -> None:
    """Draw the physical pixel dimensions of the pending capture.

    Physical, not logical: the number shown has to be the size of the file the user ends up
    with, or it is decoration.
    """
    # The multiplication sign, not the letter x. It is the one character in the overlay a
    # user actually reads, and 'x' next to digits looks like a variable.
    text = f"{width} × {height}"
    rect = _pill_rect(painter.fontMetrics(), text)
    placed = size_readout_rect(painter, selection, bounds)
    rect.moveTopLeft(placed.topLeft())
    _paint_pill(painter, rect, text, QColor(theme.TEXT_PRIMARY))


def hint_rect(painter: QPainter, bounds: QRect) -> QRectF:
    """Low and centred, not in the middle of the screen.

    The middle is where the pointer usually is when the overlay opens, and the loupe is
    drawn at the pointer -- centring the hint puts the two on top of each other and leaves
    the instruction half readable. Low and centred is also where this category of tool
    conventionally puts it.
    """
    rect = _pill_rect(painter.fontMetrics(), _HINT_TEXT)
    rect.moveCenter(QPointF(bounds.center()))
    rect.moveBottom(float(bounds.bottom()) - _HINT_BOTTOM_MARGIN)
    return rect


def paint_hint(painter: QPainter, bounds: QRect) -> None:
    """The pre-selection prompt.

    Shown only before a drag begins. A hint that stayed up during the drag would be chrome
    sitting over the very pixels being framed.
    """
    font = QFont(painter.font())
    font.setPointSizeF(font.pointSizeF() + 1.0)
    painter.save()
    painter.setFont(font)
    _paint_pill(painter, hint_rect(painter, bounds), _HINT_TEXT, QColor(theme.TEXT_MUTED))
    painter.restore()
