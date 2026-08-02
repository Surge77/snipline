"""Monitor enumeration.

Lands in M1. The pure geometry these functions feed -- unions, hit testing, virtual desktop
derivation -- already lives in ``geometry.py`` and is tested there against synthetic layouts,
so the untested surface here stays as thin as possible.

Monitor state is re-read on every capture rather than cached at startup: docking, hot-plug,
and scaling changes all rearrange the desktop while the app is running.
"""

from __future__ import annotations

from snipline.platform.geometry import MonitorInfo, PhysicalRect, virtual_desktop

__all__ = ["MonitorInfo", "enumerate_monitors", "virtual_desktop_rect"]


def enumerate_monitors() -> list[MonitorInfo]:
    """All connected displays, in OS enumeration order, primary first.

    To be implemented in M1 over ``QGuiApplication.screens()``, reading bounds from
    ``QScreen.geometry()`` scaled by ``devicePixelRatio()`` to reach physical pixels. Qt is
    preferred over raw ``EnumDisplayMonitors`` because it already tracks per-screen device
    pixel ratios and emits change signals on hot-plug.
    """
    raise NotImplementedError("M1: monitor enumeration")


def virtual_desktop_rect() -> PhysicalRect:
    """Bounding rect of every monitor, in physical pixels.

    The origin is frequently negative: a monitor positioned left of or above the primary
    extends into negative virtual-desktop coordinates.
    """
    return virtual_desktop(enumerate_monitors())
