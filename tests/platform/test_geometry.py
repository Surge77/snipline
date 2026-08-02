from __future__ import annotations

import pytest

from snipline.platform.geometry import (
    LogicalRect,
    MonitorInfo,
    PhysicalRect,
    Point,
    monitor_at,
    rect_from_corners,
    union,
    virtual_desktop,
)
from tests.conftest import LAYOUT_C1, LAYOUT_C3, LAYOUT_C4, LAYOUT_C5


class TestRectBasics:
    def test_computes_edges_from_origin_and_extent(self) -> None:
        rect = PhysicalRect(10, 20, 100, 50)
        assert (rect.right, rect.bottom) == (110, 70)

    def test_rejects_negative_extent(self) -> None:
        with pytest.raises(ValueError, match="negative extent"):
            PhysicalRect(0, 0, -1, 10)

    def test_allows_negative_origin(self) -> None:
        # A monitor left of the primary lives at negative virtual-desktop coordinates.
        rect = PhysicalRect(-1920, -200, 1920, 1080)
        assert rect.right == 0
        assert rect.bottom == 880

    def test_contains_excludes_the_far_edge(self) -> None:
        rect = PhysicalRect(0, 0, 10, 10)
        assert rect.contains(9, 9)
        assert not rect.contains(10, 10)

    def test_reports_zero_extent_as_empty(self) -> None:
        assert PhysicalRect(5, 5, 0, 10).is_empty


class TestRectFromCorners:
    def test_normalises_a_right_to_left_drag(self) -> None:
        rect = rect_from_corners(Point(300, 100), Point(100, 400))
        assert rect == PhysicalRect(100, 100, 200, 300)

    def test_normalises_a_bottom_to_top_drag(self) -> None:
        rect = rect_from_corners(Point(50, 500), Point(150, 200))
        assert rect == PhysicalRect(50, 200, 100, 300)

    def test_a_click_without_drag_is_empty(self) -> None:
        assert rect_from_corners(Point(7, 9), Point(7, 9)).is_empty


class TestIntersection:
    def test_returns_the_overlapping_area(self) -> None:
        a = PhysicalRect(0, 0, 100, 100)
        b = PhysicalRect(50, 50, 100, 100)
        assert a.intersection(b) == PhysicalRect(50, 50, 50, 50)

    def test_returns_empty_when_disjoint(self) -> None:
        a = PhysicalRect(0, 0, 10, 10)
        b = PhysicalRect(100, 100, 10, 10)
        assert a.intersection(b).is_empty

    def test_clamps_a_selection_dragged_past_the_desktop_edge(self) -> None:
        desktop = PhysicalRect(0, 0, 1920, 1080)
        selection = PhysicalRect(1800, 1000, 400, 400)
        assert desktop.intersection(selection) == PhysicalRect(1800, 1000, 120, 80)


class TestNormalisedWithin:
    def test_rebases_against_a_negative_container_origin(self) -> None:
        # The bug this guards: indexing a buffer with absolute coordinates when the
        # virtual desktop starts left of zero reads from the wrong monitor entirely.
        container = PhysicalRect(-1920, 0, 3840, 1080)
        selection = PhysicalRect(-1820, 100, 200, 200)
        assert selection.normalised_within(container) == PhysicalRect(100, 100, 200, 200)

    def test_is_identity_for_a_zero_origin_container(self) -> None:
        container = PhysicalRect(0, 0, 1920, 1080)
        selection = PhysicalRect(10, 20, 30, 40)
        assert selection.normalised_within(container) == selection


class TestUnion:
    def test_bounds_all_rects(self) -> None:
        result = union([PhysicalRect(0, 0, 100, 100), PhysicalRect(200, 50, 100, 100)])
        assert result == PhysicalRect(0, 0, 300, 150)

    def test_handles_negative_origins(self) -> None:
        result = union([PhysicalRect(0, 0, 100, 100), PhysicalRect(-50, -25, 20, 20)])
        assert result == PhysicalRect(-50, -25, 150, 125)

    def test_ignores_empty_rects(self) -> None:
        # An empty rect at the origin must not drag the bounds back to zero.
        result = union([PhysicalRect(100, 100, 50, 50), PhysicalRect(0, 0, 0, 0)])
        assert result == PhysicalRect(100, 100, 50, 50)

    def test_returns_empty_for_no_rects(self) -> None:
        assert union([]).is_empty


class TestDpiConversion:
    def test_logical_to_physical_scales_up(self) -> None:
        assert LogicalRect(0, 0, 100, 100).to_physical(1.5) == PhysicalRect(0, 0, 150, 150)

    def test_physical_to_logical_scales_down(self) -> None:
        assert PhysicalRect(0, 0, 150, 150).to_logical(1.5) == LogicalRect(0, 0, 100, 100)

    def test_round_trips_within_a_pixel(self) -> None:
        original = LogicalRect(13, 27, 101, 57)
        result = original.to_physical(1.25).to_logical(1.25)
        for a, b in zip(
            (original.left, original.top, original.width, original.height),
            (result.left, result.top, result.width, result.height),
            strict=True,
        ):
            assert abs(a - b) <= 1

    def test_scales_a_negative_origin_correctly(self) -> None:
        assert LogicalRect(-100, -50, 10, 10).to_physical(2.0).left == -200


class TestMonitorLayouts:
    def test_virtual_desktop_of_a_single_monitor_is_that_monitor(self) -> None:
        assert virtual_desktop(LAYOUT_C1) == PhysicalRect(0, 0, 1920, 1080)

    def test_virtual_desktop_spans_side_by_side_mixed_dpi(self) -> None:
        assert virtual_desktop(LAYOUT_C3) == PhysicalRect(0, 0, 5760, 2160)

    def test_virtual_desktop_starts_negative_when_a_monitor_is_left_of_primary(self) -> None:
        desktop = virtual_desktop(LAYOUT_C4)
        assert desktop.left == -1920
        assert desktop.width == 5760

    def test_virtual_desktop_handles_vertical_offset(self) -> None:
        desktop = virtual_desktop(LAYOUT_C5)
        assert desktop.top == -200
        assert desktop.left == -3840

    def test_every_layout_produces_a_non_empty_desktop(
        self, layout: list[MonitorInfo]
    ) -> None:
        assert not virtual_desktop(layout).is_empty

    def test_every_layout_has_exactly_one_primary(self, layout: list[MonitorInfo]) -> None:
        assert sum(1 for m in layout if m.is_primary) == 1


class TestMonitorAt:
    def test_finds_the_monitor_owning_a_point(self) -> None:
        found = monitor_at(LAYOUT_C3, 4000, 500)
        assert found is not None
        assert found.index == 1

    def test_finds_a_monitor_at_negative_coordinates(self) -> None:
        found = monitor_at(LAYOUT_C4, -1000, 500)
        assert found is not None
        assert found.index == 1
        assert found.scale == 1.0

    def test_returns_none_for_dead_space_inside_the_desktop_bounds(self) -> None:
        # C5's monitors are vertically offset, leaving a gap that is inside the virtual
        # desktop's bounding box but on no actual display.
        assert monitor_at(LAYOUT_C5, 2000, -150) is not None
        assert monitor_at(LAYOUT_C5, 100, -150) is None

    def test_neighbouring_monitors_report_their_own_scale(self) -> None:
        left = monitor_at(LAYOUT_C3, 100, 100)
        right = monitor_at(LAYOUT_C3, 4000, 100)
        assert left is not None and right is not None
        assert left.scale != right.scale


class TestMonitorInfo:
    def test_rejects_a_non_positive_scale(self) -> None:
        with pytest.raises(ValueError, match="non-positive scale"):
            MonitorInfo(
                index=0,
                bounds=PhysicalRect(0, 0, 100, 100),
                work_area=PhysicalRect(0, 0, 100, 100),
                scale=0.0,
                is_primary=True,
            )
