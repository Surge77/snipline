from __future__ import annotations

import pytest

from snipline.config import ExportFormat, RedactionStyle, Settings


class TestRedactionStyle:
    def test_solid_and_pixelate_are_redaction(self) -> None:
        assert RedactionStyle.SOLID.is_redaction
        assert RedactionStyle.PIXELATE.is_redaction

    def test_blur_is_not_redaction(self) -> None:
        # Blurred text is frequently recoverable, so blur must never be treated as a
        # privacy guarantee anywhere in the codebase. See D7.
        assert not RedactionStyle.BLUR.is_redaction

    def test_the_default_redaction_style_is_a_real_redaction(self) -> None:
        assert Settings().redaction_style.is_redaction


class TestExportFormat:
    def test_jpeg_does_not_support_alpha(self) -> None:
        assert not ExportFormat.JPEG.supports_alpha

    def test_png_and_webp_support_alpha(self) -> None:
        assert ExportFormat.PNG.supports_alpha
        assert ExportFormat.WEBP.supports_alpha


class TestSettings:
    def test_defaults_are_usable(self) -> None:
        settings = Settings()
        assert settings.hotkey
        assert settings.export_format is ExportFormat.PNG

    @pytest.mark.parametrize("quality", [0, 101, -5])
    def test_rejects_out_of_range_jpeg_quality(self, quality: int) -> None:
        with pytest.raises(ValueError, match="jpeg quality"):
            Settings(jpeg_quality=quality)
