"""Redaction and the cosmetic blur (D7).

**Pixelate and solid fill are redaction. Blur is not**, and is labelled a cosmetic effect
everywhere it is offered. Blurred text is frequently recoverable -- render candidate strings,
apply the same blur, compare -- and a privacy feature that fails against a motivated reader
is worse than none, because people rely on it. Solid fill is the default for that reason.

The items sample the background **inside ``paint``** rather than once at creation. That is
what makes dragging a redaction re-process the area it now covers instead of smearing the
pixels it originally sampled over new content -- which would be a redaction that reveals
exactly what it is supposed to hide.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import (
    QGraphicsItem,
    QStyleOptionGraphicsItem,
    QWidget,
)

from snipline.editor.style import DEFAULT_STYLE, ToolStyle
from snipline.editor.tools.shapes import MIN_EXTENT_PX, rect_from_drag

__all__ = [
    "BlurTool",
    "PixelateItem",
    "PixelateTool",
    "RedactionItem",
    "SolidFillItem",
    "SolidFillTool",
]

# Blocks per redaction, not a fixed block size: a small region gets small blocks and stays
# unreadable, rather than becoming one flat square that hides where the text even was.
PIXELATE_BLOCKS = 12

# Deliberately coarse. A gentle blur looks like a redaction while recovering easily.
BLUR_DOWNSCALE = 0.08

SOLID_COLOUR = "#111827"


class RedactionItem(QGraphicsItem):
    """Base for items that replace the pixels beneath them."""

    def __init__(self, rect: QRectF) -> None:
        super().__init__()
        self._rect = rect
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

    @property
    def is_redaction(self) -> bool:
        """True for tools that actually destroy information. See D7."""
        return True

    def rect(self) -> QRectF:
        return self._rect

    def set_rect(self, rect: QRectF) -> None:
        self.prepareGeometryChange()
        self._rect = rect

    def boundingRect(self) -> QRectF:  # noqa: N802 - Qt override
        return self._rect

    def _background_patch(self) -> QImage | None:
        """The capture's pixels currently beneath this item, in scene coordinates.

        Read on every paint, so a dragged item processes where it is *now*.
        """
        scene = self.scene()
        source = getattr(scene, "background", None)
        if not isinstance(source, QPixmap) or source.isNull():
            return None

        covered = self.mapRectToScene(self._rect).toAlignedRect()
        patch = source.copy(covered)
        return patch.toImage() if not patch.isNull() else None

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionGraphicsItem,
        widget: QWidget | None = None,
    ) -> None:
        processed = self.process(self._background_patch())
        if processed is None:
            # No background to sample -- fall back to an opaque fill rather than painting
            # nothing, which would leave the region readable.
            painter.fillRect(self._rect, QColor(SOLID_COLOUR))
            return
        painter.drawImage(self._rect, processed)

    def process(self, patch: QImage | None) -> QImage | None:
        raise NotImplementedError


class SolidFillItem(RedactionItem):
    """Opaque fill. The strongest and default redaction: nothing survives it."""

    def process(self, patch: QImage | None) -> QImage | None:
        return None  # paint() fills instead, which is exactly the desired result


class PixelateItem(RedactionItem):
    """Downsample and upsample with nearest-neighbour, destroying detail."""

    def process(self, patch: QImage | None) -> QImage | None:
        if patch is None or patch.isNull():
            return None

        blocks = max(1, min(PIXELATE_BLOCKS, patch.width(), patch.height()))
        small = patch.scaled(
            max(1, patch.width() // blocks),
            max(1, patch.height() // blocks),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            # Fast, i.e. nearest neighbour. Smooth scaling here would average pixels and
            # leave recoverable structure behind.
            Qt.TransformationMode.FastTransformation,
        )
        return small.scaled(
            patch.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.FastTransformation,
        )


class BlurItem(RedactionItem):
    """Cosmetic softening. **Not** redaction -- see D7."""

    @property
    def is_redaction(self) -> bool:
        return False

    def process(self, patch: QImage | None) -> QImage | None:
        if patch is None or patch.isNull():
            return None

        small = patch.scaled(
            max(1, int(patch.width() * BLUR_DOWNSCALE)),
            max(1, int(patch.height() * BLUR_DOWNSCALE)),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        return small.scaled(
            patch.size(),
            Qt.AspectRatioMode.IgnoreAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )


class _RedactionTool:
    """Drag a box; the item replaces whatever is under it."""

    name = "redaction"
    label = "Redact"
    item_type: type[RedactionItem] = SolidFillItem

    def __init__(self, style: ToolStyle = DEFAULT_STYLE) -> None:
        self._style = style
        self._item: RedactionItem | None = None
        self._start = QPointF()

    @property
    def style(self) -> ToolStyle:
        return self._style

    def press(self, position: QPointF) -> QGraphicsItem | None:
        self._start = position
        self._item = self.item_type(QRectF(position, position))
        return self._item

    def move(self, position: QPointF) -> None:
        if self._item is not None:
            self._item.set_rect(rect_from_drag(self._start, position))

    def release(self, position: QPointF) -> QGraphicsItem | None:
        item = self._item
        self._item = None
        if item is None:
            return None

        rect = rect_from_drag(self._start, position)
        item.set_rect(rect)
        # A zero-area redaction hides nothing but looks, in the layer list, like something
        # was hidden.
        if rect.width() < MIN_EXTENT_PX or rect.height() < MIN_EXTENT_PX:
            return None
        return item


class SolidFillTool(_RedactionTool):
    name = "solid"
    label = "Redact (solid)"
    item_type = SolidFillItem


class PixelateTool(_RedactionTool):
    name = "pixelate"
    label = "Redact (pixelate)"
    item_type = PixelateItem


class BlurTool(_RedactionTool):
    name = "blur"
    # Named as an effect, never as redaction. See D7.
    label = "Blur (cosmetic, not redaction)"
    item_type = BlurItem
