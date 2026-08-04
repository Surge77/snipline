"""The tool and style toolbar.

Built by iterating the registry, so adding a tool in ``tools/registry.py`` puts it in the UI
with no change here and none in the editor.

Redaction tools are separated from the drawing tools and the cosmetic blur is labelled as an
effect (D7). The grouping is part of the honesty of the feature: a user reaching for "hide
this" must not land on blur by accident.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QObject, QRectF, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QComboBox, QSpinBox, QToolBar, QWidget

from snipline.editor.style import MAX_WIDTH, MIN_WIDTH, ToolStyle
from snipline.editor.tools.registry import TOOLS
from snipline.ui.icons import has_glyph, tool_icon

__all__ = ["PALETTE", "StyleBar", "build_tool_actions"]

# A small fixed palette rather than a colour dialog: annotation colours only need to be
# distinguishable from the screenshot, and a modal dialog per colour change is friction on
# the most common adjustment there is.
PALETTE = (
    ("Red", "#EF4444"),
    ("Amber", "#F59E0B"),
    ("Green", "#22C55E"),
    ("Blue", "#3B82F6"),
    ("Black", "#111827"),
    ("White", "#F9FAFB"),
)

_SWATCH_SIZE = 18
_SWATCH_RADIUS = 5.0
# White and near-black swatches need an outline or they vanish into the menu behind them.
_SWATCH_EDGE = QColor(255, 255, 255, 46)


def _swatch(colour: str) -> QIcon:
    pixmap = QPixmap(_SWATCH_SIZE, _SWATCH_SIZE)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(colour))
    painter.setPen(QPen(_SWATCH_EDGE, 1.0))
    inset = 1.0
    painter.drawRoundedRect(
        QRectF(inset, inset, _SWATCH_SIZE - inset * 2, _SWATCH_SIZE - inset * 2),
        _SWATCH_RADIUS,
        _SWATCH_RADIUS,
    )
    painter.end()
    return QIcon(pixmap)


def build_tool_actions(
    parent: QWidget, on_selected: Callable[[str], None]
) -> tuple[QActionGroup, list[QAction]]:
    """One checkable action per registered tool, mutually exclusive."""
    group = QActionGroup(parent)
    group.setExclusive(True)

    actions: list[QAction] = []
    for entry in TOOLS:
        action = QAction(entry.label, parent)
        # A tool without a glyph still gets its label, so a new registry entry appears in
        # the toolbar with or without artwork. The missing glyph is caught in tests rather
        # than by leaving a blank button in the shipped build.
        if has_glyph(entry.name):
            action.setIcon(tool_icon(entry.name))
        action.setCheckable(True)
        action.setData(entry.name)
        action.setToolTip(entry.label)
        action.triggered.connect(lambda _checked=False, name=entry.name: on_selected(name))
        group.addAction(action)
        actions.append(action)

    if actions:
        actions[0].setChecked(True)
    return group, actions


def split_at_redaction(actions: list[QAction]) -> tuple[list[QAction], list[QAction]]:
    """Divide the tools into the drawing run and the redaction run.

    Split by position rather than by the ``is_redaction`` flag, because the cosmetic blur
    carries ``is_redaction=False`` on purpose (D7) while still needing to sit beside the
    tools it must not be mistaken for. The registry orders the trailing group deliberately;
    this respects that order rather than re-deriving it from a flag that means something
    else.

    Returns everything in the first list when no redaction tool is registered.
    """
    first = next((index for index, entry in enumerate(TOOLS) if entry.is_redaction), None)
    if first is None:
        return list(actions), []
    return list(actions[:first]), list(actions[first:])


class StyleBar(QObject):
    """Colour and stroke width controls."""

    style_changed = Signal(object)  # ToolStyle

    def __init__(self, style: ToolStyle, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._style = style

        self._colours = QComboBox()
        for name, value in PALETTE:
            self._colours.addItem(_swatch(value), name, value)
        self._colours.setCurrentIndex(
            next((i for i, (_, v) in enumerate(PALETTE) if v == style.colour), 0)
        )
        self._colours.currentIndexChanged.connect(self._on_colour)

        self._width = QSpinBox()
        self._width.setRange(MIN_WIDTH, MAX_WIDTH)
        self._width.setValue(style.width)
        self._width.setToolTip("Stroke width")
        self._width.valueChanged.connect(self._on_width)

    @property
    def style(self) -> ToolStyle:
        return self._style

    def select_colour(self, index: int) -> None:
        """Choose a palette entry by position. Public so the choice is scriptable."""
        self._colours.setCurrentIndex(index)

    def set_width(self, width: int) -> None:
        """Set stroke width, clamped by the widget to the supported range."""
        self._width.setValue(width)

    def add_to(self, toolbar: QToolBar) -> None:
        toolbar.addWidget(self._colours)
        toolbar.addWidget(self._width)

    def _on_colour(self, index: int) -> None:
        value = self._colours.itemData(index)
        if isinstance(value, str):
            self._style = self._style.with_colour(value)
            self.style_changed.emit(self._style)

    def _on_width(self, width: int) -> None:
        self._style = self._style.with_width(width)
        self.style_changed.emit(self._style)
