"""Rectangle and ellipse tools.

Both are the same gesture -- drag a bounding box -- differing only in what they draw, so they
share a base rather than duplicating the state machine. Written against the same interface
as the arrow tool, with no editor changes.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import (
    QGraphicsEllipseItem,
    QGraphicsItem,
    QGraphicsRectItem,
)

from snipline.editor.style import DEFAULT_STYLE, ToolStyle

__all__ = ["EllipseTool", "RectangleTool", "rect_from_drag"]

# Smaller than this in either direction and the gesture was a click, not a shape.
MIN_EXTENT_PX = 4.0


def rect_from_drag(start: QPointF, end: QPointF) -> QRectF:
    """Normalise a drag into a rect.

    Dragging up and to the left is ordinary, and would otherwise yield negative width and
    height that paint as nothing.
    """
    return QRectF(
        min(start.x(), end.x()),
        min(start.y(), end.y()),
        abs(end.x() - start.x()),
        abs(end.y() - start.y()),
    )


def _configure(item: QGraphicsItem, style: ToolStyle) -> None:
    pen = QPen(QColor(style.colour), style.width)
    pen.setJoinStyle(pen.joinStyle().MiterJoin)
    # Both shapes are outlines. A filled rectangle is what the solid redaction tool is for,
    # and conflating them would make an annotation look like a redaction.
    if isinstance(item, QGraphicsRectItem | QGraphicsEllipseItem):
        item.setPen(pen)
    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
    item.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)


class _BoxTool:
    """Shared press-drag-release box gesture."""

    name = "box"
    label = "Add shape"

    def __init__(self, style: ToolStyle = DEFAULT_STYLE) -> None:
        self._style = style
        self._item: QGraphicsRectItem | QGraphicsEllipseItem | None = None
        self._start = QPointF()

    @property
    def style(self) -> ToolStyle:
        return self._style

    def _create(self) -> QGraphicsRectItem | QGraphicsEllipseItem:
        raise NotImplementedError

    def press(self, position: QPointF) -> QGraphicsItem | None:
        self._start = position
        item = self._create()
        _configure(item, self._style)
        item.setRect(QRectF(position, position))
        self._item = item
        return item

    def move(self, position: QPointF) -> None:
        if self._item is not None:
            self._item.setRect(rect_from_drag(self._start, position))

    def release(self, position: QPointF) -> QGraphicsItem | None:
        item = self._item
        self._item = None
        if item is None:
            return None

        rect = rect_from_drag(self._start, position)
        item.setRect(rect)
        if rect.width() < MIN_EXTENT_PX and rect.height() < MIN_EXTENT_PX:
            return None
        return item


class RectangleTool(_BoxTool):
    name = "rectangle"
    label = "Add rectangle"

    def _create(self) -> QGraphicsRectItem:
        return QGraphicsRectItem()


class EllipseTool(_BoxTool):
    name = "ellipse"
    label = "Add ellipse"

    def _create(self) -> QGraphicsEllipseItem:
        return QGraphicsEllipseItem()
