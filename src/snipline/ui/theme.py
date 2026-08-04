"""Design tokens.

Plain strings and ints, no Qt types, for the same reason ``editor/style.py`` holds none:
the values are asserted in tests that must not need a QApplication, and a token module that
imports Qt drags the whole GUI into every import of it.

**Dark only, deliberately.** A screenshot annotator draws its chrome over arbitrary pixels it
did not choose. A theme that followed the OS would flip the toolbar to light while the user
is annotating a light screenshot, which is exactly when the chrome most needs to separate
from the content. One committed surface colour is a smaller lie than a contrast guarantee
that only holds half the time.

Note the difference between this module and ``editor/style.py``. This is the colour of the
*application*; that is the colour of the *annotations*. They are separate because the user
changes one constantly and the other never.
"""

from __future__ import annotations

__all__ = [
    "ACCENT",
    "ACCENT_PRESSED",
    "ACCENT_SOFT",
    "ACCENT_TEXT",
    "BORDER",
    "BORDER_STRONG",
    "RADIUS_CONTROL",
    "RADIUS_PANEL",
    "RADIUS_SMALL",
    "SPACE",
    "SURFACE",
    "SURFACE_HOVER",
    "SURFACE_RAISED",
    "TEXT_DISABLED",
    "TEXT_MUTED",
    "TEXT_PRIMARY",
    "rgba",
]


def rgba(hex_colour: str, alpha: float) -> str:
    """``"#3B82F6", 0.14`` -> ``"rgba(59, 130, 246, 0.14)"``.

    Qt style sheets accept ``rgba()`` but not the ``#RRGGBBAA`` shorthand, and hard-coding
    the decimal triples next to the hex ones is how a palette drifts out of sync.
    """
    value = hex_colour.lstrip("#")
    if len(value) != 6:
        raise ValueError(f"expected a 6-digit hex colour, got {hex_colour!r}")
    if not 0.0 <= alpha <= 1.0:
        raise ValueError(f"alpha out of range: {alpha}")
    red, green, blue = (int(value[i : i + 2], 16) for i in (0, 2, 4))
    return f"rgba({red}, {green}, {blue}, {alpha})"


# -- surfaces -------------------------------------------------------------------
# Near-black rather than pure black: #000 against a dark screenshot reads as a hole in the
# screen, and the 1px borders below have nothing to separate from.
SURFACE = "#0B0E14"
SURFACE_RAISED = "#141922"
SURFACE_HOVER = "#1C2230"

# Hairlines, not solid greys. A border that is a lightened surface colour stops working the
# moment the panel sits on something lighter than itself; an alpha-white line does not.
BORDER = rgba("#FFFFFF", 0.08)
BORDER_STRONG = rgba("#FFFFFF", 0.14)

# -- text -----------------------------------------------------------------------
TEXT_PRIMARY = "#E6EAF2"
TEXT_MUTED = "#9AA4B8"
TEXT_DISABLED = "#5D6779"

# -- accent ---------------------------------------------------------------------
# The same blue the selection border already used, so the overlay and the editor read as one
# application rather than two that happen to launch together.
ACCENT = "#3B82F6"
ACCENT_TEXT = "#93C5FD"
ACCENT_PRESSED = "#2563EB"
ACCENT_SOFT = rgba(ACCENT, 0.16)

# -- geometry -------------------------------------------------------------------
RADIUS_PANEL = 12
RADIUS_CONTROL = 8
RADIUS_SMALL = 6

SPACE = 8
