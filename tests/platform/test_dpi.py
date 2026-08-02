from __future__ import annotations

import pytest

from snipline.platform.dpi import dpi_from_scale, scale_from_dpi


class TestScaleConversion:
    @pytest.mark.parametrize(
        ("dpi", "scale"),
        [(96, 1.0), (120, 1.25), (144, 1.5), (168, 1.75), (192, 2.0)],
    )
    def test_converts_the_standard_windows_scaling_steps(self, dpi: int, scale: float) -> None:
        assert scale_from_dpi(dpi) == scale
        assert dpi_from_scale(scale) == dpi

    def test_rejects_non_positive_dpi(self) -> None:
        with pytest.raises(ValueError, match="non-positive DPI"):
            scale_from_dpi(0)

    def test_rejects_non_positive_scale(self) -> None:
        with pytest.raises(ValueError, match="non-positive scale"):
            dpi_from_scale(-1.0)
