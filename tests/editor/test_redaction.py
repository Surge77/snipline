"""Redaction (D7).

The assertions that matter here are about information destruction, not appearance:

- a redacted region must not still contain the pixels it covered;
- dragging a redaction must re-process what it now covers, rather than carrying the
  originally sampled pixels along with it -- which would paint old content over new and
  reveal exactly what the user meant to hide;
- blur must never claim to be redaction.
"""

from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QApplication

from snipline.capture.fake_backend import FakeBackend
from snipline.editor.scene import AnnotationScene, EditorController
from snipline.editor.tools.redaction import (
    BlurItem,
    BlurTool,
    PixelateItem,
    PixelateTool,
    SolidFillItem,
    SolidFillTool,
)
from snipline.platform.geometry import PhysicalRect

CAPTURE = PhysicalRect(0, 0, 200, 160)
REGION = QRectF(20, 20, 80, 60)


def _scene() -> AnnotationScene:
    return AnnotationScene(FakeBackend().grab(CAPTURE))


def _draw(controller: EditorController, x1: int, y1: int, x2: int, y2: int) -> object:
    controller.press(QPointF(x1, y1))
    controller.move(QPointF(x2, y2))
    return controller.release(QPointF(x2, y2))


def _distinct_colours(image: QImage, rect: QRectF) -> int:
    return len(
        {
            image.pixel(x, y)
            for x in range(int(rect.left()), int(rect.right()), 2)
            for y in range(int(rect.top()), int(rect.bottom()), 2)
        }
    )


def test_solid_fill_leaves_no_detail(qapp: QApplication) -> None:
    scene = _scene()
    controller = EditorController(scene=scene, tool=SolidFillTool())
    _draw(controller, 20, 20, 100, 80)

    flattened = scene.flatten()

    assert _distinct_colours(flattened, REGION) == 1


def test_pixelate_destroys_detail(qapp: QApplication) -> None:
    scene = _scene()
    before = _distinct_colours(scene.flatten(), REGION)
    controller = EditorController(scene=scene, tool=PixelateTool())
    _draw(controller, 20, 20, 100, 80)

    after = _distinct_colours(scene.flatten(), REGION)

    assert after < before / 4


def _mean_colour(image: QImage, rect: QRectF) -> tuple[float, float, float]:
    samples = [
        QColor(image.pixel(x, y))
        for x in range(int(rect.left()), int(rect.right()), 2)
        for y in range(int(rect.top()), int(rect.bottom()), 2)
    ]
    count = len(samples)
    return (
        sum(c.red() for c in samples) / count,
        sum(c.green() for c in samples) / count,
        sum(c.blue() for c in samples) / count,
    )


def _distance(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum(abs(x - y) for x, y in zip(a, b, strict=True))


def test_a_dragged_redaction_reprocesses_its_new_area(qapp: QApplication) -> None:
    # The bug this guards against: an item that sampled once at creation carries those
    # pixels with it, painting the *original* content wherever it is dragged. That is a
    # redaction which actively reveals what it was meant to hide.
    #
    # Asserted on mean colour rather than colour count, because stale pixels are also
    # low-detail and would pass a count-based check. Pixelation preserves local average, so
    # a correctly re-sampled block matches the capture underneath it and a stale one still
    # matches where it came from. FakeBackend's gradient makes those two clearly different.
    scene = _scene()
    controller = EditorController(scene=scene, tool=PixelateTool())
    item = _draw(controller, 0, 0, 60, 40)
    assert isinstance(item, PixelateItem)

    origin = QRectF(2, 2, 56, 36)
    destination = QRectF(122, 102, 56, 36)
    clean = AnnotationScene(FakeBackend().grab(CAPTURE)).flatten()

    # Render once before moving. The user always sees the redaction where they drew it
    # before dragging it, and an implementation that samples lazily-but-once would
    # otherwise be indistinguishable from one that re-samples.
    scene.flatten()

    item.setPos(QPointF(120, 100))
    redacted = _mean_colour(scene.flatten(), destination)

    assert _distance(redacted, _mean_colour(clean, destination)) < 30  # matches where it is
    assert _distance(redacted, _mean_colour(clean, origin)) > 60  # not where it came from


def test_the_area_a_redaction_left_is_the_original_capture_again(
    qapp: QApplication,
) -> None:
    scene = _scene()
    controller = EditorController(scene=scene, tool=SolidFillTool())
    item = _draw(controller, 0, 0, 60, 40)
    assert isinstance(item, SolidFillItem)

    item.setPos(QPointF(120, 100))
    flattened = scene.flatten()

    clean = AnnotationScene(FakeBackend().grab(CAPTURE)).flatten()
    vacated = QRectF(2, 2, 50, 30)
    assert _distinct_colours(flattened, vacated) == _distinct_colours(clean, vacated)


def test_blur_is_not_labelled_or_treated_as_redaction(qapp: QApplication) -> None:
    # D7. Blurred text is frequently recoverable, so this must never claim otherwise.
    assert not BlurItem(REGION).is_redaction
    assert SolidFillItem(REGION).is_redaction
    assert PixelateItem(REGION).is_redaction
    assert "not redaction" in BlurTool.label.lower()


def test_blur_still_alters_the_image(qapp: QApplication) -> None:
    scene = _scene()
    before = _distinct_colours(scene.flatten(), REGION)
    controller = EditorController(scene=scene, tool=BlurTool())
    _draw(controller, 20, 20, 100, 80)

    assert _distinct_colours(scene.flatten(), REGION) < before


def test_a_redaction_with_no_background_still_paints_opaque(qapp: QApplication) -> None:
    # An item not in a scene has nothing to sample. Painting nothing would leave the region
    # readable, so it falls back to a fill.
    item = PixelateItem(QRectF(0, 0, 40, 30))
    image = QImage(40, 30, QImage.Format.Format_RGB32)
    image.fill(QColor("#FFFFFF"))

    painter = QPainter(image)
    item.paint(painter, None)  # type: ignore[arg-type]
    painter.end()

    assert image.pixelColor(20, 15) != QColor("#FFFFFF")


def test_a_zero_area_redaction_is_rejected(qapp: QApplication) -> None:
    controller = EditorController(scene=_scene(), tool=SolidFillTool())

    controller.press(QPointF(50, 50))
    committed = controller.release(QPointF(50, 50))

    assert committed is None
    assert controller.scene.items() == []


def test_redactions_are_undoable_like_any_annotation(qapp: QApplication) -> None:
    scene = _scene()
    controller = EditorController(scene=scene, tool=SolidFillTool())
    clean = scene.flatten()

    _draw(controller, 20, 20, 100, 80)
    controller.undo_stack.undo()

    assert scene.flatten() == clean
