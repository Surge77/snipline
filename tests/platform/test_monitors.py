"""Monitor enumeration: the pure half.

The ctypes half is a thin fetch of raw numbers from the OS and is covered by the manual
checklist. Everything that can be wrong about *interpreting* those numbers -- ordering,
negative origins, DPI-to-scale conversion, work areas -- lives in ``monitors_from_raw``
and is tested here against the same synthetic layouts the rest of the suite uses.
"""

from __future__ import annotations

import pytest

from snipline.platform.geometry import PhysicalRect
from snipline.platform.monitors import RawMonitor, monitors_from_raw, virtual_desktop_of


def _raw(
    left: int,
    top: int,
    width: int,
    height: int,
    dpi: int = 96,
    primary: bool = False,
    work_inset: int = 0,
) -> RawMonitor:
    return RawMonitor(
        left=left,
        top=top,
        right=left + width,
        bottom=top + height,
        work_left=left,
        work_top=top,
        work_right=left + width,
        work_bottom=top + height - work_inset,
        dpi=dpi,
        is_primary=primary,
    )


def test_converts_bounds_to_physical_rect() -> None:
    monitors = monitors_from_raw([_raw(0, 0, 1920, 1080, primary=True)])

    assert monitors[0].bounds == PhysicalRect(0, 0, 1920, 1080)


def test_converts_dpi_to_scale_factor() -> None:
    monitors = monitors_from_raw([_raw(0, 0, 3840, 2160, dpi=144, primary=True)])

    assert monitors[0].scale == pytest.approx(1.5)


def test_preserves_negative_origin() -> None:
    monitors = monitors_from_raw(
        [
            _raw(0, 0, 3840, 2160, dpi=144, primary=True),
            _raw(-1920, 0, 1920, 1080),
        ]
    )
    secondary = next(m for m in monitors if not m.is_primary)

    assert secondary.bounds.left == -1920


def test_taskbar_inset_produces_smaller_work_area() -> None:
    monitors = monitors_from_raw([_raw(0, 0, 1920, 1080, primary=True, work_inset=48)])

    assert monitors[0].work_area == PhysicalRect(0, 0, 1920, 1032)
    assert monitors[0].bounds.height == 1080


def test_primary_is_listed_first_regardless_of_os_order() -> None:
    monitors = monitors_from_raw(
        [
            _raw(-1920, 0, 1920, 1080),
            _raw(0, 0, 1920, 1080, primary=True),
        ]
    )

    assert monitors[0].is_primary
    assert monitors[0].index == 0


def test_secondaries_are_ordered_left_to_right_then_top_to_bottom() -> None:
    monitors = monitors_from_raw(
        [
            _raw(1920, 0, 1920, 1080),
            _raw(-1920, 0, 1920, 1080),
            _raw(0, 0, 1920, 1080, primary=True),
        ]
    )

    assert [m.bounds.left for m in monitors] == [0, -1920, 1920]


def test_indices_are_contiguous_from_zero() -> None:
    monitors = monitors_from_raw(
        [_raw(0, 0, 800, 600, primary=True), _raw(800, 0, 800, 600), _raw(1600, 0, 800, 600)]
    )

    assert [m.index for m in monitors] == [0, 1, 2]


def test_rejects_an_empty_enumeration() -> None:
    # No monitors means the OS handed back nothing usable. Returning an empty list would
    # push the failure downstream into a zero-sized capture, which is far harder to read.
    with pytest.raises(ValueError, match="no monitors"):
        monitors_from_raw([])


def test_rejects_a_monitor_with_inverted_bounds() -> None:
    inverted = RawMonitor(
        left=100,
        top=0,
        right=0,
        bottom=100,
        work_left=100,
        work_top=0,
        work_right=0,
        work_bottom=100,
        dpi=96,
        is_primary=True,
    )
    with pytest.raises(ValueError, match="inverted"):
        monitors_from_raw([inverted])


def test_virtual_desktop_spans_negative_origin_layout(
    layout: list[object],
) -> None:
    from snipline.platform.geometry import MonitorInfo

    typed = [m for m in layout if isinstance(m, MonitorInfo)]
    desktop = virtual_desktop_of(typed)

    assert desktop.left == min(m.bounds.left for m in typed)
    assert desktop.right == max(m.bounds.right for m in typed)
    assert desktop.top == min(m.bounds.top for m in typed)
    assert desktop.bottom == max(m.bounds.bottom for m in typed)
