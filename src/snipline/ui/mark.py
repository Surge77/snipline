"""The Snipline mark.

Four corner brackets around an open centre -- a selection frame, which is the one gesture
the whole application is about. Kept from the original tray glyph because the shape was
already right; what changed is that it is now drawn once here and reused by the tray, the
window icon, and the ``.ico`` generator, instead of existing only inside ``tray.py``.

Everything is drawn from geometry rather than loaded from a file. A missing icon resource is
a classic PyInstaller failure -- it works in development and breaks in the bundle -- and a
shape this simple does not need to take that risk. ``tools/make_icons.py`` renders this same
code to a ``.ico`` at *build* time, which PyInstaller embeds into the executable; nothing
reads that file while the application is running.

Proportions are fractions of the canvas, not pixel constants, so the mark is drawn at its
real size rather than scaled up from a 64px bitmap. That is what keeps the 16px tray icon
from looking like a blurred version of the 256px one.
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import (
    QColor,
    QIcon,
    QLinearGradient,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)

from snipline.ui import theme

__all__ = ["app_icon", "app_tile_pixmap", "draw_mark", "mark_pixmap", "tray_icon"]

# Fractions of the canvas edge.
_INSET = 0.20  # bracket corner distance from the edge
_ARM = 0.20  # bracket arm length
_STROKE = 0.085  # pen width
_TILE_RADIUS = 0.22  # app tile corner rounding
_TILE_INSET = 0.03  # keeps the tile's antialiased edge inside the canvas

# Windows asks for whichever of these fits the surface it is drawing: 16 in the tray, 32 in
# the taskbar, 256 in Explorer's extra-large view. Supplying each one rendered at its own
# size is the difference between a crisp icon and a resampled one.
ICON_SIZES = (16, 20, 24, 32, 48, 64, 128, 256)

_TILE_TOP = "#1E293B"
_TILE_BOTTOM = "#0B0E14"
_TILE_HIGHLIGHT_ALPHA = 0.10


def draw_mark(
    painter: QPainter, rect: QRectF, colour: str = theme.ACCENT, stroke: float | None = None
) -> None:
    """Paint the four brackets inside ``rect``.

    Round caps and joins, which is most of why this reads as a designed mark rather than as
    eight line segments: a butt cap leaves a visible square nub at every one of the eight
    free ends.
    """
    edge = min(rect.width(), rect.height())
    width = stroke if stroke is not None else edge * _STROKE

    pen = QPen(QColor(colour), width)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)

    inset = edge * _INSET
    arm = edge * _ARM
    near_x, far_x = rect.left() + inset, rect.right() - inset
    near_y, far_y = rect.top() + inset, rect.bottom() - inset

    # One path for all four brackets: a single stroke pass joins each corner's two arms
    # instead of butting two independent lines together at a right angle.
    path = QPainterPath()
    for x, x_step in ((near_x, 1.0), (far_x, -1.0)):
        for y, y_step in ((near_y, 1.0), (far_y, -1.0)):
            path.moveTo(x + arm * x_step, y)
            path.lineTo(x, y)
            path.lineTo(x, y + arm * y_step)
    painter.drawPath(path)


def _canvas(size: int) -> QPixmap:
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))
    return pixmap


def mark_pixmap(size: int, colour: str = theme.ACCENT) -> QPixmap:
    """The brackets alone on transparency, for the tray.

    No tile: a tray icon sits directly on the taskbar, and a filled square there reads as a
    button rather than as a glyph. The accent blue is legible against both the light and the
    dark Windows taskbar, which a white or a dark mark would not be.
    """
    pixmap = _canvas(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    # Below roughly 20px the proportional stroke lands under a pixel and the mark greys out
    # into a smudge, so it is floored rather than allowed to vanish.
    stroke = max(size * _STROKE, 1.5)
    draw_mark(painter, QRectF(0, 0, size, size), colour, stroke)
    painter.end()
    return pixmap


def app_tile_pixmap(size: int) -> QPixmap:
    """The rounded-tile application icon: gradient ground, brackets, top highlight."""
    pixmap = _canvas(size)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)

    inset = size * _TILE_INSET
    tile = QRectF(inset, inset, size - inset * 2, size - inset * 2)
    radius = size * _TILE_RADIUS

    gradient = QLinearGradient(tile.left(), tile.top(), tile.left(), tile.bottom())
    gradient.setColorAt(0.0, QColor(_TILE_TOP))
    gradient.setColorAt(1.0, QColor(_TILE_BOTTOM))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(gradient)
    painter.drawRoundedRect(tile, radius, radius)

    # A hairline along the top edge only. Light falls from above, so an inner highlight that
    # runs the whole way round reads as a sticker; one that fades out by the midpoint reads
    # as a lit surface.
    highlight = QColor(255, 255, 255)
    highlight.setAlphaF(_TILE_HIGHLIGHT_ALPHA)
    fade = QLinearGradient(tile.left(), tile.top(), tile.left(), tile.center().y())
    fade.setColorAt(0.0, highlight)
    fade.setColorAt(1.0, QColor(255, 255, 255, 0))
    stroke = max(size / 64.0, 1.0)
    pen = QPen(fade, stroke)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawRoundedRect(tile.adjusted(stroke / 2, stroke / 2, -stroke / 2, -stroke / 2),
                            radius, radius)

    draw_mark(painter, QRectF(0, 0, size, size))
    painter.end()
    return pixmap


def _icon_from(render: Callable[[int], QPixmap], sizes: tuple[int, ...]) -> QIcon:
    icon = QIcon()
    for size in sizes:
        icon.addPixmap(render(size))
    return icon


def tray_icon() -> QIcon:
    """Tray and notification icon, rendered at each size Windows asks for."""
    return _icon_from(mark_pixmap, (16, 20, 24, 32, 48))


def app_icon() -> QIcon:
    """Window and taskbar icon."""
    return _icon_from(app_tile_pixmap, ICON_SIZES)
