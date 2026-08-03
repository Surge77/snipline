"""Hotkey string parsing.

``RegisterHotKey`` takes a modifier bitmask and a virtual-key code. Everything between the
user's ``"Ctrl+Shift+S"`` and that pair is pure, so it is tested exhaustively here and the
ctypes call is left with nothing to decide.

Rejecting bad input precisely matters more than usual: a hotkey that silently registers the
wrong combination is indistinguishable, from the user's side, from a tool that is broken.
"""

from __future__ import annotations

import pytest

from snipline.platform.keys import (
    MOD_ALT,
    MOD_CONTROL,
    MOD_NOREPEAT,
    MOD_SHIFT,
    MOD_WIN,
    format_hotkey,
    parse_hotkey,
)


def test_parses_a_simple_combination() -> None:
    spec = parse_hotkey("Ctrl+Shift+S")

    assert spec.modifiers == MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT
    assert spec.vk == ord("S")


def test_sets_norepeat_so_a_held_key_fires_once() -> None:
    # Without MOD_NOREPEAT, holding the combination queues a capture per key repeat and the
    # user gets a burst of screenshots.
    assert parse_hotkey("Ctrl+P").modifiers & MOD_NOREPEAT


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("ctrl+shift+s", MOD_CONTROL | MOD_SHIFT),
        ("CTRL+ALT+S", MOD_CONTROL | MOD_ALT),
        ("  Ctrl + Shift + S  ", MOD_CONTROL | MOD_SHIFT),
        ("Control+S", MOD_CONTROL),
        ("Win+Shift+S", MOD_WIN | MOD_SHIFT),
        ("Meta+S", MOD_WIN),
        ("Alt+S", MOD_ALT),
    ],
)
def test_modifier_spellings_and_casing(text: str, expected: int) -> None:
    assert parse_hotkey(text).modifiers == expected | MOD_NOREPEAT


@pytest.mark.parametrize(
    ("text", "expected_vk"),
    [
        ("Ctrl+A", 0x41),
        ("Ctrl+Z", 0x5A),
        ("Ctrl+0", 0x30),
        ("Ctrl+9", 0x39),
        ("Ctrl+F1", 0x70),
        ("Ctrl+F12", 0x7B),
        ("Ctrl+PrintScreen", 0x2C),
        ("Ctrl+Insert", 0x2D),
        ("Ctrl+Space", 0x20),
        ("Ctrl+Esc", 0x1B),
    ],
)
def test_key_names_map_to_virtual_key_codes(text: str, expected_vk: int) -> None:
    assert parse_hotkey(text).vk == expected_vk


def test_print_screen_alias_is_accepted() -> None:
    # The key is labelled "PrtSc" on most keyboards and "Print Screen" in Windows settings.
    assert parse_hotkey("PrtSc").vk == parse_hotkey("PrintScreen").vk


def test_a_bare_key_with_no_modifier_is_allowed() -> None:
    # PrintScreen alone is a legitimate and common screenshot binding.
    spec = parse_hotkey("PrintScreen")

    assert spec.modifiers == MOD_NOREPEAT
    assert spec.vk == 0x2C


@pytest.mark.parametrize(
    "text",
    ["", "   ", "Ctrl", "Ctrl+", "+S", "Ctrl+Shift", "Ctrl+NotAKey", "Ctrl+F13", "Ctrl+S+A"],
)
def test_rejects_malformed_combinations(text: str) -> None:
    with pytest.raises(ValueError):
        parse_hotkey(text)


def test_rejects_a_duplicated_modifier() -> None:
    with pytest.raises(ValueError, match="repeated"):
        parse_hotkey("Ctrl+Ctrl+S")


def test_keeps_the_original_text_for_display() -> None:
    assert parse_hotkey("ctrl+shift+s").text == "ctrl+shift+s"


@pytest.mark.parametrize(
    "text", ["Ctrl+Shift+S", "Alt+F4", "Win+Shift+S", "PrintScreen", "Ctrl+Alt+Insert"]
)
def test_format_round_trips_to_a_canonical_spelling(text: str) -> None:
    canonical = format_hotkey(parse_hotkey(text))

    assert parse_hotkey(canonical).vk == parse_hotkey(text).vk
    assert parse_hotkey(canonical).modifiers == parse_hotkey(text).modifiers


def test_format_orders_modifiers_consistently() -> None:
    assert format_hotkey(parse_hotkey("shift+ctrl+alt+s")) == "Ctrl+Alt+Shift+S"
