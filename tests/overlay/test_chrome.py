"""Selection chrome geometry.

The handles and the loupe are only otherwise observable by looking at a screen, and the
development machine has one screen in one configuration. These assert the placement rules
directly instead.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QPoint, QRect, QRectF
from PySide6.QtGui import QPainter, QPixmap
from PySide6.QtWidgets import QApplication

from snipline.overlay import chrome
from snipline.overlay.magnifier import loupe_origin


class TestHandles:
    def test_a_normal_selection_gets_eight_grips(self) -> None:
        assert len(chrome.handle_rects(QRect(100, 100, 400, 300))) == 8

    @pytest.mark.parametrize("size", [4, 12, chrome.HANDLE_SIZE])
    def test_a_tiny_selection_gets_none(self, size: int) -> None:
        # Eight grips around a 12px selection is more chrome than selection.
        assert chrome.handle_rects(QRect(0, 0, size, size)) == []

    def test_no_handle_covers_a_selected_pixel(self) -> None:
        """The load-bearing assertion in this file.

        Chrome drawn over the selection hides the pixels the user is aligning against,
        which this project treats as a lie about what is being captured. A handle that
        creeps inward by a pixel is invisible in review and obvious only to whoever later
        wonders why their edge is off by one.
        """
        selection = QRect(200, 150, 300, 200)
        # right()/bottom() are the last contained pixel, so the area actually selected runs
        # one further than QRectF(selection) would cover.
        selected = QRectF(
            selection.left(), selection.top(), selection.width(), selection.height()
        )
        for handle in chrome.handle_rects(selection):
            assert not handle.intersects(selected), (
                f"handle {handle} overlaps the selection {selected}"
            )

    def test_handles_hug_the_selection(self) -> None:
        selection = QRect(100, 100, 200, 200)
        handles = chrome.handle_rects(selection)
        gaps = {
            round(selection.left() - handle.right())
            for handle in handles
            if handle.right() < selection.left()
        }
        assert gaps == {chrome.HANDLE_GAP}

    def test_placement_follows_the_selection(self) -> None:
        first = chrome.handle_rects(QRect(0, 0, 200, 200))
        second = chrome.handle_rects(QRect(500, 400, 200, 200))
        assert first[0].topLeft() != second[0].topLeft()


class TestHintPlacement:
    """Regression guard.

    The hint was centred on the screen and the loupe is drawn at the pointer, which on a
    freshly opened overlay is usually near the middle. The loupe won, and the instruction
    read "c to cancel".
    """

    BOUNDS = QRect(0, 0, 1920, 1080)

    def _painter(self) -> tuple[QPainter, QPixmap]:
        surface = QPixmap(self.BOUNDS.width(), self.BOUNDS.height())
        return QPainter(surface), surface

    def test_sits_in_the_lower_part_of_the_screen(self, qapp: QApplication) -> None:
        painter, _surface = self._painter()
        rect = chrome.hint_rect(painter, self.BOUNDS)
        painter.end()
        assert rect.top() > self.BOUNDS.center().y()

    def test_stays_on_screen(self, qapp: QApplication) -> None:
        painter, _surface = self._painter()
        rect = chrome.hint_rect(painter, self.BOUNDS)
        painter.end()
        assert rect.bottom() <= self.BOUNDS.bottom()
        assert rect.left() >= self.BOUNDS.left()

    def test_clears_a_loupe_drawn_at_the_centre(self, qapp: QApplication) -> None:
        painter, _surface = self._painter()
        rect = chrome.hint_rect(painter, self.BOUNDS)
        painter.end()

        centre = QPoint(self.BOUNDS.center().x(), self.BOUNDS.center().y())
        loupe_size = 132 + 22
        origin = loupe_origin(centre, self.BOUNDS, loupe_size, loupe_size)
        loupe = QRectF(origin.x(), origin.y(), loupe_size, loupe_size)
        assert not rect.intersects(loupe)


class TestLoupePlacement:
    BOUNDS = QRect(0, 0, 1920, 1080)
    SIZE = 132

    def test_sits_below_right_of_the_pointer_by_default(self) -> None:
        origin = loupe_origin(QPoint(400, 400), self.BOUNDS, self.SIZE, self.SIZE)
        assert origin.x() > 400
        assert origin.y() > 400

    def test_flips_away_from_the_right_edge(self) -> None:
        origin = loupe_origin(QPoint(1900, 400), self.BOUNDS, self.SIZE, self.SIZE)
        assert origin.x() + self.SIZE <= self.BOUNDS.right()

    def test_flips_away_from_the_bottom_edge(self) -> None:
        origin = loupe_origin(QPoint(400, 1070), self.BOUNDS, self.SIZE, self.SIZE)
        assert origin.y() + self.SIZE <= self.BOUNDS.bottom()

    def test_stays_on_screen_in_the_bottom_right_corner(self) -> None:
        # The corner is the case that needs both flips at once, and it is the corner a user
        # selects toward most often.
        origin = loupe_origin(QPoint(1919, 1079), self.BOUNDS, self.SIZE, self.SIZE)
        assert origin.x() >= self.BOUNDS.left()
        assert origin.y() >= self.BOUNDS.top()
        assert origin.x() + self.SIZE <= self.BOUNDS.right()
        assert origin.y() + self.SIZE <= self.BOUNDS.bottom()

    def test_clamps_when_the_loupe_barely_fits(self) -> None:
        tiny = QRect(0, 0, 200, 200)
        origin = loupe_origin(QPoint(100, 100), tiny, self.SIZE, self.SIZE)
        assert origin.x() >= tiny.left()
        assert origin.y() >= tiny.top()
