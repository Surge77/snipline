"""Numbered step badges.

Each click drops the next number, which is what makes the tool worth having: annotating a
six-step workflow means six clicks, not six text items typed by hand.

The counter lives on the tool instance, so a fresh editor starts at 1 while a continuing
session keeps counting.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen
from PySide6.QtWidgets import QGraphicsItem, QStyleOptionGraphicsItem, QWidget

from snipline.editor.style import DEFAULT_STYLE, ToolStyle

__all__ = ["StepBadgeItem", "StepTool"]

RADIUS_FACTOR = 3.5
MIN_RADIUS_PX = 12.0
FIRST_STEP = 1

_OUTLINE_COLOUR = "#FFFFFF"
_OUTLINE_WIDTH = 2


class StepBadgeItem(QGraphicsItem):
    """A filled circle with a number in it."""

    def __init__(self, number: int, style: ToolStyle) -> None:
        super().__init__()
        self._number = number
        self._style = style
        self._radius = max(MIN_RADIUS_PX, style.width * RADIUS_FACTOR)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

    @property
    def number(self) -> int:
        return self._number

    @property
    def radius(self) -> float:
        return self._radius

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt override
        # Grown by the outline width so the white ring is not clipped.
        extent = self._radius + _OUTLINE_WIDTH
        return QRectF(-extent, -extent, extent * 2, extent * 2)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        circle = QRectF(
            -self._radius, -self._radius, self._radius * 2, self._radius * 2
        )

        # White outline so the badge stays legible on a screenshot that happens to be the
        # same colour as the badge.
        painter.setPen(QPen(QColor(_OUTLINE_COLOUR), _OUTLINE_WIDTH))
        painter.setBrush(QBrush(QColor(self._style.colour)))
        painter.drawEllipse(circle)

        font = QFont()
        font.setPointSizeF(self._radius)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QPen(QColor(_OUTLINE_COLOUR)))
        painter.drawText(circle, int(Qt.AlignmentFlag.AlignCenter), str(self._number))


class StepTool:
    name = "step"
    label = "Add step badge"

    def __init__(self, style: ToolStyle = DEFAULT_STYLE, start_at: int = FIRST_STEP) -> None:
        self._style = style
        self._next = start_at
        self._item: StepBadgeItem | None = None

    @property
    def style(self) -> ToolStyle:
        return self._style

    @property
    def next_number(self) -> int:
        return self._next

    def reset(self, start_at: int = FIRST_STEP) -> None:
        self._next = start_at

    def press(self, position: QPointF) -> QGraphicsItem | None:
        item = StepBadgeItem(self._next, self._style)
        item.setPos(position)
        self._item = item
        return item

    def move(self, position: QPointF) -> None:
        # Dragging repositions the badge before it is committed.
        if self._item is not None:
            self._item.setPos(position)

    def release(self, position: QPointF) -> QGraphicsItem | None:
        item = self._item
        self._item = None
        if item is None:
            return None

        item.setPos(position)
        # Advanced only on a committed badge, so a cancelled gesture does not leave a gap
        # in the numbering.
        self._next += 1
        return item
