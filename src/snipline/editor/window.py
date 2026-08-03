"""The editor window.

Thin by design: a view onto the scene, a toolbar, and keyboard shortcuts. All editing logic
lives in ``EditorController``, and every tool lives under ``tools/``, so the M5 work of
adding rectangle, ellipse, text, and redaction tools should not require touching this file.

The view maps its own mouse events into scene coordinates, which are the capture's physical
pixels one-to-one. Zooming changes the transform, never the scene, so an annotation drawn
while zoomed lands on the same pixels it appeared to.
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QKeySequence,
    QMouseEvent,
    QPainter,
    QScreen,
)
from PySide6.QtWidgets import QGraphicsView, QMainWindow, QWidget

from snipline.capture.frame import Frame
from snipline.editor.scene import AnnotationScene, EditorController
from snipline.editor.style import DEFAULT_STYLE, ToolStyle
from snipline.editor.toolbar import StyleBar, build_tool_actions
from snipline.editor.tools.arrow import ArrowTool
from snipline.editor.tools.registry import build_tool

__all__ = ["EditorView", "EditorWindow"]

_MIN_WINDOW_SIZE = (480, 360)
# Leaves room for the toolbar and window chrome so a full-screen capture still opens as a
# window rather than something taller than the display it opened on.
_SCREEN_FRACTION = 0.8


class EditorView(QGraphicsView):
    """Forwards mouse events to the controller in scene coordinates."""

    def __init__(self, controller: EditorController, parent: QWidget | None = None) -> None:
        super().__init__(controller.scene, parent)
        self._controller = controller
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _scene_position(self, event: QMouseEvent) -> QPointF:
        return self.mapToScene(event.position().toPoint())

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton:
            self._controller.press(self._scene_position(event))

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        self._controller.move(self._scene_position(event))

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802 - Qt override
        if event.button() == Qt.MouseButton.LeftButton:
            self._controller.release(self._scene_position(event))


class EditorWindow(QMainWindow):
    """Holds one captured frame and its annotations."""

    export_requested = Signal()
    copy_requested = Signal()
    closed = Signal()

    def __init__(self, frame: Frame, style: ToolStyle = DEFAULT_STYLE) -> None:
        super().__init__()
        self._controller = EditorController(scene=AnnotationScene(frame), tool=ArrowTool(style))
        self._view = EditorView(self._controller)

        self.setWindowTitle(f"Snipline — {frame.width} x {frame.height}")
        self.setCentralWidget(self._view)
        self.setMinimumSize(*_MIN_WINDOW_SIZE)
        self._style = style
        self._tool_name = "arrow"
        self._build_actions()
        self._build_tool_bar()

    @property
    def controller(self) -> EditorController:
        return self._controller

    @property
    def view(self) -> EditorView:
        return self._view

    def _build_actions(self) -> None:
        undo_stack = self._controller.undo_stack

        undo = undo_stack.createUndoAction(self, "Undo")
        undo.setShortcut(QKeySequence.StandardKey.Undo)
        redo = undo_stack.createRedoAction(self, "Redo")
        # Both Ctrl+Y and Ctrl+Shift+Z: the first is the Windows convention, the second is
        # what anyone arriving from a design tool will press.
        redo.setShortcuts(
            [QKeySequence(QKeySequence.StandardKey.Redo), QKeySequence("Ctrl+Shift+Z")]
        )

        copy = QAction("Copy", self)
        copy.setShortcut(QKeySequence.StandardKey.Copy)
        copy.triggered.connect(self.copy_requested)

        save = QAction("Save", self)
        save.setShortcut(QKeySequence.StandardKey.Save)
        save.triggered.connect(self.export_requested)

        close = QAction("Close", self)
        close.setShortcut(QKeySequence(Qt.Key.Key_Escape))
        close.triggered.connect(self.close)

        toolbar = self.addToolBar("Edit")
        for action in (undo, redo, copy, save):
            toolbar.addAction(action)
        self.addAction(close)

    def _build_tool_bar(self) -> None:
        toolbar = self.addToolBar("Tools")
        _group, actions = build_tool_actions(self, self.select_tool)
        for action in actions:
            toolbar.addAction(action)

        toolbar.addSeparator()
        self._style_bar = StyleBar(self._style, self)
        self._style_bar.style_changed.connect(self.set_style)
        self._style_bar.add_to(toolbar)

    def select_tool(self, name: str) -> None:
        """Switch to a registered tool by name."""
        self._tool_name = name
        self._controller.set_tool(build_tool(name, self._style))

    def set_style(self, style: ToolStyle) -> None:
        """Apply colour and width to subsequent annotations."""
        # Style applies to the next annotation, not retroactively to existing ones: an
        # edit that silently restyled work already done would be surprising and is not
        # undoable through the same command stack.
        self._style = style
        self._controller.set_tool(build_tool(self._tool_name, style))

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        # An explicit signal rather than QObject.destroyed: destroyed fires while the C++
        # object is being torn down, and anything it reaches that also holds a reference to
        # this window is reading memory Qt is in the middle of freeing.
        self.closed.emit()
        super().closeEvent(event)

    def fit_to_screen(self) -> None:
        """Size the window to the capture, bounded by the screen it opens on."""
        # Qt's stub says screen() is non-optional; it returns null for a window that has
        # not been shown or mapped to a display yet.
        screen = cast("QScreen | None", self.screen())
        if screen is None:
            return

        available = screen.availableGeometry()
        scene_rect = self._controller.scene.sceneRect()
        width = min(int(scene_rect.width()), int(available.width() * _SCREEN_FRACTION))
        height = min(int(scene_rect.height()), int(available.height() * _SCREEN_FRACTION))
        self.resize(max(width, _MIN_WINDOW_SIZE[0]), max(height, _MIN_WINDOW_SIZE[1]))
