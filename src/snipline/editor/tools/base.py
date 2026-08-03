"""The tool interface.

Every annotation tool is a small state machine over three events. The editor owns the scene
and the undo stack; a tool owns only the item it is currently drawing.

The interface is the contract that keeps M5 cheap: adding rectangle, ellipse, freehand,
text, step badges, and the redaction tools must require **zero** edits to the editor. If a
new tool forces an editor change, the interface is wrong and should be fixed rather than
worked around.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QGraphicsItem

from snipline.editor.style import ToolStyle

__all__ = ["Tool"]


@runtime_checkable
class Tool(Protocol):
    """Draws one annotation per press-drag-release."""

    name: str
    label: str

    @property
    def style(self) -> ToolStyle: ...

    def press(self, position: QPointF) -> QGraphicsItem | None:
        """Begin drawing. Returns the item to show during the drag, if any.

        The editor adds the returned item to the scene immediately so the user sees the
        annotation follow the cursor; it is wrapped in an undo command only on release.
        """
        ...

    def move(self, position: QPointF) -> None:
        """Update the in-progress item. Called only while drawing."""
        ...

    def release(self, position: QPointF) -> QGraphicsItem | None:
        """Finish. Returns the item to commit, or None to discard it.

        Returning None is how a tool rejects a degenerate gesture -- a click with no drag
        would otherwise leave an invisible zero-length annotation in the scene that the
        user cannot select or delete.
        """
        ...
