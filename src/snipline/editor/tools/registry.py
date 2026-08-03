"""The list of available tools.

Exists so the editor window can build its toolbar by iterating rather than by naming each
tool. Adding a tool means adding an entry here and nothing else -- in particular, no change
to ``EditorController``, which is the property M5 was meant to prove.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from snipline.editor.style import ToolStyle
from snipline.editor.tools.arrow import ArrowTool
from snipline.editor.tools.base import Tool
from snipline.editor.tools.freehand import FreehandTool
from snipline.editor.tools.redaction import BlurTool, PixelateTool, SolidFillTool
from snipline.editor.tools.shapes import EllipseTool, RectangleTool
from snipline.editor.tools.step import StepTool
from snipline.editor.tools.text import TextTool

__all__ = ["TOOLS", "ToolEntry", "build_tool", "tool_names"]


@dataclass(frozen=True, slots=True)
class ToolEntry:
    name: str
    label: str
    factory: Callable[[ToolStyle], Tool]
    is_redaction: bool = False


# Order is the toolbar order: drawing tools first, redaction last and grouped, so the
# cosmetic blur sits next to the tools it must not be confused with.
TOOLS: Sequence[ToolEntry] = (
    ToolEntry("arrow", "Arrow", ArrowTool),
    ToolEntry("rectangle", "Rectangle", RectangleTool),
    ToolEntry("ellipse", "Ellipse", EllipseTool),
    ToolEntry("freehand", "Freehand", FreehandTool),
    ToolEntry("text", "Text", TextTool),
    ToolEntry("step", "Step badge", StepTool),
    ToolEntry("solid", "Redact (solid)", SolidFillTool, is_redaction=True),
    ToolEntry("pixelate", "Redact (pixelate)", PixelateTool, is_redaction=True),
    # Labelled as an effect, and is_redaction stays False. See D7: blurred text is
    # frequently recoverable, so presenting this as privacy would be a lie.
    ToolEntry("blur", "Blur (cosmetic)", BlurTool),
)


def tool_names() -> list[str]:
    return [entry.name for entry in TOOLS]


def build_tool(name: str, style: ToolStyle) -> Tool:
    for entry in TOOLS:
        if entry.name == name:
            return entry.factory(style)
    raise KeyError(f"unknown tool: {name!r}")
