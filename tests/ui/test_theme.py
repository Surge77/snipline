"""Design tokens. No QApplication: the point of the module is that it needs none."""

from __future__ import annotations

import pytest

from snipline.ui import theme


class TestRgba:
    def test_converts_hex_to_qt_rgba(self) -> None:
        assert theme.rgba("#3B82F6", 0.14) == "rgba(59, 130, 246, 0.14)"

    def test_accepts_a_colour_without_the_hash(self) -> None:
        assert theme.rgba("FFFFFF", 1.0) == "rgba(255, 255, 255, 1.0)"

    @pytest.mark.parametrize("colour", ["#FFF", "#FFFFFFFF", "", "#GGGGGG"])
    def test_rejects_anything_that_is_not_six_hex_digits(self, colour: str) -> None:
        with pytest.raises(ValueError):
            theme.rgba(colour, 1.0)

    @pytest.mark.parametrize("alpha", [-0.1, 1.1])
    def test_rejects_alpha_outside_zero_to_one(self, alpha: float) -> None:
        with pytest.raises(ValueError, match="alpha out of range"):
            theme.rgba("#000000", alpha)


class TestTokens:
    @pytest.mark.parametrize(
        "colour",
        [
            theme.SURFACE,
            theme.SURFACE_RAISED,
            theme.SURFACE_HOVER,
            theme.TEXT_PRIMARY,
            theme.TEXT_MUTED,
            theme.TEXT_DISABLED,
            theme.ACCENT,
            theme.ACCENT_TEXT,
            theme.ACCENT_PRESSED,
        ],
    )
    def test_solid_colours_are_six_digit_hex(self, colour: str) -> None:
        assert colour.startswith("#")
        assert len(colour) == 7
        int(colour[1:], 16)

    def test_surfaces_get_lighter_as_they_are_raised(self) -> None:
        # Guards the direction of the ramp. A hover state darker than the surface it sits on
        # reads as a hole rather than as a lift, and it is an easy thing to invert by hand.
        def luminance(colour: str) -> int:
            return sum(int(colour[i : i + 2], 16) for i in (1, 3, 5))

        assert luminance(theme.SURFACE) < luminance(theme.SURFACE_RAISED)
        assert luminance(theme.SURFACE_RAISED) < luminance(theme.SURFACE_HOVER)
