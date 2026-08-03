"""Undo commands.

The scene-graph decision (D6) exists so undo is a stack of small commands rather than a
stack of whole-image snapshots. On a 4K capture each snapshot would be tens of megabytes and
memory would grow with edit count; here an undone annotation costs one pointer.

An undone item is *removed from the scene but still owned by the command*, which is what
keeps redo able to restore it with its styling and position intact.
"""

from __future__ import annotations

from typing import cast

from PySide6.QtGui import QUndoCommand
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

__all__ = ["AddItemCommand", "RemoveItemCommand", "owning_scene"]


def owning_scene(item: QGraphicsItem) -> QGraphicsScene | None:
    """The scene holding ``item``, or None when it belongs to none.

    Qt's type stubs declare ``QGraphicsItem.scene()`` as non-optional, but it genuinely
    returns null for an item that has been removed -- which is the entire state an undone
    command leaves behind. The cast restores the truth rather than suppressing the checker
    at each call site.
    """
    return cast("QGraphicsScene | None", item.scene())


class AddItemCommand(QUndoCommand):
    """Adds one annotation to the scene."""

    def __init__(self, scene: QGraphicsScene, item: QGraphicsItem, label: str) -> None:
        super().__init__(label)
        self._scene = scene
        self._item = item

    @property
    def item(self) -> QGraphicsItem:
        return self._item

    def redo(self) -> None:
        # Idempotent, because the tool has usually already put the item in the scene during
        # the drag. Adding it twice would be a Qt error; removing and re-adding it would
        # flicker. Checking is cheaper than coordinating.
        if owning_scene(self._item) is None:
            self._scene.addItem(self._item)

    def undo(self) -> None:
        self._scene.removeItem(self._item)


class RemoveItemCommand(QUndoCommand):
    """Deletes one annotation."""

    def __init__(self, scene: QGraphicsScene, item: QGraphicsItem, label: str) -> None:
        super().__init__(label)
        self._scene = scene
        self._item = item

    @property
    def item(self) -> QGraphicsItem:
        return self._item

    def redo(self) -> None:
        if owning_scene(self._item) is not None:
            self._scene.removeItem(self._item)

    def undo(self) -> None:
        if owning_scene(self._item) is None:
            self._scene.addItem(self._item)
