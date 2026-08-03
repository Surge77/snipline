"""The annotation scene and the editing controller.

The captured pixmap is the scene background rather than an item, so it can never be
selected, moved, or deleted by a stray click -- and so ``QGraphicsScene.render`` flattens
annotations over it in one pass at export.

The controller is the piece M5 must not have to touch: it routes three mouse events to
whichever tool is active and wraps whatever comes back in an undo command. It knows nothing
about arrows.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRect, QRectF
from PySide6.QtGui import QImage, QPainter, QPixmap, QUndoStack
from PySide6.QtWidgets import QGraphicsItem, QGraphicsScene

from snipline.capture.frame import Frame
from snipline.editor.commands import AddItemCommand, RemoveItemCommand, owning_scene
from snipline.editor.tools.base import Tool
from snipline.export.clipboard import frame_to_qimage

__all__ = ["AnnotationScene", "EditorController"]


class AnnotationScene(QGraphicsScene):
    """A captured frame with annotations on top."""

    def __init__(self, frame: Frame) -> None:
        super().__init__()
        self._background = QPixmap.fromImage(frame_to_qimage(frame))
        # Scene coordinates are the capture's physical pixels, one to one. Any other choice
        # would put a scale factor between what the user draws and what gets exported.
        self.setSceneRect(QRectF(0, 0, frame.width, frame.height))

    @property
    def background(self) -> QPixmap:
        return self._background

    def drawBackground(  # noqa: N802 - Qt override
        self, painter: QPainter, rect: QRectF | QRect
    ) -> None:
        painter.drawPixmap(self.sceneRect(), self._background, QRectF(self._background.rect()))

    def annotations(self) -> list[QGraphicsItem]:
        return list(self.items())

    def flatten(self) -> QImage:
        """Render the background and every annotation into one image.

        Rendered at the scene's own resolution, which is the capture's physical size. This
        is the M6 trap stated early: rendering at *view* resolution silently downscales the
        export on a high-DPI monitor.
        """
        image = QImage(
            int(self.sceneRect().width()),
            int(self.sceneRect().height()),
            QImage.Format.Format_RGB32,
        )
        painter = QPainter(image)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.render(painter, QRectF(image.rect()), self.sceneRect())
        painter.end()
        return image


class EditorController:
    """Routes mouse events to the active tool and records the result as undo commands.

    Deliberately free of any per-tool knowledge: adding a tool in M5 must not require
    editing this class.
    """

    def __init__(
        self,
        scene: AnnotationScene,
        tool: Tool,
        undo_stack: QUndoStack | None = None,
    ) -> None:
        self._scene = scene
        self._tool = tool
        self._undo_stack = undo_stack or QUndoStack()
        self._drawing = False

    @property
    def scene(self) -> AnnotationScene:
        return self._scene

    @property
    def undo_stack(self) -> QUndoStack:
        return self._undo_stack

    @property
    def tool(self) -> Tool:
        return self._tool

    @property
    def is_drawing(self) -> bool:
        return self._drawing

    def set_tool(self, tool: Tool) -> None:
        """Switch tools. Any half-drawn annotation is discarded rather than committed."""
        self.abort()
        self._tool = tool

    def press(self, position: QPointF) -> None:
        draft = self._tool.press(position)
        self._drawing = True
        if draft is not None and owning_scene(draft) is None:
            # Shown immediately so the annotation follows the cursor; it becomes undoable
            # only on release.
            self._scene.addItem(draft)

    def move(self, position: QPointF) -> None:
        if self._drawing:
            self._tool.move(position)

    def release(self, position: QPointF) -> QGraphicsItem | None:
        if not self._drawing:
            return None

        self._drawing = False
        committed = self._tool.release(position)
        if committed is None:
            self._discard_drafts()
            return None

        self._undo_stack.push(AddItemCommand(self._scene, committed, self._tool.label))
        return committed

    def delete(self, item: QGraphicsItem) -> None:
        self._undo_stack.push(RemoveItemCommand(self._scene, item, "Delete annotation"))

    def abort(self) -> None:
        """Drop an in-progress annotation without recording it."""
        if self._drawing:
            self._drawing = False
            self._discard_drafts()

    def _discard_drafts(self) -> None:
        # A rejected draft is already in the scene but never reached the undo stack, so
        # nothing else will ever remove it.
        for item in self._scene.items():
            if owning_scene(item) is not None and not self._is_committed(item):
                self._scene.removeItem(item)

    def _is_committed(self, item: QGraphicsItem) -> bool:
        for index in range(self._undo_stack.count()):
            command = self._undo_stack.command(index)
            if isinstance(command, AddItemCommand) and command.item is item:
                return True
        return False
