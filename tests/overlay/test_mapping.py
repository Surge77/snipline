"""Overlay coordinate mapping.

Qt delivers mouse events in logical widget coordinates; the selection model and the capture
backend speak absolute physical pixels. This conversion is the single boundary between the
two, and it is per-screen: on a mixed-DPI desktop there is no one scale factor for the
virtual desktop, which is exactly why a drag across a seam goes wrong in most tools.
"""

from __future__ import annotations

import pytest

from snipline.overlay.mapping import (
    frame_slice_for,
    local_to_physical,
    physical_to_local,
)
from snipline.platform.geometry import MonitorInfo, PhysicalRect

PRIMARY_4K = MonitorInfo(
    0, PhysicalRect(0, 0, 3840, 2160), PhysicalRect(0, 0, 3840, 2160), 1.5, True
)
LEFT_1080P = MonitorInfo(
    1, PhysicalRect(-1920, 0, 1920, 1080), PhysicalRect(-1920, 0, 1920, 1080), 1.0, False
)


def test_origin_of_a_screen_maps_to_that_screens_physical_origin() -> None:
    assert local_to_physical(PRIMARY_4K, 0, 0) == (0, 0)
    assert local_to_physical(LEFT_1080P, 0, 0) == (-1920, 0)


def test_scaling_is_applied_before_the_monitor_offset() -> None:
    # 100 logical points on a 150% screen is 150 physical pixels. Adding the offset first
    # and scaling afterwards would move the point by half the monitor's origin.
    assert local_to_physical(PRIMARY_4K, 100, 200) == (150, 300)


def test_offset_is_applied_for_a_negative_origin_screen() -> None:
    assert local_to_physical(LEFT_1080P, 100, 50) == (-1820, 50)


def test_the_far_corner_of_each_screen_maps_inside_its_bounds() -> None:
    # 3840x2160 at 150% is 2560x1440 logical.
    x, y = local_to_physical(PRIMARY_4K, 2559, 1439)

    assert PRIMARY_4K.bounds.contains(x, y)


def test_the_same_logical_point_on_two_screens_maps_to_different_physical_points() -> None:
    # The bug this module exists to prevent: one device-pixel-ratio applied to the whole
    # virtual desktop instead of each screen's own.
    assert local_to_physical(PRIMARY_4K, 100, 100) != local_to_physical(LEFT_1080P, 100, 100)


@pytest.mark.parametrize("monitor", [PRIMARY_4K, LEFT_1080P])
@pytest.mark.parametrize(("x", "y"), [(0, 0), (10, 20), (500, 400)])
def test_physical_and_local_conversions_are_inverse(
    monitor: MonitorInfo, x: int, y: int
) -> None:
    physical = local_to_physical(monitor, x, y)

    assert physical_to_local(monitor, *physical) == (x, y)


def test_frame_slice_is_the_monitors_own_area_within_the_desktop_frame() -> None:
    desktop = PhysicalRect(-1920, 0, 5760, 2160)

    # The frozen frame's buffer starts at the desktop origin, which is negative here, so a
    # monitor's slice must be rebased rather than used at its absolute coordinates.
    assert frame_slice_for(LEFT_1080P, desktop) == PhysicalRect(0, 0, 1920, 1080)
    assert frame_slice_for(PRIMARY_4K, desktop) == PhysicalRect(1920, 0, 3840, 2160)


def test_frame_slice_of_a_vertically_offset_monitor() -> None:
    desktop = PhysicalRect(0, -200, 1920, 1280)
    high = MonitorInfo(
        0, PhysicalRect(0, -200, 1920, 200), PhysicalRect(0, -200, 1920, 200), 1.0, False
    )

    assert frame_slice_for(high, desktop) == PhysicalRect(0, 0, 1920, 200)
