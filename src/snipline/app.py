"""Application entry point.

The ordering constraint in ``main`` is load-bearing: DPI awareness must be declared before
``QApplication`` exists. Qt queries screen geometry during construction, and a process that
is not yet DPI-aware receives virtualised numbers that stay wrong for the rest of its life.

Tray, hotkey, and capture flow arrive in M2.
"""

from __future__ import annotations

import sys

from snipline.platform.dpi import declare_dpi_awareness

APP_NAME = "Snipline"
ORG_NAME = "Snipline"


def main() -> int:
    declare_dpi_awareness()

    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setQuitOnLastWindowClosed(False)  # the tray outlives every window

    raise NotImplementedError("M2: tray, single instance, and hotkey registration")


if __name__ == "__main__":
    sys.exit(main())
