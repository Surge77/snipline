"""Freehand drawing.

Points are accumulated during the drag and appended to the path. Mouse move events already
arrive coalesced by Qt, so no additional smoothing is applied -- a hand-drawn circle should
look hand-drawn rather than be silently corrected into something the user did not draw.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtGui import QColor, QPainterPath, QPen
from PySide6.QtWidgets import QGraphicsItem, QGraphicsPathItem

from snipline.editor.style import DEFAULT_STYLE, ToolStyle

__all__ = ["FreehandItem", "FreehandTool"]

# Total path length below this was a click, not a stroke.
MIN_STROKE_LENGTH_PX = 4.0

# Points closer together than this add nothing visible but do add to the path's element
# count, which costs on every repaint of a long stroke.
MIN_POINT_SPACING_PX = 1.0


class FreehandItem(QGraphicsPathItem):
    """One continuous stroke."""

    def __init__(self, start: QPointF, style: ToolStyle) -> None:
        super().__init__()
        self._last = start
        self._count = 1
        self._length = 0.0
        # Extended by one segment per move rather than rebuilt from the full point list.
        # Rebuilding replayed every previous segment on every mouse-move event, so a long
        # stroke got slower the longer it grew -- which is exactly when drawing has to stay
        # responsive.
        self._path = QPainterPath(start)

        pen = QPen(QColor(style.colour), style.width)
        pen.setCapStyle(pen.capStyle().RoundCap)
        pen.setJoinStyle(pen.joinStyle().RoundJoin)
        self.setPen(pen)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setPath(self._path)

    @property
    def point_count(self) -> int:
        return self._count

    @property
    def length(self) -> float:
        return self._length

    def add_point(self, point: QPointF) -> bool:
        """Extend the stroke. False when the point was too close to be worth keeping."""
        step = (point - self._last).manhattanLength()
        if step < MIN_POINT_SPACING_PX:
            return False

        self._path.lineTo(point)
        self._last = point
        self._count += 1
        self._length += step
        self.setPath(self._path)
        return True


class FreehandTool:
    name = "freehand"
    label = "Draw freehand"

    def __init__(self, style: ToolStyle = DEFAULT_STYLE) -> None:
        self._style = style
        self._item: FreehandItem | None = None

    @property
    def style(self) -> ToolStyle:
        return self._style

    def press(self, position: QPointF) -> QGraphicsItem | None:
        self._item = FreehandItem(position, self._style)
        return self._item

    def move(self, position: QPointF) -> None:
        if self._item is not None:
            self._item.add_point(position)

    def release(self, position: QPointF) -> QGraphicsItem | None:
        item = self._item
        self._item = None
        if item is None:
            return None

        item.add_point(position)
        return item if item.length >= MIN_STROKE_LENGTH_PX else None
