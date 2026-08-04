"""Overlay painting geometry.

The offscreen platform reports one screen, so what the overlay *looks like* is a manual
check. What is asserted here is the arithmetic behind it, which is where the mistakes
actually are: a dim band drawn one pixel too far in covers the edge of the selection, so the
user lines their crop up against pixels the app is lying about.
"""

from __future__ import annotations

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from snipline.capture.fake_backend import FakeBackend
from snipline.overlay.controller import OverlayController
from snipline.overlay.window import OverlayWindow
from snipline.platform.geometry import MonitorInfo, PhysicalRect

DESKTOP = PhysicalRect(0, 0, 800, 600)
MONITORS = [MonitorInfo(0, DESKTOP, DESKTOP, 1.0, True)]


def _window(qapp: QApplication) -> tuple[OverlayController, OverlayWindow]:
    controller = OverlayController(frozen=FakeBackend().grab(DESKTOP), monitors=MONITORS)
    windows = controller.build_windows()
    assert windows
    return controller, windows[0]


def test_the_dim_bands_never_cover_the_selection(qapp: QApplication) -> None:
    controller, window = _window(qapp)
    try:
        selection = QRect(100, 80, 240, 160)

        for band in window.surrounding_bands(selection):
            assert not band.intersects(selection), band
    finally:
        controller.close()


def test_the_dim_bands_cover_everything_outside_the_selection(qapp: QApplication) -> None:
    # The complement matters as much as the overlap: a gap is an undimmed strip that reads
    # as part of the selection.
    controller, window = _window(qapp)
    try:
        full = window.rect()
        selection = QRect(100, 80, 240, 160)

        covered = QRect()
        for band in window.surrounding_bands(selection):
            covered = covered.united(band) if not covered.isNull() else band

        assert covered.united(selection) == full
    finally:
        controller.close()


def test_a_selection_flush_against_an_edge_produces_no_negative_band(
    qapp: QApplication,
) -> None:
    controller, window = _window(qapp)
    try:
        full = window.rect()
        selection = QRect(0, 0, full.width(), full.height())

        for band in window.surrounding_bands(selection):
            assert band.width() >= 0
            assert band.height() >= 0
            assert band.isEmpty()
    finally:
        controller.close()
