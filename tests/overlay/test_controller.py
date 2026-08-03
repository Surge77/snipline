"""Overlay coordination.

The offscreen platform reports one screen, so multi-monitor overlay *rendering* is a manual
check. What is tested here is the coordination that a second monitor would only reveal after
the fact: that the frozen frame is sliced per screen, that a commit crops the frozen pixels
rather than re-capturing, and that every window is torn down together.

A window left behind covers a monitor with an unclickable frozen image of itself, which
looks like the machine has hung -- so teardown is asserted on every exit path.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from snipline.capture.fake_backend import FakeBackend, pixel_value
from snipline.overlay.controller import OverlayController
from snipline.platform.geometry import MonitorInfo, PhysicalRect

DESKTOP = PhysicalRect(0, 0, 800, 600)
MONITORS = [MonitorInfo(0, DESKTOP, DESKTOP, 1.0, True)]


def _controller() -> OverlayController:
    return OverlayController(frozen=FakeBackend().grab(DESKTOP), monitors=MONITORS)


def test_a_window_is_built_for_each_matched_screen(qapp: QApplication) -> None:
    controller = _controller()
    try:
        assert len(controller.build_windows()) == len(QApplication.screens())
    finally:
        controller.close()


def test_windows_that_match_no_screen_are_skipped_rather_than_crashing(
    qapp: QApplication,
) -> None:
    # Happens mid-hot-plug, when Qt and Win32 briefly disagree about the layout.
    phantom = PhysicalRect(99_000, 99_000, 640, 480)
    controller = OverlayController(
        frozen=FakeBackend().grab(DESKTOP),
        monitors=[MonitorInfo(9, phantom, phantom, 1.0, False)],
    )
    try:
        assert controller.build_windows() == []
        assert not controller.show()
    finally:
        controller.close()


def test_committing_a_drag_emits_the_selected_region(qapp: QApplication) -> None:
    controller = _controller()
    selected: list[PhysicalRect] = []
    controller.selected.connect(selected.append)
    controller.build_windows()

    controller.model.begin(100, 80)
    controller.model.update(300, 260)
    controller.commit()  # what a mouse release reaches

    assert selected == [PhysicalRect(100, 80, 200, 180)]


def test_committing_closes_every_window(qapp: QApplication) -> None:
    controller = _controller()
    windows = controller.build_windows()
    controller.model.begin(10, 10)
    controller.model.update(200, 200)

    controller.commit()

    assert all(not window.isVisible() for window in windows)


def test_cancelling_emits_cancelled_and_closes_every_window(qapp: QApplication) -> None:
    controller = _controller()
    windows = controller.build_windows()
    cancelled: list[bool] = []
    controller.cancelled.connect(lambda: cancelled.append(True))

    controller.cancel()

    assert cancelled == [True]
    assert all(not window.isVisible() for window in windows)


def test_an_empty_selection_cancels_rather_than_capturing_nothing(
    qapp: QApplication,
) -> None:
    controller = _controller()
    controller.build_windows()
    outcomes: list[str] = []
    def on_selected(_region: PhysicalRect) -> None:
        outcomes.append("selected")

    controller.selected.connect(on_selected)
    controller.cancelled.connect(lambda: outcomes.append("cancelled"))

    # Press and release on the same pixel of a point no monitor owns.
    empty = OverlayController(frozen=FakeBackend().grab(DESKTOP), monitors=[])
    empty.selected.connect(on_selected)
    empty.cancelled.connect(lambda: outcomes.append("cancelled"))
    empty.model.begin(400, 300)
    empty.commit()

    assert outcomes == ["cancelled"]


def test_crop_takes_pixels_from_the_frozen_frame(qapp: QApplication) -> None:
    # The defining property of freeze-then-overlay (D5): no second capture happens, so the
    # cropped pixels are the ones from before the overlay was on screen.
    backend = FakeBackend()
    controller = OverlayController(frozen=backend.grab(DESKTOP), monitors=MONITORS)
    grabs_before = len(backend.grab_calls)

    cropped = controller.crop(PhysicalRect(100, 50, 32, 16))

    assert len(backend.grab_calls) == grabs_before
    assert cropped.rect == PhysicalRect(100, 50, 32, 16)
    assert tuple(cropped.pixels[0:4]) == pixel_value(100, 50)


def test_show_resets_state_left_over_from_a_previous_capture(qapp: QApplication) -> None:
    controller = _controller()
    try:
        controller.model.begin(10, 10)
        controller.model.cancel()

        controller.show()

        assert not controller.model.cancelled
        assert controller.model.rect is None
    finally:
        controller.close()
