"""Settings persistence.

Every test uses an isolated INI file rather than the native registry scope: writing to the
real user scope would pollute the developer's actual settings and leak state between runs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from snipline.config import DefaultSink, ExportFormat, RedactionStyle, Settings
from snipline.settings_store import SettingsStore


@pytest.fixture
def store(tmp_path: Path) -> SettingsStore:
    return SettingsStore(QSettings(str(tmp_path / "snipline.ini"), QSettings.Format.IniFormat))


def test_defaults_are_returned_when_nothing_is_stored(store: SettingsStore) -> None:
    assert store.load() == Settings()


def test_every_field_survives_a_round_trip(store: SettingsStore, tmp_path: Path) -> None:
    original = Settings(
        hotkey="Ctrl+Alt+P",
        default_sink=DefaultSink.FILE,
        export_format=ExportFormat.WEBP,
        jpeg_quality=71,
        save_directory=tmp_path / "shots",
        redaction_style=RedactionStyle.PIXELATE,
        show_magnifier=False,
    )

    store.save(original)

    assert store.load() == original


def test_a_boolean_survives_the_string_round_trip(store: SettingsStore) -> None:
    # QSettings round-trips booleans as strings through the registry, so a naive read
    # returns the string "false" -- which is truthy.
    store.save(Settings(show_magnifier=False))

    assert store.load().show_magnifier is False


def test_an_unparseable_hotkey_falls_back_to_the_default(store: SettingsStore) -> None:
    # A hotkey that cannot be parsed would fail to register, leaving the app with no
    # working shortcut and no obvious cause.
    store.save(Settings())
    store._store.setValue("hotkey", "Ctrl+NotAKey")  # type: ignore[attr-defined]

    assert store.load().hotkey == Settings().hotkey


def test_an_unknown_enum_value_falls_back(store: SettingsStore) -> None:
    store.save(Settings())
    store._store.setValue("export_format", "tiff")  # type: ignore[attr-defined]

    assert store.load().export_format == Settings().export_format


@pytest.mark.parametrize("quality", ["not a number", "0", "101", "-5"])
def test_an_out_of_range_quality_falls_back(store: SettingsStore, quality: str) -> None:
    # Settings validates this and would raise; a hand-edited file must not stop the app
    # from starting.
    store.save(Settings())
    store._store.setValue("jpeg_quality", quality)  # type: ignore[attr-defined]

    assert store.load().jpeg_quality == Settings().jpeg_quality


def test_one_corrupt_value_does_not_discard_the_others(store: SettingsStore) -> None:
    store.save(Settings(hotkey="Ctrl+Alt+P", export_format=ExportFormat.WEBP))
    store._store.setValue("jpeg_quality", "garbage")  # type: ignore[attr-defined]

    loaded = store.load()

    assert loaded.jpeg_quality == Settings().jpeg_quality
    assert loaded.hotkey == "Ctrl+Alt+P"
    assert loaded.export_format == ExportFormat.WEBP


def test_an_empty_save_directory_loads_as_none(store: SettingsStore) -> None:
    store.save(Settings(save_directory=None))

    assert store.load().save_directory is None


def test_settings_persist_across_store_instances(tmp_path: Path) -> None:
    path = str(tmp_path / "snipline.ini")
    SettingsStore(QSettings(path, QSettings.Format.IniFormat)).save(
        Settings(hotkey="Ctrl+Alt+9")
    )

    reopened = SettingsStore(QSettings(path, QSettings.Format.IniFormat))

    assert reopened.load().hotkey == "Ctrl+Alt+9"
