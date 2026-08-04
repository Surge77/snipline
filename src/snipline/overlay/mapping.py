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

from PySide6.QtGui import QGuiApplication, QScreen

from snipline.platform.geometry import MonitorInfo, PhysicalRect

__all__ = ["frame_slice_for", "local_to_physical", "physical_to_local", "screen_for"]

# Slack allowed when matching a Qt screen to a Win32 monitor by origin. Wide enough to
# absorb the rounding in Qt's logical-to-physical reconstruction, far narrower than the
# hundreds of pixels separating any two real monitors.
_ORIGIN_TOLERANCE_PX = 4


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


def screen_for(monitor: MonitorInfo) -> QScreen | None:
    """Find the QScreen matching a monitor, by physical origin.

    Matched on position rather than index: Qt's screen order and the Win32 enumeration
    order are independently defined and do not have to agree.

    The match is nearest-origin rather than exact. Qt reports logical geometry, so
    reconstructing a physical origin from it rounds, and on a mixed-DPI desktop the rounding
    error accumulates across screens. Demanding an exact hit means one stray pixel drops the
    screen from the overlay -- and if it happens on every screen, the hotkey silently does
    nothing, which is this application's worst failure mode.
    """
    best: QScreen | None = None
    best_distance = _ORIGIN_TOLERANCE_PX
    for screen in QGuiApplication.screens():
        geometry = screen.geometry()
        ratio = screen.devicePixelRatio()
        distance = max(
            abs(round(geometry.left() * ratio) - monitor.bounds.left),
            abs(round(geometry.top() * ratio) - monitor.bounds.top),
        )
        if distance < best_distance:
            best, best_distance = screen, distance
    return best
