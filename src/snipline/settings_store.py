"""Persisting settings.

``QSettings`` writes to the Windows registry, so the scope is injected rather than assumed:
tests pass their own, and never touch the real user's keys.

Loading is deliberately forgiving. A settings file can be edited by hand, written by an older
version, or corrupted by a crash mid-write, and none of those is a reason for a screenshot
tool to refuse to start. Every unreadable value falls back to its default and the rest of the
settings still load.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import TypeVar

from PySide6.QtCore import QSettings

from snipline.config import DefaultSink, ExportFormat, RedactionStyle, Settings
from snipline.platform.keys import parse_hotkey

__all__ = ["SettingsStore"]

# PEP 695 syntax would read better but requires 3.12; this project's floor is 3.11.
EnumT = TypeVar("EnumT", bound=Enum)

_KEY_HOTKEY = "hotkey"
_KEY_SINK = "default_sink"
_KEY_FORMAT = "export_format"
_KEY_QUALITY = "jpeg_quality"
_KEY_DIRECTORY = "save_directory"
_KEY_REDACTION = "redaction_style"
_KEY_MAGNIFIER = "show_magnifier"


class SettingsStore:
    """Reads and writes ``Settings``."""

    def __init__(self, settings: QSettings) -> None:
        self._store = settings

    def load(self) -> Settings:
        """Read persisted settings, falling back to defaults for anything unusable."""
        defaults = Settings()

        return Settings(
            hotkey=self._valid_hotkey(defaults.hotkey),
            default_sink=self._enum(_KEY_SINK, DefaultSink, defaults.default_sink),
            export_format=self._enum(_KEY_FORMAT, ExportFormat, defaults.export_format),
            jpeg_quality=self._quality(defaults.jpeg_quality),
            save_directory=self._directory(),
            redaction_style=self._enum(_KEY_REDACTION, RedactionStyle, defaults.redaction_style),
            show_magnifier=self._bool(_KEY_MAGNIFIER, defaults.show_magnifier),
        )

    def save(self, settings: Settings) -> None:
        self._store.setValue(_KEY_HOTKEY, settings.hotkey)
        self._store.setValue(_KEY_SINK, settings.default_sink.value)
        self._store.setValue(_KEY_FORMAT, settings.export_format.value)
        self._store.setValue(_KEY_QUALITY, settings.jpeg_quality)
        self._store.setValue(
            _KEY_DIRECTORY, str(settings.save_directory) if settings.save_directory else ""
        )
        self._store.setValue(_KEY_REDACTION, settings.redaction_style.value)
        self._store.setValue(_KEY_MAGNIFIER, settings.show_magnifier)
        self._store.sync()

    def _raw(self, key: str) -> str | None:
        value = self._store.value(key)
        return value if isinstance(value, str) and value else None

    def _valid_hotkey(self, fallback: str) -> str:
        stored = self._raw(_KEY_HOTKEY)
        if stored is None:
            return fallback
        try:
            parse_hotkey(stored)
        except ValueError:
            # A hotkey that cannot be parsed would fail to register and leave the app with
            # no working shortcut, which is its worst failure mode.
            return fallback
        return stored

    def _enum(self, key: str, enum: type[EnumT], fallback: EnumT) -> EnumT:
        stored = self._raw(key)
        if stored is None:
            return fallback
        try:
            return enum(stored)
        except ValueError:
            return fallback

    def _quality(self, fallback: int) -> int:
        try:
            quality = int(self._store.value(_KEY_QUALITY, fallback))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return fallback
        # Settings validates this too and would raise; clamping here keeps a hand-edited
        # value from stopping the app from starting.
        return quality if 1 <= quality <= 100 else fallback

    def _directory(self) -> Path | None:
        stored = self._raw(_KEY_DIRECTORY)
        return Path(stored) if stored else None

    def _bool(self, key: str, fallback: bool) -> bool:
        value = self._store.value(key, fallback)
        if isinstance(value, bool):
            return value
        # QSettings round-trips booleans as strings through the registry.
        if isinstance(value, str):
            return value.lower() in {"true", "1", "yes"}
        return fallback
