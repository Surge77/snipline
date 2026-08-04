"""The application style sheet.

Built as a string from the tokens rather than kept as a ``.qss`` file, for two reasons: a
stylesheet file is a runtime resource and would reintroduce the PyInstaller failure mode the
icons were drawn in code to avoid, and a literal ``#0B0E14`` written into a stylesheet is a
copy of a token that nothing keeps in sync.

The Fusion style is applied alongside this. Qt's native Windows style paints several widgets
through the OS theme engine, which ignores most style-sheet properties -- a QSpinBox keeps
its light native background and the toolbar ends up half dark. Fusion draws everything
itself, so the sheet below is the whole story.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from snipline.ui import theme

__all__ = ["apply_theme", "build_stylesheet"]


def build_stylesheet() -> str:
    """The whole application sheet."""
    return f"""
QMainWindow, QDialog {{
    background: {theme.SURFACE};
}}

QWidget {{
    color: {theme.TEXT_PRIMARY};
    font-size: 13px;
}}

/* The capture fills the view, so the view's own background is only ever seen as the
   letterbox around a capture smaller than the window. */
QGraphicsView {{
    background: {theme.SURFACE};
    border: none;
}}

QToolBar {{
    background: {theme.SURFACE_RAISED};
    border: none;
    border-bottom: 1px solid {theme.BORDER};
    padding: 6px 8px;
    spacing: 4px;
}}

QToolBar::separator {{
    background: {theme.BORDER};
    width: 1px;
    margin: 4px 8px;
}}

QToolButton {{
    background: transparent;
    border: 1px solid transparent;
    border-radius: {theme.RADIUS_CONTROL}px;
    padding: 5px 9px;
    color: {theme.TEXT_MUTED};
}}

QToolButton:hover {{
    background: {theme.SURFACE_HOVER};
    color: {theme.TEXT_PRIMARY};
}}

QToolButton:pressed {{
    background: {theme.rgba(theme.ACCENT, 0.24)};
}}

/* Checked is the selected tool. It reads as accent-on-tinted-ground rather than as a
   pressed bevel, which is the one state a user needs to find without looking. */
QToolButton:checked {{
    background: {theme.ACCENT_SOFT};
    border: 1px solid {theme.rgba(theme.ACCENT, 0.34)};
    color: {theme.ACCENT_TEXT};
}}

QToolButton:disabled {{
    color: {theme.TEXT_DISABLED};
}}

QComboBox, QSpinBox, QLineEdit {{
    background: {theme.SURFACE};
    border: 1px solid {theme.BORDER};
    border-radius: {theme.RADIUS_CONTROL}px;
    padding: 4px 8px;
    min-height: 22px;
    color: {theme.TEXT_PRIMARY};
    selection-background-color: {theme.ACCENT};
}}

QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{
    border: 1px solid {theme.BORDER_STRONG};
}}

QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{
    border: 1px solid {theme.ACCENT};
}}

QComboBox::drop-down {{
    border: none;
    width: 18px;
}}

QComboBox QAbstractItemView {{
    background: {theme.SURFACE_RAISED};
    border: 1px solid {theme.BORDER};
    border-radius: {theme.RADIUS_CONTROL}px;
    padding: 4px;
    selection-background-color: {theme.ACCENT_SOFT};
    selection-color: {theme.TEXT_PRIMARY};
    outline: none;
}}

QSpinBox::up-button, QSpinBox::down-button {{
    background: {theme.SURFACE_HOVER};
    border: none;
    width: 16px;
}}

QSpinBox::up-button {{
    border-top-right-radius: {theme.RADIUS_SMALL}px;
}}

QSpinBox::down-button {{
    border-bottom-right-radius: {theme.RADIUS_SMALL}px;
}}

QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
    background: {theme.rgba(theme.ACCENT, 0.30)};
}}

QMenu {{
    background: {theme.SURFACE_RAISED};
    border: 1px solid {theme.BORDER};
    border-radius: {theme.RADIUS_PANEL}px;
    padding: 6px;
}}

QMenu::item {{
    padding: 7px 16px;
    border-radius: {theme.RADIUS_SMALL}px;
    color: {theme.TEXT_PRIMARY};
}}

QMenu::item:selected {{
    background: {theme.ACCENT_SOFT};
    color: {theme.ACCENT_TEXT};
}}

QMenu::separator {{
    height: 1px;
    background: {theme.BORDER};
    margin: 6px 8px;
}}

QToolTip {{
    background: {theme.SURFACE_RAISED};
    border: 1px solid {theme.BORDER};
    border-radius: {theme.RADIUS_SMALL}px;
    padding: 5px 8px;
    color: {theme.TEXT_PRIMARY};
}}

QStatusBar {{
    background: {theme.SURFACE_RAISED};
    border-top: 1px solid {theme.BORDER};
    color: {theme.TEXT_MUTED};
}}

QScrollBar:vertical, QScrollBar:horizontal {{
    background: transparent;
    border: none;
    width: 10px;
    height: 10px;
}}

QScrollBar::handle {{
    background: {theme.rgba("#FFFFFF", 0.16)};
    border-radius: 5px;
    min-height: 28px;
    min-width: 28px;
}}

QScrollBar::handle:hover {{
    background: {theme.rgba("#FFFFFF", 0.26)};
}}

QScrollBar::add-line, QScrollBar::sub-line,
QScrollBar::add-page, QScrollBar::sub-page {{
    background: none;
    border: none;
    height: 0px;
    width: 0px;
}}
"""


def _dark_palette() -> QPalette:
    """Colours for the parts Qt paints without consulting the style sheet.

    Menu shadows, the text cursor, and disabled text all come from the palette, so leaving
    it light produces a dark application with a handful of bright artefacts in it.
    """
    palette = QPalette()
    surface, raised = QColor(theme.SURFACE), QColor(theme.SURFACE_RAISED)
    text, muted = QColor(theme.TEXT_PRIMARY), QColor(theme.TEXT_DISABLED)

    for role in (QPalette.ColorRole.Window, QPalette.ColorRole.Base):
        palette.setColor(role, surface)
    palette.setColor(QPalette.ColorRole.AlternateBase, raised)
    palette.setColor(QPalette.ColorRole.Button, raised)
    palette.setColor(QPalette.ColorRole.ToolTipBase, raised)

    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
        QPalette.ColorRole.ToolTipText,
        QPalette.ColorRole.BrightText,
    ):
        palette.setColor(role, text)

    palette.setColor(QPalette.ColorRole.Highlight, QColor(theme.ACCENT))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Link, QColor(theme.ACCENT_TEXT))

    for role in (
        QPalette.ColorRole.WindowText,
        QPalette.ColorRole.Text,
        QPalette.ColorRole.ButtonText,
    ):
        palette.setColor(QPalette.ColorGroup.Disabled, role, muted)
    return palette


def apply_theme(app: QApplication) -> None:
    """Style, palette, and sheet, in that order.

    Order matters: setting the style resets the palette, so a palette applied first is
    discarded.
    """
    app.setStyle("Fusion")
    app.setPalette(_dark_palette())
    app.setStyleSheet(build_stylesheet())
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)
