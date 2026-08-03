"""Tool selection and style controls."""

from __future__ import annotations

from PySide6.QtCore import QPointF
from PySide6.QtWidgets import QApplication, QToolBar

from snipline.capture.fake_backend import FakeBackend
from snipline.editor.style import DEFAULT_STYLE, ToolStyle
from snipline.editor.toolbar import PALETTE, StyleBar, build_tool_actions
from snipline.editor.tools.redaction import SolidFillItem
from snipline.editor.tools.registry import TOOLS
from snipline.editor.window import EditorWindow
from snipline.platform.geometry import PhysicalRect

CAPTURE = PhysicalRect(0, 0, 320, 240)


def _window() -> EditorWindow:
    return EditorWindow(FakeBackend().grab(CAPTURE))


def test_every_registered_tool_appears_in_the_toolbar(qapp: QApplication) -> None:
    # The registry drives the UI, so a new tool needs no toolbar edit.
    window = _window()
    labels = {
        action.text()
        for bar in window.findChildren(QToolBar)
        for action in bar.actions()
    }

    for entry in TOOLS:
        assert entry.label in labels


def test_tool_actions_are_mutually_exclusive(qapp: QApplication) -> None:
    window = _window()
    group, actions = build_tool_actions(window, lambda _name: None)

    actions[2].setChecked(True)

    assert group.isExclusive()
    assert sum(action.isChecked() for action in actions) == 1


def test_selecting_a_tool_switches_what_gets_drawn(qapp: QApplication) -> None:
    window = _window()

    window.select_tool("solid")
    controller = window.controller
    controller.press(QPointF(10, 10))
    controller.move(QPointF(120, 90))
    controller.release(QPointF(120, 90))

    assert isinstance(controller.scene.items()[0], SolidFillItem)


def test_changing_style_affects_the_next_annotation_only(qapp: QApplication) -> None:
    # Retroactively restyling finished work would be surprising and is not undoable through
    # the same command stack.
    window = _window()
    controller = window.controller
    controller.press(QPointF(10, 10))
    controller.move(QPointF(100, 100))
    controller.release(QPointF(100, 100))
    first = controller.scene.items()[0]

    window.set_style(ToolStyle(colour="#22C55E", width=10))
    controller.press(QPointF(120, 10))
    controller.move(QPointF(200, 100))
    controller.release(QPointF(200, 100))

    assert first.pen().color().name().upper() == DEFAULT_STYLE.colour.upper()  # type: ignore[attr-defined]
    assert controller.tool.style.width == 10


def test_the_style_bar_reports_colour_changes(qapp: QApplication) -> None:
    bar = StyleBar(DEFAULT_STYLE)
    received: list[ToolStyle] = []
    bar.style_changed.connect(received.append)

    bar.select_colour(3)

    assert received
    assert received[-1].colour == PALETTE[3][1]


def test_the_style_bar_reports_width_changes(qapp: QApplication) -> None:
    bar = StyleBar(DEFAULT_STYLE)
    received: list[ToolStyle] = []
    bar.style_changed.connect(received.append)

    bar.set_width(11)

    assert received[-1].width == 11


def test_width_is_bounded_to_the_supported_range(qapp: QApplication) -> None:
    # ToolStyle rejects out-of-range widths, so the widget must not offer them.
    bar = StyleBar(DEFAULT_STYLE)

    bar.set_width(10_000)

    assert bar.style.width <= 64
