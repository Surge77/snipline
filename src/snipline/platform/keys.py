"""Hotkey text to Win32 modifier mask and virtual-key code.

``RegisterHotKey`` wants a bitmask and a VK code. Turning ``"Ctrl+Shift+S"`` into that pair
is pure table lookup, so it lives here, fully tested, and the ctypes call in ``hotkey.py``
is left with no decisions to make.

Strict parsing is deliberate. A hotkey that silently registers a *different* combination
from the one the user typed is, from their side, indistinguishable from a broken tool -- so
anything ambiguous is rejected rather than guessed at.
"""

from __future__ import annotations

from dataclasses import dataclass

__all__ = [
    "MOD_ALT",
    "MOD_CONTROL",
    "MOD_NOREPEAT",
    "MOD_SHIFT",
    "MOD_WIN",
    "HotkeySpec",
    "format_hotkey",
    "parse_hotkey",
]

# Modifier flags for RegisterHotKey, from winuser.h.
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
# Without NOREPEAT, holding the combination down queues one capture per key repeat and the
# user gets a burst of screenshots.
MOD_NOREPEAT = 0x4000

_MODIFIER_NAMES = {
    "ctrl": MOD_CONTROL,
    "control": MOD_CONTROL,
    "alt": MOD_ALT,
    "shift": MOD_SHIFT,
    "win": MOD_WIN,
    "meta": MOD_WIN,
    "super": MOD_WIN,
}

# Ordered as Windows itself renders modifiers, so a round-tripped hotkey reads the way the
# user expects to see it written.
_MODIFIER_DISPLAY = (
    (MOD_CONTROL, "Ctrl"),
    (MOD_ALT, "Alt"),
    (MOD_SHIFT, "Shift"),
    (MOD_WIN, "Win"),
)

_FUNCTION_KEY_COUNT = 12
_VK_F1 = 0x70

_NAMED_KEYS = {
    "space": 0x20,
    "esc": 0x1B,
    "escape": 0x1B,
    "tab": 0x09,
    "enter": 0x0D,
    "return": 0x0D,
    "backspace": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "insert": 0x2D,
    "ins": 0x2D,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "printscreen": 0x2C,
    "prtsc": 0x2C,
    "prtscn": 0x2C,
    "snapshot": 0x2C,
    "pause": 0x13,
}

_KEY_DISPLAY = {
    0x20: "Space",
    0x1B: "Esc",
    0x09: "Tab",
    0x0D: "Enter",
    0x08: "Backspace",
    0x2E: "Delete",
    0x2D: "Insert",
    0x24: "Home",
    0x23: "End",
    0x21: "PageUp",
    0x22: "PageDown",
    0x25: "Left",
    0x26: "Up",
    0x27: "Right",
    0x28: "Down",
    0x2C: "PrintScreen",
    0x13: "Pause",
}


@dataclass(frozen=True, slots=True)
class HotkeySpec:
    """A parsed hotkey, ready for ``RegisterHotKey``.

    ``text`` keeps whatever the user typed so error messages and the settings UI can echo it
    back verbatim rather than a canonicalised form they may not recognise.
    """

    modifiers: int
    vk: int
    text: str


def _parse_key(name: str) -> int:
    lowered = name.lower()

    if lowered in _NAMED_KEYS:
        return _NAMED_KEYS[lowered]

    if len(name) == 1 and name.isalnum():
        # VK codes for letters and digits are their uppercase ASCII values.
        return ord(name.upper())

    if lowered.startswith("f") and lowered[1:].isdigit():
        number = int(lowered[1:])
        if 1 <= number <= _FUNCTION_KEY_COUNT:
            return _VK_F1 + number - 1
        raise ValueError(f"function key out of range: {name!r}")

    raise ValueError(f"unknown key: {name!r}")


def parse_hotkey(text: str) -> HotkeySpec:
    """Parse ``"Ctrl+Shift+S"`` into modifier flags and a virtual-key code.

    A bare key with no modifier is allowed: PrintScreen alone is a common and legitimate
    screenshot binding.
    """
    parts = [part.strip() for part in text.split("+")]
    if not text.strip() or any(not part for part in parts):
        raise ValueError(f"malformed hotkey: {text!r}")

    *modifier_names, key_name = parts

    modifiers = 0
    for name in modifier_names:
        flag = _MODIFIER_NAMES.get(name.lower())
        if flag is None:
            raise ValueError(f"{name!r} is not a modifier; modifiers must come first")
        if modifiers & flag:
            raise ValueError(f"repeated modifier in {text!r}")
        modifiers |= flag

    if key_name.lower() in _MODIFIER_NAMES:
        raise ValueError(f"hotkey needs a non-modifier key: {text!r}")

    return HotkeySpec(modifiers=modifiers | MOD_NOREPEAT, vk=_parse_key(key_name), text=text)


def format_hotkey(spec: HotkeySpec) -> str:
    """Canonical spelling, for display. Round-trips through ``parse_hotkey``."""
    names = [name for flag, name in _MODIFIER_DISPLAY if spec.modifiers & flag]

    if spec.vk in _KEY_DISPLAY:
        names.append(_KEY_DISPLAY[spec.vk])
    elif _VK_F1 <= spec.vk < _VK_F1 + _FUNCTION_KEY_COUNT:
        names.append(f"F{spec.vk - _VK_F1 + 1}")
    else:
        names.append(chr(spec.vk))

    return "+".join(names)
