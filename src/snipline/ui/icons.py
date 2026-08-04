"""Tool glyphs.

One drawing function per tool, keyed by the same name the registry uses. Drawn rather than
loaded, for the reason given in ``mark.py``.

Every glyph is described in fractions of a unit square and scaled to whatever canvas is
asked for, so the 16px and the 64px renders are the same drawing rather than the same
bitmap at two sizes.

The toolbar shows icons *and* text labels. Icon-only toolbars are the norm in this category
and they are a guessing game for anyone who has not memorised the set; "Redact (pixelate)"
and "Blur (cosmetic)" in particular are a distinction this application refuses to leave to a
glyph (D7).
"""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from snipline.ui import theme

__all__ = ["GLYPH_NAMES", "glyph_pixmap", "has_glyph", "tool_icon"]

_STROKE = 0.085
_RENDER_SIZES = (16, 20, 24, 32, 48, 64)

Glyph = Callable[[QPainter, float], None]


def _stroke_pen(painter: QPainter, size: float, colour: str, scale: float = 1.0) -> QPen:
    pen = QPen(QColor(colour), size * _STROKE * scale)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    return pen


def _fill(painter: QPainter, colour: str) -> None:
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QColor(colour))


def _rect(size: float, left: float, top: float, right: float, bottom: float) -> QRectF:
    return QRectF(left * size, top * size, (right - left) * size, (bottom - top) * size)


def _arrow(painter: QPainter, size: float) -> None:
    tail, tip = QPointF(0.20 * size, 0.80 * size), QPointF(0.78 * size, 0.22 * size)
    painter.drawLine(tail, tip)
    head = QPainterPath()
    head.moveTo(0.78 * size, 0.46 * size)
    head.lineTo(tip)
    head.lineTo(0.54 * size, 0.22 * size)
    painter.drawPath(head)


def _select(painter: QPainter, size: float) -> None:
    # A pointer, filled: the select tool moves existing annotations rather than drawing, and
    # an outlined glyph in a row of outlined glyphs would not say that.
    colour = painter.pen().color().name()
    points = (
        (0.30, 0.16),
        (0.30, 0.78),
        (0.44, 0.64),
        (0.54, 0.86),
        (0.66, 0.80),
        (0.55, 0.60),
        (0.74, 0.57),
    )
    path = QPainterPath(QPointF(points[0][0] * size, points[0][1] * size))
    for x, y in points[1:]:
        path.lineTo(QPointF(x * size, y * size))
    path.closeSubpath()
    _fill(painter, colour)
    painter.drawPath(path)


def _rectangle(painter: QPainter, size: float) -> None:
    painter.drawRoundedRect(_rect(size, 0.16, 0.24, 0.84, 0.76), 0.07 * size, 0.07 * size)


def _ellipse(painter: QPainter, size: float) -> None:
    painter.drawEllipse(_rect(size, 0.15, 0.22, 0.85, 0.78))


def _freehand(painter: QPainter, size: float) -> None:
    path = QPainterPath(QPointF(0.16 * size, 0.66 * size))
    path.cubicTo(
        QPointF(0.30 * size, 0.18 * size),
        QPointF(0.44 * size, 0.92 * size),
        QPointF(0.58 * size, 0.52 * size),
    )
    path.cubicTo(
        QPointF(0.68 * size, 0.24 * size),
        QPointF(0.78 * size, 0.34 * size),
        QPointF(0.86 * size, 0.30 * size),
    )
    painter.drawPath(path)


def _text(painter: QPainter, size: float) -> None:
    painter.drawLine(QPointF(0.22 * size, 0.26 * size), QPointF(0.78 * size, 0.26 * size))
    painter.drawLine(QPointF(0.50 * size, 0.26 * size), QPointF(0.50 * size, 0.78 * size))


def _step(painter: QPainter, size: float) -> None:
    painter.drawEllipse(_rect(size, 0.16, 0.16, 0.84, 0.84))
    # A drawn numeral rather than drawText: font availability and hinting differ per machine,
    # and a glyph that reflows with the system font is not the same icon everywhere.
    painter.drawLine(QPointF(0.50 * size, 0.34 * size), QPointF(0.50 * size, 0.68 * size))
    painter.drawLine(QPointF(0.50 * size, 0.34 * size), QPointF(0.40 * size, 0.42 * size))


def _solid(painter: QPainter, size: float) -> None:
    colour = painter.pen().color().name()
    _fill(painter, colour)
    painter.drawRoundedRect(_rect(size, 0.16, 0.24, 0.84, 0.76), 0.07 * size, 0.07 * size)


def _pixelate(painter: QPainter, size: float) -> None:
    colour = painter.pen().color().name()
    _fill(painter, colour)
    cell = 0.68 * size / 3.0
    origin = 0.16 * size
    for row in range(3):
        for column in range(3):
            if (row + column) % 2:
                continue
            painter.drawRect(
                QRectF(origin + column * cell, origin + row * cell, cell * 0.86, cell * 0.86)
            )


def _blur(painter: QPainter, size: float) -> None:
    # Three strokes fading downward. Blur is the one tool here that is explicitly *not* a
    # privacy feature, and a glyph that dissolves rather than covers is the honest picture
    # of what it does.
    colour = QColor(painter.pen().color())
    for index, y in enumerate((0.32, 0.50, 0.68)):
        faded = QColor(colour)
        faded.setAlphaF(1.0 - index * 0.30)
        pen = QPen(faded, size * _STROKE)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        path = QPainterPath(QPointF(0.16 * size, y * size))
        path.cubicTo(
            QPointF(0.38 * size, (y - 0.10) * size),
            QPointF(0.62 * size, (y + 0.10) * size),
            QPointF(0.84 * size, y * size),
        )
        painter.drawPath(path)


_GLYPHS: dict[str, Glyph] = {
    "arrow": _arrow,
    "select": _select,
    "rectangle": _rectangle,
    "ellipse": _ellipse,
    "freehand": _freehand,
    "text": _text,
    "step": _step,
    "solid": _solid,
    "pixelate": _pixelate,
    "blur": _blur,
}

GLYPH_NAMES = tuple(_GLYPHS)


def has_glyph(name: str) -> bool:
    return name in _GLYPHS


def glyph_pixmap(name: str, size: int, colour: str = theme.TEXT_PRIMARY) -> QPixmap:
    """Render one glyph. Raises ``KeyError`` for an unknown tool."""
    draw = _GLYPHS[name]
    pixmap = QPixmap(size, size)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    _stroke_pen(painter, float(size), colour)
    draw(painter, float(size))
    painter.end()
    return pixmap


def tool_icon(name: str) -> QIcon:
    """A tool glyph in its resting and selected colours.

    ``State_On`` is what a checked QToolButton asks for, so the accent tint follows the
    exclusive tool selection without the toolbar having to repaint anything itself.
    """
    icon = QIcon()
    for size in _RENDER_SIZES:
        icon.addPixmap(glyph_pixmap(name, size, theme.TEXT_MUTED), QIcon.Mode.Normal,
                       QIcon.State.Off)
        icon.addPixmap(glyph_pixmap(name, size, theme.TEXT_PRIMARY), QIcon.Mode.Active,
                       QIcon.State.Off)
        icon.addPixmap(glyph_pixmap(name, size, theme.ACCENT_TEXT), QIcon.Mode.Normal,
                       QIcon.State.On)
        icon.addPixmap(glyph_pixmap(name, size, theme.ACCENT_TEXT), QIcon.Mode.Active,
                       QIcon.State.On)
    return icon
