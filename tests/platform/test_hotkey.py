"""Hotkey registration failure reporting.

The ``RegisterHotKey`` call itself is an OS boundary and is covered by MANUAL_TESTS.md;
asserting that ctypes was invoked with particular arguments would break on refactors and
catch nothing.

What *is* tested here is the message the user sees when registration fails, because "the
hotkey does nothing and there is no error" is this application's worst failure mode.
"""

from __future__ import annotations

import pytest

from snipline.platform.hotkey import (
    ERROR_HOTKEY_ALREADY_REGISTERED,
    GlobalHotkey,
    HotkeyError,
    describe_registration_failure,
)
from snipline.platform.keys import parse_hotkey


def test_conflict_message_names_the_combination_and_the_way_out() -> None:
    message = describe_registration_failure(
        parse_hotkey("Ctrl+Shift+S"), ERROR_HOTKEY_ALREADY_REGISTERED
    )

    assert "Ctrl+Shift+S" in message
    assert "another application" in message
    assert "Settings" in message


def test_unknown_failure_still_names_the_combination_and_the_code() -> None:
    message = describe_registration_failure(parse_hotkey("Alt+F4"), 5)

    assert "Alt+F4" in message
    assert "5" in message


def test_message_uses_canonical_spelling_not_the_raw_input() -> None:
    message = describe_registration_failure(parse_hotkey("shift+ctrl+s"), 1409)

    assert "Ctrl+Shift+S" in message


def test_a_fresh_hotkey_has_nothing_registered(qapp: object) -> None:
    assert GlobalHotkey().registered is None


def test_unregister_is_safe_when_nothing_is_registered(qapp: object) -> None:
    hotkey = GlobalHotkey()

    hotkey.unregister()
    hotkey.unregister()

    assert hotkey.registered is None


def test_non_hotkey_native_events_are_ignored(qapp: object) -> None:
    hotkey = GlobalHotkey()
    fired: list[bool] = []
    hotkey.triggered.connect(lambda: fired.append(True))

    # A message from a platform this filter does not handle must be passed through
    # untouched rather than dereferenced as a Win32 MSG pointer.
    handled, result = hotkey.nativeEventFilter(b"xcb_generic_event_t", 0)

    assert (handled, result) == (False, 0)
    assert fired == []


def test_registering_off_windows_fails_loudly(
    qapp: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("snipline.platform.hotkey.sys.platform", "linux")

    with pytest.raises(HotkeyError, match="Windows-only"):
        GlobalHotkey().register(parse_hotkey("Ctrl+Shift+S"))
