"""Per-monitor DPI awareness.

``declare_dpi_awareness()`` must run before ``QApplication`` is constructed and before any
other Win32 call. Declared late, Windows silently virtualises coordinates: monitor bounds
come back in scaled units, captures land in the wrong place, and the result is blurry --
and all of it only on high-DPI monitors, so a single-1080p dev machine never reproduces it.
"""

from __future__ import annotations

import sys

# SetProcessDpiAwarenessContext values from winuser.h. V2 is what gives per-monitor
# awareness plus correct scaling of non-client areas (title bars, scroll bars).
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4

USER_DEFAULT_SCREEN_DPI = 96.0


def declare_dpi_awareness() -> bool:
    """Opt this process into per-monitor DPI awareness V2.

    Returns True when awareness is in effect. Returns False on non-Windows platforms and
    when the OS rejects the call, which happens if awareness was already set -- by an
    embedding host, or by a manifest. That is not an error: an already-correct process
    stays correct.
    """
    if sys.platform != "win32":
        return False

    import ctypes

    user32 = ctypes.windll.user32  # type: ignore[attr-defined]
    try:
        set_context = user32.SetProcessDpiAwarenessContext
    except AttributeError:
        # Pre-1703 Windows. Out of support and out of scope; the app declares Windows 10+.
        return False

    set_context.restype = ctypes.c_bool
    set_context.argtypes = [ctypes.c_void_p]
    return bool(set_context(ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)))


def scale_from_dpi(dpi: int) -> float:
    """Convert a raw DPI value to a scale factor. 96 DPI is 100%, 144 is 150%."""
    if dpi <= 0:
        raise ValueError(f"non-positive DPI: {dpi}")
    return dpi / USER_DEFAULT_SCREEN_DPI


def dpi_from_scale(scale: float) -> int:
    if scale <= 0:
        raise ValueError(f"non-positive scale: {scale}")
    return round(scale * USER_DEFAULT_SCREEN_DPI)
