"""Annotation styling.

Shared by every tool so that adding a tool never means adding a parallel notion of colour
and stroke width. Plain data, no Qt types, so tool state machines stay testable without a
QApplication.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["DEFAULT_STYLE", "ToolStyle"]

# A saturated red reads against both light and dark screenshots, which is most of what gets
# annotated.
DEFAULT_COLOUR = "#EF4444"
DEFAULT_WIDTH = 4

MIN_WIDTH = 1
MAX_WIDTH = 64


@dataclass(frozen=True, slots=True)
class ToolStyle:
    colour: str = DEFAULT_COLOUR
    width: int = DEFAULT_WIDTH

    def __post_init__(self) -> None:
        if not MIN_WIDTH <= self.width <= MAX_WIDTH:
            raise ValueError(f"stroke width out of range: {self.width}")
        if not self.colour.startswith("#"):
            raise ValueError(f"colour must be a hex string: {self.colour!r}")

    def with_width(self, width: int) -> ToolStyle:
        return ToolStyle(colour=self.colour, width=width)

    def with_colour(self, colour: str) -> ToolStyle:
        return ToolStyle(colour=colour, width=self.width)


DEFAULT_STYLE = ToolStyle()
