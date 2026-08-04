"""Tool glyphs and the brand mark.

Rendering needs a QApplication but no display; ``conftest`` runs the suite with the
offscreen platform.
"""

from __future__ import annotations

import pytest

from snipline.editor.tools.registry import TOOLS, tool_names
from snipline.ui import icons, mark


class TestGlyphCoverage:
    def test_every_registered_tool_has_a_glyph(self) -> None:
        # The reason this file exists. Adding a tool to the registry is meant to be the only
        # step needed to put it in the toolbar, which means a tool can reach the UI with no
        # artwork and nothing but a blank button to say so.
        missing = [name for name in tool_names() if not icons.has_glyph(name)]
        assert missing == [], f"tools without a glyph: {missing}"

    def test_no_glyph_is_drawn_for_a_tool_that_does_not_exist(self) -> None:
        orphans = set(icons.GLYPH_NAMES) - set(tool_names())
        assert orphans == set(), f"glyphs for unknown tools: {sorted(orphans)}"

    def test_registry_and_glyphs_are_the_same_size(self) -> None:
        assert len(icons.GLYPH_NAMES) == len(TOOLS)


class TestGlyphRendering:
    @pytest.mark.parametrize("name", icons.GLYPH_NAMES)
    def test_glyph_renders_something_visible(self, name: str) -> None:
        pixmap = icons.glyph_pixmap(name, 32)
        assert not pixmap.isNull()
        assert pixmap.size().width() == 32

        image = pixmap.toImage()
        painted = any(
            image.pixelColor(x, y).alpha() > 0
            for x in range(image.width())
            for y in range(image.height())
        )
        # A glyph that silently draws nothing still produces a valid transparent pixmap, so
        # asserting on the pixmap alone would pass for an empty drawing function.
        assert painted, f"{name} drew nothing"

    @pytest.mark.parametrize("size", [16, 64])
    def test_glyphs_render_at_the_sizes_the_toolbar_asks_for(self, size: int) -> None:
        assert icons.glyph_pixmap("arrow", size).width() == size

    def test_unknown_tool_is_an_error_rather_than_a_blank(self) -> None:
        with pytest.raises(KeyError):
            icons.glyph_pixmap("no-such-tool", 16)

    def test_tool_icon_carries_a_distinct_selected_appearance(self) -> None:
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QIcon

        icon = icons.tool_icon("arrow")
        size = QSize(32, 32)
        off = icon.pixmap(size, QIcon.Mode.Normal, QIcon.State.Off).toImage()
        on = icon.pixmap(size, QIcon.Mode.Normal, QIcon.State.On).toImage()
        assert off != on, "checked and unchecked tools render identically"


class TestMark:
    @pytest.mark.parametrize("size", [16, 32, 256])
    def test_mark_renders_at_every_size(self, size: int) -> None:
        assert not mark.mark_pixmap(size).isNull()
        assert mark.app_tile_pixmap(size).width() == size

    def test_tray_mark_leaves_its_corners_transparent(self) -> None:
        # The tray glyph must not be a filled tile: it sits directly on the taskbar, and a
        # square of background there reads as a button.
        image = mark.mark_pixmap(64).toImage()
        assert image.pixelColor(0, 0).alpha() == 0

    def test_app_tile_is_opaque_at_its_centre(self) -> None:
        image = mark.app_tile_pixmap(64).toImage()
        assert image.pixelColor(32, 32).alpha() > 0

    def test_icons_offer_every_declared_size(self) -> None:
        available = {size.width() for size in mark.app_icon().availableSizes()}
        assert set(mark.ICON_SIZES).issubset(available)
