"""Editor window and view.

The view's job is to convert mouse events into scene coordinates and hand them to the
controller. That conversion is worth testing because a view transform silently offsetting
every annotation is the sort of bug that looks like a drawing bug.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QToolBar

from snipline.capture.fake_backend import FakeBackend
from snipline.editor.tools.arrow import ArrowItem
from snipline.editor.window import EditorWindow
from snipline.platform.geometry import PhysicalRect

CAPTURE = PhysicalRect(0, 0, 400, 300)


def _window() -> EditorWindow:
    return EditorWindow(FakeBackend().grab(CAPTURE))


def _click(window: EditorWindow, kind: QMouseEvent.Type, x: int, y: int) -> QMouseEvent:
    return QMouseEvent(
        kind,
        QPointF(x, y),
        window.view.mapToGlobal(QPoint(x, y)).toPointF(),
        Qt.MouseButton.LeftButton,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )


def test_the_title_states_the_physical_size(qapp: QApplication) -> None:
    # A multiplication sign, not the letter x, matching the overlay's size readout.
    assert "400 × 300" in _window().windowTitle()


def test_the_scene_is_sized_to_the_capture(qapp: QApplication) -> None:
    window = _window()

    rect = window.controller.scene.sceneRect()

    assert (rect.width(), rect.height()) == (CAPTURE.width, CAPTURE.height)


def test_dragging_in_the_view_draws_an_annotation(qapp: QApplication) -> None:
    window = _window()
    view = window.view

    view.mousePressEvent(_click(window, QMouseEvent.Type.MouseButtonPress, 20, 20))
    view.mouseMoveEvent(_click(window, QMouseEvent.Type.MouseMove, 120, 90))
    view.mouseReleaseEvent(_click(window, QMouseEvent.Type.MouseButtonRelease, 120, 90))

    items = window.controller.scene.items()
    assert len(items) == 1
    assert isinstance(items[0], ArrowItem)


def test_the_annotation_lands_where_the_mouse_was(qapp: QApplication) -> None:
    # Asserted against mapToScene rather than against the raw view coordinates: the view
    # centres a scene smaller than the viewport, so the two legitimately differ. Using the
    # event position directly -- the bug this guards against -- would offset every
    # annotation by exactly that centring margin.
    window = _window()
    view = window.view

    view.mousePressEvent(_click(window, QMouseEvent.Type.MouseButtonPress, 30, 40))
    view.mouseReleaseEvent(_click(window, QMouseEvent.Type.MouseButtonRelease, 200, 150))

    arrow = window.controller.scene.items()[0]
    assert isinstance(arrow, ArrowItem)
    assert arrow.start == view.mapToScene(QPoint(30, 40))
    assert arrow.end == view.mapToScene(QPoint(200, 150))


def test_a_scrolled_view_still_maps_clicks_onto_the_right_pixels(qapp: QApplication) -> None:
    # A capture larger than the window is the normal case, and scrolling is where a
    # forgotten mapToScene stops being a constant offset and starts tracking the
    # scrollbars.
    window = EditorWindow(FakeBackend().grab(PhysicalRect(0, 0, 4000, 3000)))
    window.resize(400, 300)
    view = window.view
    view.horizontalScrollBar().setValue(view.horizontalScrollBar().maximum())
    view.verticalScrollBar().setValue(view.verticalScrollBar().maximum())

    view.mousePressEvent(_click(window, QMouseEvent.Type.MouseButtonPress, 10, 10))
    view.mouseReleaseEvent(_click(window, QMouseEvent.Type.MouseButtonRelease, 120, 120))

    arrow = window.controller.scene.items()[0]
    assert isinstance(arrow, ArrowItem)
    assert arrow.start == view.mapToScene(QPoint(10, 10))
    assert arrow.start.x() > 0  # scrolled away from the origin, not clamped to it


def test_a_right_click_does_not_start_an_annotation(qapp: QApplication) -> None:
    window = _window()
    event = QMouseEvent(
        QMouseEvent.Type.MouseButtonPress,
        QPointF(10, 10),
        QPointF(10, 10),
        Qt.MouseButton.RightButton,
        Qt.MouseButton.RightButton,
        Qt.KeyboardModifier.NoModifier,
    )

    window.view.mousePressEvent(event)

    assert not window.controller.is_drawing


def test_undo_and_redo_actions_exist_with_standard_shortcuts(qapp: QApplication) -> None:
    window = _window()

    toolbar = window.findChild(QToolBar)
    assert toolbar is not None
    shortcuts = {
        text for action in toolbar.actions() for text in action.shortcut().toString().split(", ")
    }

    assert "Ctrl+Z" in shortcuts
    assert shortcuts & {"Ctrl+Y", "Ctrl+Shift+Z"}


def test_fit_to_screen_never_exceeds_the_available_area(qapp: QApplication) -> None:
    # A full-screen capture must not open a window taller than the screen showing it.
    window = EditorWindow(FakeBackend().grab(PhysicalRect(0, 0, 6000, 4000)))

    window.fit_to_screen()

    screen = window.screen()
    assert screen is not None
    assert window.width() <= screen.availableGeometry().width()
    assert window.height() <= screen.availableGeometry().height()


def test_copy_and_export_are_signals_not_direct_calls(qapp: QApplication) -> None:
    # The window does not know where a capture goes; the app decides. Keeps the editor
    # free of clipboard and filesystem concerns.
    window = _window()
    received: list[str] = []
    window.copy_requested.connect(lambda: received.append("copy"))
    window.export_requested.connect(lambda: received.append("export"))

    window.copy_requested.emit()
    window.export_requested.emit()

    assert received == ["copy", "export"]


def test_the_select_tool_hands_mouse_events_to_the_scene(qapp: QApplication) -> None:
    # Every annotation is created selectable and movable. Without this branch the view
    # consumes all three mouse events and those flags are unreachable: a placed item can
    # never be picked up, and a text item's caret can never be positioned.
    window = EditorWindow(FakeBackend().grab(CAPTURE))

    window.select_tool("select")

    assert window.view.is_selecting

    window.select_tool("arrow")

    assert not window.view.is_selecting


def test_deleting_a_selected_annotation_is_undoable(qapp: QApplication) -> None:
    window = EditorWindow(FakeBackend().grab(CAPTURE))
    controller = window.controller
    controller.press(QPointF(20, 20))
    controller.move(QPointF(140, 100))
    item = controller.release(QPointF(140, 100))
    assert item is not None
    item.setSelected(True)

    window.delete_selected()
    assert controller.scene.items() == []

    controller.undo_stack.undo()
    assert controller.scene.items() == [item]
