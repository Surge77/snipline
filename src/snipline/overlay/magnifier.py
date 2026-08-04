"""The magnifier loupe.

``config.show_magnifier`` has existed since M6 and was persisted by the settings store, but
nothing ever drew one -- the setting toggled nothing. This is that feature.

Sampling is nearest-neighbour, deliberately. A smoothed magnifier is a picture of what the
pixels nearly are; this application's claim is that the region selected is the region
captured, and the loupe exists so a user can put an edge on the right pixel. Interpolating
here would be the same category of lie as dimming the selected area.

The frozen pixmap is converted to a QImage once, at construction. ``QPixmap::toImage`` is a
copy off the graphics backend, and doing it per mouse-move to read one pixel's colour is a
full-screen copy on every event of a drag.
"""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap

from snipline.ui import theme

__all__ = ["Magnifier", "loupe_origin"]

LOUPE_SIZE = 132
ZOOM = 8
_CURSOR_OFFSET = 22
_READOUT_HEIGHT = 22
_RADIUS = 10.0

_BORDER = QColor(255, 255, 255, 38)
_BACKGROUND = QColor(11, 14, 20, 240)
_CROSSHAIR = QColor(theme.ACCENT)
_CROSSHAIR_WIDTH = 1.2
_GRID = QColor(255, 255, 255, 20)

# Below this the grid lines outnumber the pixels they separate and it reads as mesh.
_MIN_ZOOM_FOR_GRID = 6


def loupe_origin(cursor: QPoint, bounds: QRect, width: int, height: int) -> QPointF:
    """Top-left of the loupe, flipped to whichever side of the cursor has room.

    Pure geometry so the flipping is assertable. A loupe that ran off the screen edge would
    be useless exactly when the user is selecting up to that edge, which is the case it is
    most needed for.
    """
    x = cursor.x() + _CURSOR_OFFSET
    y = cursor.y() + _CURSOR_OFFSET
    if x + width > bounds.right():
        x = cursor.x() - _CURSOR_OFFSET - width
    if y + height > bounds.bottom():
        y = cursor.y() - _CURSOR_OFFSET - height
    # Clamp for the corner case where neither side fits: a small screen, or a loupe larger
    # than the space beside the cursor.
    x = max(float(bounds.left()), min(float(x), float(bounds.right() - width)))
    y = max(float(bounds.top()), min(float(y), float(bounds.bottom() - height)))
    return QPointF(x, y)


class Magnifier:
    """Draws a zoomed view of the frozen capture around the pointer."""

    def __init__(self, frozen: QPixmap) -> None:
        self._frozen = frozen
        self._image: QImage | None = None

    @property
    def image(self) -> QImage:
        """The frozen pixmap as an image, converted once and reused."""
        if self._image is None:
            self._image = self._frozen.toImage()
        return self._image

    def colour_at(self, source: QPoint) -> QColor | None:
        image = self.image
        if not image.rect().contains(source):
            return None
        return QColor(image.pixelColor(source))

    def paint(self, painter: QPainter, cursor: QPoint, bounds: QRect, ratio: float) -> None:
        """Draw the loupe near ``cursor``.

        ``ratio`` converts widget-local coordinates to frozen-pixmap coordinates; they
        differ whenever the screen's device pixel ratio is not 1, which is the normal case
        on the mixed-DPI desktops this project exists for.
        """
        source_point = QPoint(round(cursor.x() * ratio), round(cursor.y() * ratio))
        colour = self.colour_at(source_point)
        if colour is None:
            return

        total_height = LOUPE_SIZE + _READOUT_HEIGHT
        origin = loupe_origin(cursor, bounds, LOUPE_SIZE, total_height)
        frame = QRectF(origin.x(), origin.y(), LOUPE_SIZE, total_height)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setBrush(_BACKGROUND)
        painter.setPen(QPen(_BORDER, 1.0))
        painter.drawRoundedRect(frame, _RADIUS, _RADIUS)

        view = QRectF(origin.x(), origin.y(), LOUPE_SIZE, LOUPE_SIZE)
        painter.save()
        painter.setClipRect(view)
        self._paint_zoom(painter, view, source_point)
        self._paint_grid(painter, view)
        self._paint_crosshair(painter, view)
        painter.restore()

        self._paint_readout(painter, frame, source_point, colour)
        painter.restore()

    def _paint_zoom(self, painter: QPainter, view: QRectF, source: QPoint) -> None:
        span = LOUPE_SIZE / ZOOM
        source_rect = QRectF(
            source.x() - span / 2.0, source.y() - span / 2.0, span, span
        )
        # Off, so each source pixel lands as a hard square. This is the whole point.
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.drawPixmap(view, self._frozen, source_rect)

    def _paint_grid(self, painter: QPainter, view: QRectF) -> None:
        if ZOOM < _MIN_ZOOM_FOR_GRID:
            return
        painter.setPen(QPen(_GRID, 1.0))
        steps = int(LOUPE_SIZE / ZOOM)
        for index in range(1, steps + 1):
            offset = index * ZOOM
            painter.drawLine(
                QPointF(view.left() + offset, view.top()),
                QPointF(view.left() + offset, view.bottom()),
            )
            painter.drawLine(
                QPointF(view.left(), view.top() + offset),
                QPointF(view.right(), view.top() + offset),
            )

    def _paint_crosshair(self, painter: QPainter, view: QRectF) -> None:
        centre = view.center()
        # One zoomed pixel, outlined rather than filled: the pixel under the pointer has to
        # stay visible, since its colour is the thing being read.
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(_CROSSHAIR, _CROSSHAIR_WIDTH))
        painter.drawRect(
            QRectF(centre.x() - ZOOM / 2.0, centre.y() - ZOOM / 2.0, ZOOM, ZOOM)
        )

    def _paint_readout(
        self, painter: QPainter, frame: QRectF, source: QPoint, colour: QColor
    ) -> None:
        strip = QRectF(
            frame.left(), frame.bottom() - _READOUT_HEIGHT, frame.width(), _READOUT_HEIGHT
        )
        swatch = QRectF(strip.left() + 8, strip.center().y() - 5, 10, 10)
        painter.setBrush(colour)
        painter.setPen(QPen(_BORDER, 1.0))
        painter.drawRoundedRect(swatch, 2.0, 2.0)

        font = QFont(painter.font())
        font.setPointSizeF(8.5)
        painter.setFont(font)
        painter.setPen(QColor(theme.TEXT_MUTED))
        text = f"{source.x()}, {source.y()}   {colour.name().upper()}"
        painter.drawText(
            strip.adjusted(24, 0, -8, 0),
            int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft),
            text,
        )
