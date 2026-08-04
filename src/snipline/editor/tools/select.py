"""Selecting and moving annotations already on the capture.

Every annotation item is created selectable and movable, but nothing could reach those flags:
the view routed all three mouse events to the active drawing tool and never to the scene, so
a placed item could not be picked up, and a text item could not have its caret positioned.

This tool draws nothing. Its presence is the signal to the view that mouse events belong to
the scene for the duration -- which is what makes a dragged redaction re-sample the area it
now covers (D7), rather than that behaviour existing only in the paint code that implements
it.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsItem

from snipline.editor.style import DEFAULT_STYLE, ToolStyle

__all__ = ["SELECT_TOOL_NAME", "SelectTool"]

SELECT_TOOL_NAME = "select"


class SelectTool:
    """Hands the scene its own mouse events instead of drawing."""

    name = SELECT_TOOL_NAME
    label = "Select"

    def __init__(self, style: ToolStyle = DEFAULT_STYLE) -> None:
        self._style = style

    @property
    def style(self) -> ToolStyle:
        return self._style

    def press(self, position: QPointF) -> QGraphicsItem | None:
        return None

    def move(self, position: QPointF) -> None:
        return

    def release(self, position: QPointF) -> QGraphicsItem | None:
        return None
