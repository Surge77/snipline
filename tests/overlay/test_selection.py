"""The selection state machine.

Pure and Qt-free, so every interaction the overlay supports -- drag in any direction,
arrow-key nudge, click-without-drag, cancel -- is tested headlessly. The overlay widget on
top of this owns only painting and event forwarding.

All coordinates are absolute physical pixels, including negative ones.
"""

from __future__ import annotations

import pytest

from snipline.overlay.selection import CLICK_THRESHOLD_PX, Edge, SelectionModel
from snipline.platform.geometry import MonitorInfo, PhysicalRect

PRIMARY = PhysicalRect(0, 0, 1920, 1080)
LEFT_OF_PRIMARY = PhysicalRect(-1920, 0, 1920, 1080)

MONITORS = [
    MonitorInfo(0, PRIMARY, PRIMARY, 1.0, True),
    MonitorInfo(1, LEFT_OF_PRIMARY, LEFT_OF_PRIMARY, 1.0, False),
]
DESKTOP = PhysicalRect(-1920, 0, 3840, 1080)


@pytest.fixture
def model() -> SelectionModel:
    return SelectionModel(desktop=DESKTOP, monitors=MONITORS)


def test_starts_with_no_selection(model: SelectionModel) -> None:
    assert model.rect is None
    assert not model.is_dragging


def test_a_left_to_right_drag_produces_the_dragged_rect(model: SelectionModel) -> None:
    model.begin(100, 100)
    model.update(300, 250)

    assert model.is_dragging
    assert model.rect == PhysicalRect(100, 100, 200, 150)


def test_a_right_to_left_upward_drag_is_normalised(model: SelectionModel) -> None:
    # Dragging from the bottom-right corner is normal and must not produce a negative
    # extent, which PhysicalRect would reject outright.
    model.begin(300, 250)
    model.update(100, 100)

    assert model.rect == PhysicalRect(100, 100, 200, 150)


def test_a_drag_across_a_negative_origin_monitor_boundary(model: SelectionModel) -> None:
    model.begin(-200, 400)
    model.update(200, 500)

    assert model.rect == PhysicalRect(-200, 400, 400, 100)


def test_a_drag_beyond_the_desktop_is_clamped(model: SelectionModel) -> None:
    # The pointer can be reported outside the desktop bounds; a selection must never be.
    model.begin(1800, 1000)
    model.update(5000, 5000)

    assert model.rect == PhysicalRect(1800, 1000, 120, 80)


def test_commit_returns_the_rect_and_ends_the_drag(model: SelectionModel) -> None:
    model.begin(10, 20)
    model.update(110, 120)

    committed = model.commit()

    assert committed == PhysicalRect(10, 20, 100, 100)
    assert not model.is_dragging


def test_cancel_discards_the_selection(model: SelectionModel) -> None:
    model.begin(10, 20)
    model.update(110, 120)

    model.cancel()

    assert model.rect is None
    assert model.cancelled
    assert model.commit() is None


def test_a_click_without_drag_selects_the_monitor_under_the_cursor(
    model: SelectionModel,
) -> None:
    # Documented in the plan: click without dragging captures the monitor under the cursor.
    model.begin(-500, 500)
    model.update(-500 + CLICK_THRESHOLD_PX - 1, 500)

    assert model.commit() == LEFT_OF_PRIMARY


def test_a_click_in_dead_space_selects_nothing(model: SelectionModel) -> None:
    # An L-shaped arrangement leaves points inside the desktop bounds that no monitor owns.
    sparse = SelectionModel(
        desktop=PhysicalRect(0, 0, 2000, 2000),
        monitors=[MonitorInfo(0, PhysicalRect(0, 0, 100, 100), PRIMARY, 1.0, True)],
    )
    sparse.begin(1500, 1500)

    assert sparse.commit() is None


def test_a_drag_longer_than_the_threshold_is_not_treated_as_a_click(
    model: SelectionModel,
) -> None:
    model.begin(100, 100)
    model.update(100 + CLICK_THRESHOLD_PX + 1, 100 + CLICK_THRESHOLD_PX + 1)

    committed = model.commit()

    assert committed is not None
    assert committed != PRIMARY
    assert committed.width == CLICK_THRESHOLD_PX + 1


def test_committing_without_a_drag_started_returns_nothing(model: SelectionModel) -> None:
    assert model.commit() is None


@pytest.mark.parametrize(
    ("edge", "delta", "expected"),
    [
        (Edge.RIGHT, 3, PhysicalRect(100, 100, 203, 150)),
        (Edge.RIGHT, -3, PhysicalRect(100, 100, 197, 150)),
        (Edge.LEFT, -5, PhysicalRect(95, 100, 205, 150)),
        (Edge.TOP, -5, PhysicalRect(100, 95, 200, 155)),
        (Edge.BOTTOM, 4, PhysicalRect(100, 100, 200, 154)),
    ],
)
def test_arrow_key_nudge_moves_one_edge(
    model: SelectionModel, edge: Edge, delta: int, expected: PhysicalRect
) -> None:
    # Pixel-precise edges are the reason the overlay exists rather than a plain drag.
    model.begin(100, 100)
    model.update(300, 250)

    model.nudge(edge, delta)

    assert model.rect == expected


def test_nudging_cannot_invert_an_edge_past_its_opposite(model: SelectionModel) -> None:
    model.begin(100, 100)
    model.update(110, 110)

    model.nudge(Edge.RIGHT, -100)

    assert model.rect is not None
    assert model.rect.width == 0
    assert model.rect.left == 100


def test_nudging_is_clamped_to_the_desktop(model: SelectionModel) -> None:
    model.begin(-1900, 10)
    model.update(-1800, 200)

    model.nudge(Edge.LEFT, -500)

    assert model.rect is not None
    assert model.rect.left == DESKTOP.left


def test_nudging_before_a_selection_exists_does_nothing(model: SelectionModel) -> None:
    model.nudge(Edge.RIGHT, 5)

    assert model.rect is None


def test_a_zero_area_drag_commits_as_nothing(model: SelectionModel) -> None:
    # Press and release without moving on a point no monitor owns: nothing to capture, and
    # an empty rect would fail deeper in the capture path with a worse message.
    empty = SelectionModel(desktop=DESKTOP, monitors=[])
    empty.begin(50, 50)

    assert empty.commit() is None


def test_reset_clears_state_for_the_next_capture(model: SelectionModel) -> None:
    model.begin(10, 10)
    model.update(100, 100)
    model.cancel()

    model.reset()

    assert not model.cancelled
    assert model.rect is None
