"""Arrow tool and its geometry."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication

from snipline.editor.style import ToolStyle
from snipline.editor.tools.arrow import (
    MIN_ARROW_LENGTH_PX,
    ArrowItem,
    ArrowTool,
    arrow_path,
)


def test_a_drag_produces_an_arrow_from_press_to_release(qapp: QApplication) -> None:
    tool = ArrowTool()

    tool.press(QPointF(10, 10))
    tool.move(QPointF(50, 60))
    committed = tool.release(QPointF(100, 120))

    assert isinstance(committed, ArrowItem)
    assert committed.start == QPointF(10, 10)
    assert committed.end == QPointF(100, 120)


def test_the_draft_follows_the_cursor_during_the_drag(qapp: QApplication) -> None:
    tool = ArrowTool()
    draft = tool.press(QPointF(0, 0))
    assert isinstance(draft, ArrowItem)

    tool.move(QPointF(30, 40))

    assert draft.end == QPointF(30, 40)
    assert draft.length == 50  # 3-4-5


def test_a_click_without_a_drag_commits_nothing(qapp: QApplication) -> None:
    # Otherwise the scene collects invisible zero-length arrows that cannot be selected or
    # deleted.
    tool = ArrowTool()
    tool.press(QPointF(10, 10))

    assert tool.release(QPointF(10, 10)) is None


def test_a_drag_shorter_than_the_minimum_commits_nothing(qapp: QApplication) -> None:
    tool = ArrowTool()
    tool.press(QPointF(0, 0))

    assert tool.release(QPointF(MIN_ARROW_LENGTH_PX - 1, 0)) is None


def test_releasing_without_pressing_is_harmless(qapp: QApplication) -> None:
    assert ArrowTool().release(QPointF(5, 5)) is None


def test_a_second_arrow_is_independent_of_the_first(qapp: QApplication) -> None:
    tool = ArrowTool()
    tool.press(QPointF(0, 0))
    first = tool.release(QPointF(100, 0))

    tool.press(QPointF(200, 200))
    second = tool.release(QPointF(300, 200))

    assert first is not second


def test_the_item_carries_the_tools_style(qapp: QApplication) -> None:
    style = ToolStyle(colour="#00FF00", width=9)
    tool = ArrowTool(style)

    tool.press(QPointF(0, 0))
    committed = tool.release(QPointF(80, 0))

    assert isinstance(committed, ArrowItem)
    assert committed.pen().width() == 9
    assert committed.pen().color().name().upper() == "#00FF00"


def test_arrows_are_selectable_and_movable(qapp: QApplication) -> None:
    # D6: annotations stay editable after being drawn rather than being baked into pixels.
    from PySide6.QtWidgets import QGraphicsItem

    item = ArrowItem(QPointF(0, 0), ToolStyle())

    assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsSelectable
    assert item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable


def test_the_path_contains_a_shaft_and_two_barbs(qapp: QApplication) -> None:
    path = arrow_path(QPointF(0, 0), QPointF(100, 0), width=4)

    # One shaft line plus two barbs, each starting with its own moveTo.
    assert path.elementCount() > 2


def test_a_degenerate_path_is_just_the_shaft(qapp: QApplication) -> None:
    short = arrow_path(QPointF(0, 0), QPointF(1, 0), width=4)
    full = arrow_path(QPointF(0, 0), QPointF(100, 0), width=4)

    assert short.elementCount() < full.elementCount()


def test_the_head_scales_with_stroke_width(qapp: QApplication) -> None:
    # A fixed head size looks wrong at both ends of the width range.
    thin = arrow_path(QPointF(0, 0), QPointF(100, 0), width=2)
    thick = arrow_path(QPointF(0, 0), QPointF(100, 0), width=16)

    assert thick.boundingRect().height() > thin.boundingRect().height()


def test_the_arrow_points_the_way_it_was_dragged(qapp: QApplication) -> None:
    path = arrow_path(QPointF(100, 100), QPointF(0, 100), width=4)

    # Dragging left means the barbs trail to the right of the tip.
    assert path.boundingRect().right() > 0
    assert math.isclose(path.elementAt(0).x, 100)
