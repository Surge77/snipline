"""The remaining M5 tools, and the interface claim.

The claim M5 exists to test: every tool satisfies one interface and requires zero changes to
``EditorController``. The parametrised tests below run the whole tool set through the same
controller, which is what makes that claim checkable rather than aspirational.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QGraphicsItem

from snipline.capture.fake_backend import FakeBackend
from snipline.editor.scene import AnnotationScene, EditorController
from snipline.editor.style import DEFAULT_STYLE, ToolStyle
from snipline.editor.tools.base import Tool
from snipline.editor.tools.freehand import FreehandItem, FreehandTool
from snipline.editor.tools.registry import TOOLS, build_tool, tool_names
from snipline.editor.tools.shapes import EllipseTool, RectangleTool, rect_from_drag
from snipline.editor.tools.step import StepBadgeItem, StepTool
from snipline.editor.tools.text import TextItem, TextTool
from snipline.platform.geometry import PhysicalRect

CAPTURE = PhysicalRect(0, 0, 320, 240)


def _controller(tool: Tool) -> EditorController:
    return EditorController(scene=AnnotationScene(FakeBackend().grab(CAPTURE)), tool=tool)


def _drag(controller: EditorController, x1: int, y1: int, x2: int, y2: int) -> object:
    controller.press(QPointF(x1, y1))
    controller.move(QPointF((x1 + x2) // 2, (y1 + y2) // 2))
    controller.move(QPointF(x2, y2))
    return controller.release(QPointF(x2, y2))


# -- the interface claim ---------------------------------------------------------


@pytest.mark.parametrize("name", tool_names())
def test_every_tool_satisfies_the_tool_protocol(qapp: QApplication, name: str) -> None:
    assert isinstance(build_tool(name, DEFAULT_STYLE), Tool)


@pytest.mark.parametrize("name", tool_names())
def test_every_tool_draws_through_the_same_controller(qapp: QApplication, name: str) -> None:
    # No per-tool branching exists in EditorController; if any tool needed some, this test
    # would be where that shows up.
    controller = _controller(build_tool(name, DEFAULT_STYLE))

    committed = _drag(controller, 20, 20, 160, 120)

    assert committed is not None
    assert len(controller.scene.items()) == 1


@pytest.mark.parametrize("name", tool_names())
def test_every_tool_produces_an_undoable_annotation(qapp: QApplication, name: str) -> None:
    controller = _controller(build_tool(name, DEFAULT_STYLE))
    _drag(controller, 20, 20, 160, 120)

    controller.undo_stack.undo()

    assert controller.scene.items() == []


@pytest.mark.parametrize("name", tool_names())
def test_every_tool_produces_a_selectable_item(qapp: QApplication, name: str) -> None:
    controller = _controller(build_tool(name, DEFAULT_STYLE))

    _drag(controller, 20, 20, 160, 120)

    item = controller.scene.items()[0]
    assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
    assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable


@pytest.mark.parametrize("name", tool_names())
def test_switching_between_any_two_tools_is_clean(qapp: QApplication, name: str) -> None:
    controller = _controller(build_tool("arrow", DEFAULT_STYLE))
    controller.press(QPointF(10, 10))
    controller.move(QPointF(90, 90))

    controller.set_tool(build_tool(name, DEFAULT_STYLE))

    assert controller.scene.items() == []
    assert controller.undo_stack.count() == 0


def test_the_registry_exposes_every_tool_exactly_once() -> None:
    names = tool_names()

    assert len(names) == len(set(names))
    assert len(names) == len(TOOLS)


def test_an_unknown_tool_name_is_rejected() -> None:
    with pytest.raises(KeyError, match="unknown tool"):
        build_tool("polygon", DEFAULT_STYLE)


def test_only_solid_and_pixelate_are_marked_as_redaction() -> None:
    # D7, enforced at the level the UI reads from.
    redacting = {entry.name for entry in TOOLS if entry.is_redaction}

    assert redacting == {"solid", "pixelate"}


# -- shapes ----------------------------------------------------------------------


@pytest.mark.parametrize("factory", [RectangleTool, EllipseTool])
def test_a_shape_matches_the_dragged_box(qapp: QApplication, factory: type) -> None:
    controller = _controller(factory())

    _drag(controller, 30, 40, 130, 140)

    item = controller.scene.items()[0]
    assert item.boundingRect().size().toSize().width() >= 100


@pytest.mark.parametrize("factory", [RectangleTool, EllipseTool])
def test_a_shape_dragged_up_and_left_is_normalised(qapp: QApplication, factory: type) -> None:
    controller = _controller(factory())

    _drag(controller, 200, 200, 100, 100)

    item = controller.scene.items()[0]
    assert item.boundingRect().width() > 0
    assert item.boundingRect().height() > 0


@pytest.mark.parametrize("factory", [RectangleTool, EllipseTool])
def test_a_click_without_a_drag_commits_no_shape(qapp: QApplication, factory: type) -> None:
    controller = _controller(factory())

    controller.press(QPointF(50, 50))

    assert controller.release(QPointF(50, 50)) is None


def test_rect_from_drag_normalises_every_direction() -> None:
    corners = (QPointF(10, 10), QPointF(90, 70))
    expected = rect_from_drag(*corners)

    assert rect_from_drag(corners[1], corners[0]) == expected
    assert expected.width() == 80
    assert expected.height() == 60


# -- freehand --------------------------------------------------------------------


def test_freehand_records_the_points_it_was_dragged_through(qapp: QApplication) -> None:
    tool = FreehandTool()
    item = tool.press(QPointF(0, 0))
    assert isinstance(item, FreehandItem)

    for step in range(1, 20):
        tool.move(QPointF(step * 5, step * 3))
    tool.release(QPointF(100, 60))

    assert item.point_count > 10


def test_freehand_discards_points_too_close_to_matter(qapp: QApplication) -> None:
    # Long strokes repaint on every move; redundant points cost for nothing.
    item = FreehandItem(QPointF(0, 0), DEFAULT_STYLE)

    assert not item.add_point(QPointF(0, 0))
    assert item.add_point(QPointF(20, 20))


def test_a_freehand_dot_is_not_committed(qapp: QApplication) -> None:
    tool = FreehandTool()
    tool.press(QPointF(10, 10))

    assert tool.release(QPointF(10, 10)) is None


# -- text ------------------------------------------------------------------------


def test_text_is_placed_where_it_was_clicked(qapp: QApplication) -> None:
    tool = TextTool()
    tool.press(QPointF(45, 65))
    item = tool.release(QPointF(45, 65))

    assert isinstance(item, TextItem)
    assert item.pos() == QPointF(45, 65)


def test_text_is_committed_empty_so_it_can_be_typed_into(qapp: QApplication) -> None:
    # An item that vanished on mouse-release would be impossible to use.
    tool = TextTool()
    tool.press(QPointF(10, 10))
    item = tool.release(QPointF(10, 10))

    assert isinstance(item, TextItem)
    assert item.is_empty


def test_text_accepts_editing_and_reports_content(qapp: QApplication) -> None:
    tool = TextTool()
    tool.press(QPointF(10, 10))
    item = tool.release(QPointF(10, 10))
    assert isinstance(item, TextItem)

    item.setPlainText("redacted 名前 🙂")

    assert not item.is_empty
    assert "🙂" in item.toPlainText()


def test_text_size_follows_stroke_width(qapp: QApplication) -> None:
    small = TextItem(ToolStyle(width=2))
    large = TextItem(ToolStyle(width=12))

    assert large.font().pointSize() > small.font().pointSize()


# -- step badges -----------------------------------------------------------------


def test_step_badges_number_themselves_in_order(qapp: QApplication) -> None:
    tool = StepTool()
    numbers = []

    for index in range(3):
        tool.press(QPointF(index * 30, 10))
        item = tool.release(QPointF(index * 30, 10))
        assert isinstance(item, StepBadgeItem)
        numbers.append(item.number)

    assert numbers == [1, 2, 3]


def test_an_abandoned_badge_does_not_consume_a_number(qapp: QApplication) -> None:
    # Driven through the controller so the abandoned gesture is aborted the way the editor
    # actually aborts one, rather than by reaching into the tool's state.
    tool = StepTool()
    controller = _controller(tool)

    controller.press(QPointF(10, 10))
    first = controller.release(QPointF(10, 10))

    controller.press(QPointF(50, 50))  # started, then abandoned
    controller.abort()

    controller.press(QPointF(80, 80))
    second = controller.release(QPointF(80, 80))

    assert isinstance(first, StepBadgeItem) and first.number == 1
    assert isinstance(second, StepBadgeItem) and second.number == 2


def test_step_numbering_can_be_reset(qapp: QApplication) -> None:
    tool = StepTool()
    tool.press(QPointF(10, 10))
    tool.release(QPointF(10, 10))

    tool.reset()

    assert tool.next_number == 1
