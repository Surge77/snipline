"""System tray presence.

Kept thin on purpose: a tray icon is an OS boundary with no useful test seam, so it owns no
logic beyond turning menu clicks into signals. Everything a test would want to assert lives
in ``CaptureFlow``.

The icon is drawn in code rather than loaded from a file. A missing icon resource is a
classic PyInstaller failure -- it works in development and breaks in the bundle -- and this
sidesteps it entirely for a shape this simple.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

__all__ = ["Tray", "build_icon"]

_ICON_SIZE = 64
_MARGIN = 10
_STROKE = 6
_CORNER = 20
_ACCENT = "#3B82F6"

_NOTIFICATION_TIMEOUT_MS = 4000


def build_icon() -> QIcon:
    """A crop-marks glyph, drawn at runtime."""
    pixmap = QPixmap(_ICON_SIZE, _ICON_SIZE)
    pixmap.fill(QColor(0, 0, 0, 0))

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(QPen(QColor(_ACCENT), _STROKE))

    near, far = _MARGIN, _ICON_SIZE - _MARGIN
    # Four corner brackets, leaving the middle open -- a selection frame rather than a box.
    for x_edge, x_step in ((near, 1), (far, -1)):
        for y_edge, y_step in ((near, 1), (far, -1)):
            painter.drawLine(x_edge, y_edge, x_edge + _CORNER * x_step, y_edge)
            painter.drawLine(x_edge, y_edge, x_edge, y_edge + _CORNER * y_step)
    painter.end()

    return QIcon(pixmap)


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
