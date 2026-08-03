"""Selection state machine.

Qt-free on purpose. The overlay widgets above this own painting and event forwarding and
nothing else, which keeps every interaction -- drag in any direction, arrow-key nudge,
click-without-drag, cancel -- testable headlessly.

Everything here is in absolute physical pixels, including negative coordinates. The overlay
converts from Qt's logical mouse coordinates at its own boundary, using the device pixel
ratio of the screen the event arrived on; doing that conversion per-screen is what makes a
drag spanning a mixed-DPI seam land correctly.
"""

from __future__ import annotations

from collections.abc import Sequence
from enum import Enum

from snipline.platform.geometry import (
    MonitorInfo,
    PhysicalRect,
    Point,
    monitor_at,
    rect_from_corners,
)

__all__ = ["CLICK_THRESHOLD_PX", "Edge", "SelectionModel"]

# Below this, a press-and-release is a click rather than a drag. Generous enough to absorb
# the pointer wobble of an ordinary click.
CLICK_THRESHOLD_PX = 4


class Edge(Enum):
    LEFT = "left"
    TOP = "top"
    RIGHT = "right"
    BOTTOM = "bottom"


class SelectionModel:
    """Tracks one region selection from press to commit."""

    def __init__(self, desktop: PhysicalRect, monitors: Sequence[MonitorInfo]) -> None:
        self._desktop = desktop
        self._monitors = list(monitors)
        self._anchor: Point | None = None
        self._cursor: Point | None = None
        self._dragging = False
        self._cancelled = False

    @property
    def is_dragging(self) -> bool:
        return self._dragging

    @property
    def cancelled(self) -> bool:
        return self._cancelled

    @property
    def rect(self) -> PhysicalRect | None:
        """The current selection, clamped to the desktop, or None when there is none."""
        if self._anchor is None or self._cursor is None:
            return None
        return rect_from_corners(self._anchor, self._cursor).intersection(self._desktop)

    def begin(self, x: int, y: int) -> None:
        start = Point(x, y)
        self._anchor = start
        self._cursor = start
        self._dragging = True
        self._cancelled = False

    def update(self, x: int, y: int) -> None:
        if self._anchor is None:
            return
        self._cursor = Point(x, y)

    def commit(self) -> PhysicalRect | None:
        """End the drag and return what was selected.

        A press-and-release that never really moved is a click, which the plan defines as
        "capture the monitor under the cursor" -- so it returns that monitor's bounds
        rather than a few stray pixels.
        """
        self._dragging = False
        if self._cancelled or self._anchor is None or self._cursor is None:
            return None

        if self._is_click():
            monitor = monitor_at(self._monitors, self._anchor.x, self._anchor.y)
            return monitor.bounds if monitor is not None else None

        selected = self.rect
        return None if selected is None or selected.is_empty else selected

    def cancel(self) -> None:
        self._dragging = False
        self._cancelled = True
        self._anchor = None
        self._cursor = None

    def reset(self) -> None:
        """Clear everything for the next capture."""
        self._anchor = None
        self._cursor = None
        self._dragging = False
        self._cancelled = False

    def nudge(self, edge: Edge, delta: int) -> None:
        """Move one edge by ``delta`` physical pixels.

        This is the reason the overlay exists rather than a bare drag: a mouse cannot
        reliably land on an exact pixel boundary, and a screenshot with one stray row of a
        neighbouring window looks careless.
        """
        current = self.rect
        if current is None:
            return

        left, top = current.left, current.top
        right, bottom = current.right, current.bottom

        if edge is Edge.LEFT:
            left = min(left + delta, right)
        elif edge is Edge.RIGHT:
            right = max(right + delta, left)
        elif edge is Edge.TOP:
            top = min(top + delta, bottom)
        else:
            bottom = max(bottom + delta, top)

        nudged = PhysicalRect(left, top, right - left, bottom - top)
        clamped = nudged.intersection(self._desktop)

        # Re-express as anchor/cursor so a later drag continues from the nudged rect.
        self._anchor = Point(clamped.left, clamped.top)
        self._cursor = Point(clamped.right, clamped.bottom)

    def _is_click(self) -> bool:
        if self._anchor is None or self._cursor is None:
            return False
        return (
            abs(self._cursor.x - self._anchor.x) <= CLICK_THRESHOLD_PX
            and abs(self._cursor.y - self._anchor.y) <= CLICK_THRESHOLD_PX
        )
