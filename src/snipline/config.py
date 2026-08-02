"""Application settings."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

DEFAULT_HOTKEY = "Ctrl+Shift+S"


class ExportFormat(Enum):
    PNG = "png"
    WEBP = "webp"
    JPEG = "jpeg"

    @property
    def supports_alpha(self) -> bool:
        return self is not ExportFormat.JPEG


class DefaultSink(Enum):
    CLIPBOARD = "clipboard"
    FILE = "file"


class RedactionStyle(Enum):
    """Only SOLID and PIXELATE are redaction. BLUR is a cosmetic effect.

    Blurred text is frequently recoverable by rendering candidate strings under the same
    blur and comparing, so presenting blur as a privacy feature makes a promise it cannot
    keep. SOLID is the default for that reason. See D7 in docs/DECISIONS.md.
    """

    SOLID = "solid"
    PIXELATE = "pixelate"
    BLUR = "blur"

    @property
    def is_redaction(self) -> bool:
        return self is not RedactionStyle.BLUR


@dataclass(slots=True)
class Settings:
    hotkey: str = DEFAULT_HOTKEY
    default_sink: DefaultSink = DefaultSink.CLIPBOARD
    export_format: ExportFormat = ExportFormat.PNG
    jpeg_quality: int = 92
    save_directory: Path | None = None
    redaction_style: RedactionStyle = RedactionStyle.SOLID
    show_magnifier: bool = True

    def __post_init__(self) -> None:
        if not 1 <= self.jpeg_quality <= 100:
            raise ValueError(f"jpeg quality out of range: {self.jpeg_quality}")
