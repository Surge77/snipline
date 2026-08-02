"""A captured region of the desktop."""

from __future__ import annotations

from dataclasses import dataclass

from snipline.platform.geometry import PhysicalRect

BYTES_PER_PIXEL = 4  # BGRA


@dataclass(frozen=True, slots=True)
class Frame:
    """Raw BGRA pixels plus the physical rect they were captured from.

    Carrying the source rect matters because the virtual desktop origin is usually not
    (0, 0). A caller cropping a selection out of a full-desktop frame needs to rebase the
    selection's absolute coordinates against this rect, and making the frame own that
    information stops every call site from re-deriving it (and getting it wrong on the
    monitors with negative coordinates).

    ``pixels`` is the buffer as returned by the capture backend. It is not copied. When it
    originates from mss it is a view over memory owned by the backend, so a reference must
    be kept alive for as long as any QImage wraps it -- Qt will happily read freed memory.
    """

    rect: PhysicalRect
    pixels: bytes

    def __post_init__(self) -> None:
        expected = self.rect.width * self.rect.height * BYTES_PER_PIXEL
        if len(self.pixels) != expected:
            raise ValueError(
                f"buffer is {len(self.pixels)} bytes, expected {expected} "
                f"for {self.rect.width}x{self.rect.height} BGRA"
            )

    @property
    def width(self) -> int:
        return self.rect.width

    @property
    def height(self) -> int:
        return self.rect.height

    def crop(self, region: PhysicalRect) -> Frame:
        """Extract a sub-region, given in absolute virtual-desktop coordinates.

        The region is clamped to this frame first, so a selection dragged past the edge of
        the desktop yields the visible part rather than an out-of-bounds read.
        """
        clamped = region.intersection(self.rect)
        if clamped.is_empty:
            raise ValueError(f"region {region} does not overlap frame {self.rect}")

        local = clamped.normalised_within(self.rect)
        stride = self.rect.width * BYTES_PER_PIXEL
        row_bytes = local.width * BYTES_PER_PIXEL

        rows: list[bytes] = []
        for row in range(local.height):
            start = (local.top + row) * stride + local.left * BYTES_PER_PIXEL
            rows.append(self.pixels[start : start + row_bytes])

        return Frame(rect=clamped, pixels=b"".join(rows))
