"""Capture service: what gets grabbed, and from where.

The assertions here lean on FakeBackend's coordinate-keyed gradient. Checking a corner
pixel's value proves the capture landed on the intended part of the *virtual desktop*, not
merely that a correctly sized buffer came back -- which is the difference between catching a
whole-monitor offset bug and missing it.
"""

from __future__ import annotations

import pytest

from snipline.capture.fake_backend import FakeBackend, pixel_value
from snipline.capture.service import CaptureService
from snipline.platform.geometry import MonitorInfo, PhysicalRect


def _service(backend: FakeBackend, monitors: list[MonitorInfo]) -> CaptureService:
    return CaptureService(backend=backend, monitors_provider=lambda: monitors)


def _top_left_pixel(frame: object) -> tuple[int, int, int, int]:
    from snipline.capture.frame import Frame

    assert isinstance(frame, Frame)
    return tuple(frame.pixels[0:4])  # type: ignore[return-value]


def test_grab_desktop_covers_the_union_of_all_monitors(
    backend: FakeBackend, layout: list[MonitorInfo]
) -> None:
    frame = _service(backend, layout).grab_desktop()

    assert frame.rect.left == min(m.bounds.left for m in layout)
    assert frame.rect.right == max(m.bounds.right for m in layout)


def test_grab_desktop_starts_at_the_true_origin_even_when_negative(
    backend: FakeBackend,
) -> None:
    monitors = [
        MonitorInfo(0, PhysicalRect(0, 0, 1920, 1080), PhysicalRect(0, 0, 1920, 1080), 1.0, True),
        MonitorInfo(
            1, PhysicalRect(-1920, 0, 1920, 1080), PhysicalRect(-1920, 0, 1920, 1080), 1.0, False
        ),
    ]
    frame = _service(backend, monitors).grab_desktop()

    assert frame.rect.left == -1920
    assert _top_left_pixel(frame) == pixel_value(-1920, 0)


def test_grab_monitor_returns_exactly_that_monitors_physical_bounds(
    backend: FakeBackend, layout: list[MonitorInfo]
) -> None:
    service = _service(backend, layout)

    for monitor in layout:
        frame = service.grab_monitor(monitor.index)
        assert frame.rect == monitor.bounds
        assert frame.width == monitor.bounds.width
        assert frame.height == monitor.bounds.height


def test_grab_monitor_on_a_high_dpi_screen_returns_physical_not_logical_size(
    backend: FakeBackend,
) -> None:
    # A 3840x2160 panel at 150% is 2560x1440 logical. Returning the logical size here is
    # the exact bug this project exists to prevent.
    bounds = PhysicalRect(0, 0, 3840, 2160)
    monitors = [MonitorInfo(0, bounds, bounds, 1.5, True)]

    frame = _service(backend, monitors).grab_monitor(0)

    assert (frame.width, frame.height) == (3840, 2160)


def test_grab_monitor_rejects_an_unknown_index(
    backend: FakeBackend, layout: list[MonitorInfo]
) -> None:
    with pytest.raises(IndexError, match="no monitor"):
        _service(backend, layout).grab_monitor(len(layout))


def test_grab_region_captures_only_the_requested_rect(backend: FakeBackend) -> None:
    bounds = PhysicalRect(0, 0, 1920, 1080)
    monitors = [MonitorInfo(0, bounds, bounds, 1.0, True)]
    region = PhysicalRect(100, 50, 32, 16)

    frame = _service(backend, monitors).grab_region(region)

    assert frame.rect == region
    assert _top_left_pixel(frame) == pixel_value(100, 50)
    assert backend.grab_calls == [region]


def test_grab_region_clamps_a_selection_dragged_past_the_desktop_edge(
    backend: FakeBackend,
) -> None:
    bounds = PhysicalRect(0, 0, 1920, 1080)
    monitors = [MonitorInfo(0, bounds, bounds, 1.0, True)]

    frame = _service(backend, monitors).grab_region(PhysicalRect(1900, 1070, 200, 200))

    assert frame.rect == PhysicalRect(1900, 1070, 20, 10)


def test_grab_region_rejects_a_selection_entirely_off_the_desktop(
    backend: FakeBackend,
) -> None:
    bounds = PhysicalRect(0, 0, 1920, 1080)
    monitors = [MonitorInfo(0, bounds, bounds, 1.0, True)]

    with pytest.raises(ValueError, match="outside the virtual desktop"):
        _service(backend, monitors).grab_region(PhysicalRect(5000, 5000, 100, 100))


def test_grab_region_rejects_an_empty_selection(backend: FakeBackend) -> None:
    bounds = PhysicalRect(0, 0, 1920, 1080)
    monitors = [MonitorInfo(0, bounds, bounds, 1.0, True)]

    with pytest.raises(ValueError, match="empty"):
        _service(backend, monitors).grab_region(PhysicalRect(10, 10, 0, 40))


def test_monitor_under_point_finds_the_owning_screen(
    backend: FakeBackend,
) -> None:
    left = PhysicalRect(-1920, 0, 1920, 1080)
    primary = PhysicalRect(0, 0, 1920, 1080)
    monitors = [
        MonitorInfo(0, primary, primary, 1.0, True),
        MonitorInfo(1, left, left, 1.0, False),
    ]
    service = _service(backend, monitors)

    assert service.monitor_under_point(-100, 10) is not None
    assert service.monitor_under_point(-100, 10).index == 1  # type: ignore[union-attr]
    assert service.monitor_under_point(99_999, 0) is None


def test_close_releases_the_backend(backend: FakeBackend) -> None:
    bounds = PhysicalRect(0, 0, 10, 10)
    service = _service(backend, [MonitorInfo(0, bounds, bounds, 1.0, True)])

    service.close()

    assert backend.closed


def test_freezing_the_desktop_reads_the_monitor_layout_once(
    backend: FakeBackend, layout: list[MonitorInfo]
) -> None:
    # Two enumerations per capture put a second EnumDisplayMonitors walk on the span the
    # benchmark measures, and let the frame and the layout it is sliced against disagree if
    # a display changes in between.
    calls = 0

    def counting_provider() -> list[MonitorInfo]:
        nonlocal calls
        calls += 1
        return layout

    service = CaptureService(backend=backend, monitors_provider=counting_provider)

    frame, monitors = service.grab_desktop_with_monitors()

    assert calls == 1
    assert list(monitors) == layout
    assert frame.rect == service.desktop_rect()
