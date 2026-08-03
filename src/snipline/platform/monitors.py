"""Monitor enumeration.

Split deliberately in two:

- ``monitors_from_raw`` is pure. It owns every decision that can be *wrong* -- ordering,
  DPI-to-scale conversion, negative origins, work-area insets -- and is unit tested against
  synthetic layouts including the negative-coordinate ones that break most tools.
- ``enumerate_monitors`` is a thin ``ctypes`` shell that only fetches raw numbers. It has no
  logic worth mocking, so it is covered by the manual checklist instead.

**Why Win32 and not ``QGuiApplication.screens()``.** Qt reports screen geometry in a virtual
*logical* coordinate space. On a mixed-DPI desktop, multiplying each screen's logical origin
by its own device pixel ratio does not reconstruct the true physical layout -- the errors
accumulate across screens and land as whole-monitor crop offsets. ``EnumDisplayMonitors``
reports real physical pixels directly, provided the process declared per-monitor DPI
awareness first (see ``dpi.py``). Qt's logical geometry is still the right source for mouse
events in the overlay; that conversion happens at an explicit boundary in M3.

Monitor state is re-read on every capture rather than cached at startup: docking, hot-plug,
and scaling changes all rearrange the desktop while the app is running.
"""

from __future__ import annotations

import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from snipline.platform.dpi import scale_from_dpi
from snipline.platform.geometry import MonitorInfo, PhysicalRect, virtual_desktop

__all__ = [
    "MonitorInfo",
    "RawMonitor",
    "enumerate_monitors",
    "monitors_from_raw",
    "primary_monitor",
    "virtual_desktop_of",
    "virtual_desktop_rect",
]

MDT_EFFECTIVE_DPI = 0
MONITORINFOF_PRIMARY = 0x1
FALLBACK_DPI = 96


@dataclass(frozen=True, slots=True)
class RawMonitor:
    """One display exactly as the OS reports it: edges, not extents.

    Win32 hands back right/bottom edges rather than width/height, and this type keeps that
    shape so the conversion happens in one tested place rather than at the ctypes boundary.
    """

    left: int
    top: int
    right: int
    bottom: int
    work_left: int
    work_top: int
    work_right: int
    work_bottom: int
    dpi: int
    is_primary: bool


def _rect(left: int, top: int, right: int, bottom: int) -> PhysicalRect:
    if right < left or bottom < top:
        raise ValueError(f"inverted monitor rect: ({left}, {top}) to ({right}, {bottom})")
    return PhysicalRect(left, top, right - left, bottom - top)


def _sort_key(raw: RawMonitor) -> tuple[int, int, int]:
    # Primary first -- it is the origin of the virtual desktop and the sensible default
    # target -- then left to right, then top to bottom, so indices stay stable across runs
    # even when the OS enumeration order does not.
    return (0 if raw.is_primary else 1, raw.left, raw.top)


def monitors_from_raw(raws: Sequence[RawMonitor]) -> list[MonitorInfo]:
    """Interpret raw OS monitor data into ordered, typed monitor descriptions."""
    if not raws:
        raise ValueError("no monitors reported by the OS")

    return [
        MonitorInfo(
            index=index,
            bounds=_rect(raw.left, raw.top, raw.right, raw.bottom),
            work_area=_rect(raw.work_left, raw.work_top, raw.work_right, raw.work_bottom),
            scale=scale_from_dpi(raw.dpi),
            is_primary=raw.is_primary,
        )
        for index, raw in enumerate(sorted(raws, key=_sort_key))
    ]


def _enumerate_raw() -> list[RawMonitor]:
    """Fetch raw monitor data from Win32. No interpretation happens here."""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    shcore = ctypes.windll.shcore  # type: ignore[attr-defined]

    class MONITORINFO(ctypes.Structure):
        _fields_ = (
            ("cbSize", wintypes.DWORD),
            ("rcMonitor", wintypes.RECT),
            ("rcWork", wintypes.RECT),
            ("dwFlags", wintypes.DWORD),
        )

    collected: list[RawMonitor] = []

    callback_type = ctypes.WINFUNCTYPE(  # type: ignore[attr-defined]
        wintypes.BOOL,
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(wintypes.RECT),
        wintypes.LPARAM,
    )

    def on_monitor(handle: int, _hdc: int, _bounds: object, _param: int) -> int:
        info = MONITORINFO()
        info.cbSize = ctypes.sizeof(MONITORINFO)
        if not user32.GetMonitorInfoW(handle, ctypes.byref(info)):
            return 1  # skip this display; a failed query is no reason to abort the walk

        dpi_x = ctypes.c_uint()
        dpi_y = ctypes.c_uint()
        # A failing HRESULT leaves dpi_x at 0; fall back to 96 rather than propagating a
        # zero that scale_from_dpi would reject.
        shcore.GetDpiForMonitor(
            handle, MDT_EFFECTIVE_DPI, ctypes.byref(dpi_x), ctypes.byref(dpi_y)
        )

        collected.append(
            RawMonitor(
                left=info.rcMonitor.left,
                top=info.rcMonitor.top,
                right=info.rcMonitor.right,
                bottom=info.rcMonitor.bottom,
                work_left=info.rcWork.left,
                work_top=info.rcWork.top,
                work_right=info.rcWork.right,
                work_bottom=info.rcWork.bottom,
                dpi=dpi_x.value or FALLBACK_DPI,
                is_primary=bool(info.dwFlags & MONITORINFOF_PRIMARY),
            )
        )
        return 1

    if not user32.EnumDisplayMonitors(None, None, callback_type(on_monitor), 0):
        raise RuntimeError("EnumDisplayMonitors failed")
    return collected


def enumerate_monitors() -> list[MonitorInfo]:
    """All connected displays in physical pixels, primary first.

    Requires ``declare_dpi_awareness()`` to have run: without it Windows returns virtualised
    coordinates and every downstream capture is silently wrong on high-DPI monitors.
    """
    if sys.platform != "win32":
        raise RuntimeError("monitor enumeration is Windows-only; platform/ is the seam")
    return monitors_from_raw(_enumerate_raw())


def virtual_desktop_of(monitors: Iterable[MonitorInfo]) -> PhysicalRect:
    """Bounding rect of the given monitors. Pure; prefer this in services and tests."""
    return virtual_desktop(monitors)


def virtual_desktop_rect() -> PhysicalRect:
    """Bounding rect of every connected monitor, in physical pixels.

    The origin is frequently negative: a monitor positioned left of or above the primary
    extends into negative virtual-desktop coordinates.
    """
    return virtual_desktop_of(enumerate_monitors())


def primary_monitor(monitors: Sequence[MonitorInfo]) -> MonitorInfo:
    if not monitors:
        raise ValueError("no monitors")
    return next((m for m in monitors if m.is_primary), monitors[0])
