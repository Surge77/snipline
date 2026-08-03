"""Editor scene, controller, and undo behaviour.

The success criterion this file exists to defend: "undo/redo covers every annotation
operation with no image-snapshot memory growth" (PLAN.md §2.3).
"""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from snipline.capture.fake_backend import FakeBackend, pixel_value
from snipline.editor.commands import AddItemCommand
from snipline.editor.scene import AnnotationScene, EditorController
from snipline.editor.style import ToolStyle
from snipline.editor.tools.arrow import ArrowItem, ArrowTool
from snipline.platform.geometry import PhysicalRect

CAPTURE = PhysicalRect(0, 0, 320, 240)


def _scene() -> AnnotationScene:
    return AnnotationScene(FakeBackend().grab(CAPTURE))


def _controller() -> EditorController:
    return EditorController(scene=_scene(), tool=ArrowTool())


def _draw(controller: EditorController, x1: int, y1: int, x2: int, y2: int) -> None:
    controller.press(QPointF(x1, y1))
    controller.move(QPointF(x2, y2))
    controller.release(QPointF(x2, y2))


def test_scene_coordinates_are_the_captures_physical_pixels(qapp: QApplication) -> None:
    # Anything else puts a scale factor between what the user draws and what is exported.
    scene = _scene()

    assert scene.sceneRect().width() == CAPTURE.width
    assert scene.sceneRect().height() == CAPTURE.height


def test_the_capture_is_the_background_not_a_selectable_item(qapp: QApplication) -> None:
    # A background item could be dragged away by a stray click.
    scene = _scene()

    assert scene.items() == []
    assert not scene.background.isNull()


def test_a_drag_adds_one_annotation(qapp: QApplication) -> None:
    controller = _controller()

    _draw(controller, 10, 10, 100, 100)

    assert len(controller.scene.items()) == 1
    assert isinstance(controller.scene.items()[0], ArrowItem)


def test_the_annotation_is_visible_during_the_drag(qapp: QApplication) -> None:
    controller = _controller()

    controller.press(QPointF(10, 10))
    controller.move(QPointF(80, 80))

    assert len(controller.scene.items()) == 1
    assert controller.is_drawing


def test_a_rejected_gesture_leaves_nothing_in_the_scene(qapp: QApplication) -> None:
    # The draft was already added to the scene but never reached the undo stack, so nothing
    # else would ever remove it.
    controller = _controller()

    controller.press(QPointF(10, 10))
    controller.release(QPointF(10, 10))

    assert controller.scene.items() == []
    assert controller.undo_stack.count() == 0


def test_undo_removes_the_annotation(qapp: QApplication) -> None:
    controller = _controller()
    _draw(controller, 10, 10, 100, 100)

    controller.undo_stack.undo()

    assert controller.scene.items() == []


def test_redo_restores_the_same_item(qapp: QApplication) -> None:
    controller = _controller()
    _draw(controller, 10, 10, 100, 100)
    original = controller.scene.items()[0]

    controller.undo_stack.undo()
    controller.undo_stack.redo()

    assert controller.scene.items()[0] is original


def test_undo_redo_survives_many_mixed_operations(qapp: QApplication) -> None:
    controller = _controller()
    for offset in range(5):
        _draw(controller, offset * 10, 0, offset * 10 + 50, 50)

    for _ in range(3):
        controller.undo_stack.undo()
    controller.undo_stack.redo()

    assert len(controller.scene.items()) == 3
    assert controller.undo_stack.count() == 5


def test_undo_stores_commands_not_image_snapshots(qapp: QApplication) -> None:
    # The whole point of D6. If undo ever snapshots the pixmap, memory grows with edit
    # count and this assertion is where that shows up.
    controller = _controller()
    for offset in range(10):
        _draw(controller, offset, 0, offset + 40, 40)

    commands = [controller.undo_stack.command(i) for i in range(controller.undo_stack.count())]

    assert all(isinstance(command, AddItemCommand) for command in commands)


def test_an_undone_item_is_still_owned_and_not_destroyed(qapp: QApplication) -> None:
    controller = _controller()
    _draw(controller, 10, 10, 100, 100)
    item = controller.scene.items()[0]

    controller.undo_stack.undo()

    assert item.scene() is None
    assert isinstance(item, ArrowItem)  # still alive, still an arrow
    assert item.length > 0


def test_delete_is_undoable(qapp: QApplication) -> None:
    controller = _controller()
    _draw(controller, 10, 10, 100, 100)
    item = controller.scene.items()[0]

    controller.delete(item)
    assert controller.scene.items() == []

    controller.undo_stack.undo()
    assert controller.scene.items() == [item]


def test_switching_tools_discards_a_half_drawn_annotation(qapp: QApplication) -> None:
    controller = _controller()
    controller.press(QPointF(10, 10))
    controller.move(QPointF(90, 90))

    controller.set_tool(ArrowTool(ToolStyle(colour="#00FF00")))

    assert controller.scene.items() == []
    assert not controller.is_drawing


def test_abort_discards_without_recording(qapp: QApplication) -> None:
    controller = _controller()
    controller.press(QPointF(10, 10))
    controller.move(QPointF(90, 90))

    controller.abort()

    assert controller.scene.items() == []
    assert controller.undo_stack.count() == 0


def test_move_without_press_is_ignored(qapp: QApplication) -> None:
    controller = _controller()

    controller.move(QPointF(50, 50))

    assert controller.scene.items() == []


def test_release_without_press_is_ignored(qapp: QApplication) -> None:
    controller = _controller()

    assert controller.release(QPointF(50, 50)) is None
    assert controller.undo_stack.count() == 0


def test_flatten_matches_the_capture_dimensions(qapp: QApplication) -> None:
    # The M6 trap, asserted early: rendering at view resolution would silently downscale a
    # high-DPI export.
    controller = _controller()
    _draw(controller, 10, 10, 100, 100)

    flattened = controller.scene.flatten()

    assert (flattened.width(), flattened.height()) == (CAPTURE.width, CAPTURE.height)


def test_flatten_preserves_unannotated_capture_pixels(qapp: QApplication) -> None:
    scene = _scene()

    flattened = scene.flatten()

    blue, green, red, _ = pixel_value(0, 0)
    corner = flattened.pixelColor(0, 0)
    assert (corner.red(), corner.green(), corner.blue()) == (red, green, blue)


def test_flatten_draws_annotations_over_the_capture(qapp: QApplication) -> None:
    controller = _controller()
    style_colour = controller.tool.style.colour

    _draw(controller, 0, 120, 320, 120)
    flattened = controller.scene.flatten()

    row = [flattened.pixelColor(x, 120).name().upper() for x in range(0, 320, 8)]
    assert style_colour.upper() in row


def test_flatten_is_deterministic(qapp: QApplication) -> None:
    controller = _controller()
    _draw(controller, 10, 10, 200, 150)

    first = controller.scene.flatten()
    second = controller.scene.flatten()

    assert first == second
