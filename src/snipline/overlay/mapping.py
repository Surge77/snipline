"""The logical/physical boundary for overlay windows.

Qt delivers mouse events in logical widget coordinates. The selection model and the capture
backend speak absolute physical pixels. This module is the only place the two meet, and it
converts against *one monitor's* scale factor at a time -- on a mixed-DPI desktop there is
no single factor for the whole virtual desktop, and applying one is how a drag across a
seam ends up offset.

Order matters: scale first, then offset. The offset is already in physical pixels, so
scaling it again moves the point by a fraction of the monitor's origin -- an error that is
invisible on the primary monitor, where the origin is (0, 0), and only appears on the
secondary.
"""

from __future__ import annotations

from snipline.platform.geometry import MonitorInfo, PhysicalRect

__all__ = ["frame_slice_for", "local_to_physical", "physical_to_local"]


def local_to_physical(monitor: MonitorInfo, x: int, y: int) -> tuple[int, int]:
    """Widget-local logical coordinates to absolute physical desktop coordinates."""
    return (
        monitor.bounds.left + round(x * monitor.scale),
        monitor.bounds.top + round(y * monitor.scale),
    )


def physical_to_local(monitor: MonitorInfo, x: int, y: int) -> tuple[int, int]:
    """Absolute physical desktop coordinates to widget-local logical coordinates."""
    return (
        round((x - monitor.bounds.left) / monitor.scale),
        round((y - monitor.bounds.top) / monitor.scale),
    )


def frame_slice_for(monitor: MonitorInfo, desktop: PhysicalRect) -> PhysicalRect:
    """This monitor's region within a frozen full-desktop frame.

    The frame's buffer starts at the desktop origin, which is negative whenever a monitor
    sits left of or above the primary, so absolute coordinates must be rebased before they
    can index into it.
    """
    return monitor.bounds.normalised_within(desktop)
