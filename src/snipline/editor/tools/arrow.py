"""Arrow tool -- the reference implementation of the tool interface.

The arrowhead is drawn as part of the item's own path rather than as a separate item, so an
arrow is one selectable, movable, undoable thing. Its size is tied to stroke width, because
a fixed-size head looks wrong at either extreme of the width range.
"""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem

from snipline.editor.style import DEFAULT_STYLE, ToolStyle

__all__ = ["ArrowItem", "ArrowTool", "arrow_path"]

# Multiples of stroke width, so the head scales with the line it terminates.
HEAD_LENGTH_FACTOR = 4.0
HEAD_HALF_ANGLE_RADIANS = math.pi / 7

# Shorter than this and the gesture is a click, not an arrow.
MIN_ARROW_LENGTH_PX = 6.0


def arrow_path(start: QPointF, end: QPointF, width: int) -> QPainterPath:
    """Shaft plus a two-stroke head. Pure geometry, so it is tested directly."""
    path = QPainterPath(start)
    path.lineTo(end)

    dx, dy = end.x() - start.x(), end.y() - start.y()
    length = math.hypot(dx, dy)
    if length < MIN_ARROW_LENGTH_PX:
        return path

    angle = math.atan2(dy, dx)
    head = HEAD_LENGTH_FACTOR * width
    for sign in (1, -1):
        barb = angle + sign * HEAD_HALF_ANGLE_RADIANS
        path.moveTo(end)
        path.lineTo(
            end.x() - head * math.cos(barb),
            end.y() - head * math.sin(barb),
        )
    return path


class ArrowItem(QGraphicsPathItem):
    """One arrow. Selectable and movable, per D6."""

    def __init__(self, start: QPointF, style: ToolStyle) -> None:
        super().__init__()
        self._start = start
        self._end = start
        self._style = style

        pen = QPen(QColor(style.colour), style.width)
        pen.setCapStyle(pen.capStyle().RoundCap)
        pen.setJoinStyle(pen.joinStyle().RoundJoin)
        self.setPen(pen)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self._rebuild()

    @property
    def start(self) -> QPointF:
        return self._start

    @property
    def end(self) -> QPointF:
        return self._end

    @property
    def length(self) -> float:
        return math.hypot(self._end.x() - self._start.x(), self._end.y() - self._start.y())

    def set_end(self, end: QPointF) -> None:
        self._end = end
        self._rebuild()

    def _rebuild(self) -> None:
        self.setPath(arrow_path(self._start, self._end, self._style.width))


class ArrowTool:
    """Press to anchor the tail, drag to aim, release to commit."""

    name = "arrow"
    label = "Add arrow"

    def __init__(self, style: ToolStyle = DEFAULT_STYLE) -> None:
        self._style = style
        self._item: ArrowItem | None = None

    @property
    def style(self) -> ToolStyle:
        return self._style

    def press(self, position: QPointF) -> QGraphicsItem | None:
        self._item = ArrowItem(position, self._style)
        return self._item

    def move(self, position: QPointF) -> None:
        if self._item is not None:
            self._item.set_end(position)

    def release(self, position: QPointF) -> QGraphicsItem | None:
        item = self._item
        self._item = None
        if item is None:
            return None

        item.set_end(position)
        # A click with no drag would otherwise leave an invisible zero-length arrow that
        # the user can neither see nor select to delete.
        return item if item.length >= MIN_ARROW_LENGTH_PX else None
