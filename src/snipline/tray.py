"""System tray presence.

Kept thin on purpose: a tray icon is an OS boundary with no useful test seam, so it owns no
logic beyond turning menu clicks into signals. Everything a test would want to assert lives
in ``CaptureFlow``.

The icon is drawn in code rather than loaded from a file. A missing icon resource is a
classic PyInstaller failure -- it works in development and breaks in the bundle -- and this
sidesteps it entirely for a shape this simple. The drawing itself now lives in ``ui/mark``,
so the tray, the window, and the executable's own icon are one shape rather than three that
happen to look alike.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from snipline.ui.mark import tray_icon

__all__ = ["Tray", "build_icon"]

_NOTIFICATION_TIMEOUT_MS = 4000


def build_icon() -> QIcon:
    """The mark, rendered at each size the shell asks for."""
    return tray_icon()


class Tray(QObject):
    """Tray icon and its menu, as signals."""

    capture_requested = Signal()
    settings_requested = Signal()
    quit_requested = Signal()

    def __init__(self, app_name: str, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._icon = QSystemTrayIcon(build_icon(), self)
        self._icon.setToolTip(app_name)

        menu = QMenu()
        self._menu = menu  # kept alive: QSystemTrayIcon does not take ownership
        for label, signal in (
            ("&Capture now", self.capture_requested),
            ("&Settings", self.settings_requested),
        ):
            action = QAction(label, menu)
            action.triggered.connect(signal)
            menu.addAction(action)

        menu.addSeparator()
        quit_action = QAction("&Quit", menu)
        quit_action.triggered.connect(self.quit_requested)
        menu.addAction(quit_action)

        self._icon.setContextMenu(menu)
        self._icon.activated.connect(self._on_activated)

    def show(self) -> None:
        self._icon.show()

    def hide(self) -> None:
        self._icon.hide()

    def notify(self, title: str, message: str, is_error: bool = False) -> None:
        """Show a balloon notification. Silently does nothing when the shell suppresses
        them -- notifications being disabled is not a reason to fail a capture."""
        icon = (
            QSystemTrayIcon.MessageIcon.Critical
            if is_error
            else QSystemTrayIcon.MessageIcon.Information
        )
        self._icon.showMessage(title, message, icon, _NOTIFICATION_TIMEOUT_MS)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Double-click is the conventional "do the main thing" gesture for a tray app.
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.capture_requested.emit()
