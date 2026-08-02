"""Coordinate primitives.

Two coordinate spaces exist in this application and mixing them is the root cause of
essentially every multi-monitor screenshot bug:

- **Logical**: Qt points. DPI-scaled. What widget geometry and mouse events speak.
- **Physical**: device pixels. What the framebuffer, the capture backend, and the exported
  image speak.

They are separate types so that a function taking a ``PhysicalRect`` cannot silently be
handed logical coordinates. Conversion happens only through the explicit methods below, and
always against a specific monitor's scale factor -- on a mixed-DPI desktop there is no single
factor for the whole virtual desktop.

Pure data. No OS calls, no Qt imports, fully unit tested.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Point:
    x: int
    y: int


@dataclass(frozen=True, slots=True)
class Size:
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError(f"negative size: {self.width}x{self.height}")


@dataclass(frozen=True, slots=True)
class _Rect:
    """Shared rectangle behaviour. Left/top may be negative: on Windows a monitor placed
    above or to the left of the primary has negative virtual-desktop coordinates."""

    left: int
    top: int
    width: int
    height: int

    def __post_init__(self) -> None:
        if self.width < 0 or self.height < 0:
            raise ValueError(f"negative extent: {self.width}x{self.height}")

    @property
    def right(self) -> int:
        return self.left + self.width

    @property
    def bottom(self) -> int:
        return self.top + self.height

    @property
    def size(self) -> Size:
        return Size(self.width, self.height)

    @property
    def is_empty(self) -> bool:
        return self.width == 0 or self.height == 0

    def contains(self, x: int, y: int) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    def intersects(self, other: _Rect) -> bool:
        return not (
            other.left >= self.right
            or other.right <= self.left
            or other.top >= self.bottom
            or other.bottom <= self.top
        )


@dataclass(frozen=True, slots=True)
class LogicalRect(_Rect):
    """Rectangle in Qt points. Never pass one of these to the capture backend."""

    def to_physical(self, scale: float) -> PhysicalRect:
        return PhysicalRect(
            left=round(self.left * scale),
            top=round(self.top * scale),
            width=round(self.width * scale),
            height=round(self.height * scale),
        )


@dataclass(frozen=True, slots=True)
class PhysicalRect(_Rect):
    """Rectangle in device pixels. This is what gets captured, cropped, and exported."""

    def to_logical(self, scale: float) -> LogicalRect:
        return LogicalRect(
            left=round(self.left / scale),
            top=round(self.top / scale),
            width=round(self.width / scale),
            height=round(self.height / scale),
        )

    def intersection(self, other: PhysicalRect) -> PhysicalRect:
        left = max(self.left, other.left)
        top = max(self.top, other.top)
        right = min(self.right, other.right)
        bottom = min(self.bottom, other.bottom)
        if right <= left or bottom <= top:
            return PhysicalRect(left, top, 0, 0)
        return PhysicalRect(left, top, right - left, bottom - top)

    def translated(self, dx: int, dy: int) -> PhysicalRect:
        return PhysicalRect(self.left + dx, self.top + dy, self.width, self.height)

    def normalised_within(self, container: PhysicalRect) -> PhysicalRect:
        """Re-express this rect relative to ``container``'s origin.

        Used when cropping a captured frame: the frame's buffer starts at the virtual
        desktop origin, which is frequently not (0, 0), so a selection's absolute
        coordinates must be rebased before indexing into the buffer.
        """
        return self.translated(-container.left, -container.top)


def rect_from_corners(a: Point, b: Point) -> PhysicalRect:
    """Build a rect from two drag corners in any order.

    A user dragging right-to-left or bottom-to-top is normal and must not produce a
    negative extent.
    """
    left, right = sorted((a.x, b.x))
    top, bottom = sorted((a.y, b.y))
    return PhysicalRect(left, top, right - left, bottom - top)


def union(rects: Iterable[PhysicalRect]) -> PhysicalRect:
    """Bounding box of all rects. Used to derive the virtual desktop from monitor bounds.

    Empty rects are ignored rather than dragging the bounds to the origin.
    """
    considered = [r for r in rects if not r.is_empty]
    if not considered:
        return PhysicalRect(0, 0, 0, 0)
    left = min(r.left for r in considered)
    top = min(r.top for r in considered)
    right = max(r.right for r in considered)
    bottom = max(r.bottom for r in considered)
    return PhysicalRect(left, top, right - left, bottom - top)


@dataclass(frozen=True, slots=True)
class MonitorInfo:
    """One display, as reported by the OS.

    ``bounds`` is in physical pixels within the virtual desktop and may have a negative
    origin. ``scale`` is the monitor's own DPI scale factor -- 1.5 for a 150% display --
    and differs per monitor on a mixed-DPI desktop.
    """

    index: int
    bounds: PhysicalRect
    work_area: PhysicalRect
    scale: float
    is_primary: bool

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError(f"non-positive scale factor: {self.scale}")


def monitor_at(monitors: Iterable[MonitorInfo], x: int, y: int) -> MonitorInfo | None:
    """Which monitor owns a physical point. Returns None for points in the dead space
    that L-shaped monitor arrangements leave inside the virtual desktop bounds."""
    for monitor in monitors:
        if monitor.bounds.contains(x, y):
            return monitor
    return None


def virtual_desktop(monitors: Iterable[MonitorInfo]) -> PhysicalRect:
    return union(m.bounds for m in monitors)
