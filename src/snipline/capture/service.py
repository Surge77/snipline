"""Capture orchestration.

Everything above this layer -- the CLI, the hotkey handler, the overlay -- asks for
*meaningful* regions ("the desktop", "monitor 2", "this selection") rather than raw rects.
Keeping that translation here means the monitor lookup and the desktop-clamping rule exist
once, in a headless-testable place, instead of being re-derived at each call site.

The backend and the monitor source are both injected, so the whole service runs in CI
against ``FakeBackend`` and synthetic layouts with no real screen access.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence

from snipline.capture.backend import CaptureBackend
from snipline.capture.frame import Frame
from snipline.platform.geometry import MonitorInfo, PhysicalRect, monitor_at
from snipline.platform.monitors import enumerate_monitors, virtual_desktop_of

MonitorsProvider = Callable[[], Sequence[MonitorInfo]]


class CaptureService:
    """Turns intent into a physical-pixel grab."""

    def __init__(
        self,
        backend: CaptureBackend,
        monitors_provider: MonitorsProvider = enumerate_monitors,
    ) -> None:
        self._backend = backend
        self._monitors_provider = monitors_provider

    def monitors(self) -> Sequence[MonitorInfo]:
        """Re-read the monitor layout. Never cached: hot-plug and scaling changes both
        rearrange the desktop mid-session, and a stale layout crops the wrong screen."""
        return self._monitors_provider()

    def desktop_rect(self) -> PhysicalRect:
        return virtual_desktop_of(self.monitors())

    def grab_desktop(self) -> Frame:
        return self._backend.grab(self.desktop_rect())

    def grab_desktop_with_monitors(self) -> tuple[Frame, Sequence[MonitorInfo]]:
        """The frozen desktop and the layout it was derived from, in one enumeration.

        The overlay needs both. Asking separately walks ``EnumDisplayMonitors`` twice per
        capture, once per display each time, on the span the benchmark measures -- and the
        second walk can disagree with the first if a display changes in between, which would
        slice the frozen frame against a layout it was not captured from.
        """
        monitors = self.monitors()
        return self._backend.grab(virtual_desktop_of(monitors)), monitors

    def grab_monitor(self, index: int) -> Frame:
        monitors = self.monitors()
        for monitor in monitors:
            if monitor.index == index:
                return self._backend.grab(monitor.bounds)
        raise IndexError(f"no monitor with index {index}; {len(monitors)} connected")

    def grab_region(self, region: PhysicalRect) -> Frame:
        """Capture an absolute virtual-desktop rect, clamped to the desktop.

        Clamping rather than rejecting is deliberate: a drag that runs off the edge of the
        desktop is normal user behaviour and should yield the visible part.
        """
        if region.is_empty:
            raise ValueError(f"cannot capture an empty region: {region}")

        clamped = region.intersection(self.desktop_rect())
        if clamped.is_empty:
            raise ValueError(f"region {region} lies outside the virtual desktop")
        return self._backend.grab(clamped)

    def monitor_under_point(self, x: int, y: int) -> MonitorInfo | None:
        """Which monitor owns a physical point, or None for the dead space that L-shaped
        arrangements leave inside the virtual desktop bounds."""
        return monitor_at(self.monitors(), x, y)

    def close(self) -> None:
        self._backend.close()
