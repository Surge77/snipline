"""Text annotation.

A click places an editable text item and focuses it, rather than opening a dialog: typing
straight onto the image is the whole point, and a modal would hide the thing being labelled.

``QGraphicsTextItem`` is used unmodified so IME composition and emoji work -- both are
common in screenshots and neither survives a hand-rolled text item.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QGraphicsItem, QGraphicsTextItem

from snipline.editor.style import DEFAULT_STYLE, ToolStyle

__all__ = ["TextItem", "TextTool"]

# Font size tracks stroke width so the width control means "bigger annotation" for every
# tool rather than being meaningless for this one.
FONT_SIZE_FACTOR = 4
MIN_FONT_SIZE_PT = 10


class TextItem(QGraphicsTextItem):
    """Editable text placed on the capture."""

    def __init__(self, style: ToolStyle) -> None:
        super().__init__()
        self.setDefaultTextColor(QColor(style.colour))

        font = QFont()
        font.setPointSize(max(MIN_FONT_SIZE_PT, style.width * FONT_SIZE_FACTOR))
        font.setBold(True)  # readable over busy screenshots
        self.setFont(font)

        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setTextInteractionFlags(Qt.TextInteractionFlag.TextEditorInteraction)

    @property
    def is_empty(self) -> bool:
        return not self.toPlainText().strip()


class TextTool:
    name = "text"
    label = "Add text"

    def __init__(self, style: ToolStyle = DEFAULT_STYLE) -> None:
        self._style = style
        self._item: TextItem | None = None

    @property
    def style(self) -> ToolStyle:
        return self._style

    def press(self, position: QPointF) -> QGraphicsItem | None:
        item = TextItem(self._style)
        item.setPos(position)
        self._item = item
        return item

    def move(self, position: QPointF) -> None:
        # Text is placed, not dragged. Dragging to size it would fight the text cursor.
        return

    def release(self, position: QPointF) -> QGraphicsItem | None:
        item = self._item
        self._item = None
        if item is None:
            return None

        item.setFocus()
        # Committed while still empty, because the user is about to type into it and an
        # item that vanished on mouse-release would be unusable. An abandoned empty item
        # paints nothing and is removed with a single Ctrl+Z, so it is not worth teaching
        # the editor a text-specific cleanup rule to avoid.
        return item
