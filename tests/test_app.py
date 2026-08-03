"""Application wiring.

Asserts that each of the three ways to ask for a capture -- the tray menu, the hotkey, and a
second launch -- actually reaches the capture flow. That wiring is easy to get subtly wrong
and impossible to notice: a disconnected signal looks exactly like a working app until the
moment someone uses that path.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from snipline.app import APP_NAME, configure_application, wire
from snipline.capture.fake_backend import FakeBackend
from snipline.capture.service import CaptureService
from snipline.capture_flow import CaptureFlow
from snipline.config import Settings
from snipline.platform.geometry import MonitorInfo, PhysicalRect
from snipline.single_instance import CAPTURE_COMMAND, SingleInstance
from snipline.tray import Tray, build_icon

MONITORS = [
    MonitorInfo(0, PhysicalRect(0, 0, 320, 240), PhysicalRect(0, 0, 320, 240), 1.0, True)
]


@pytest.fixture
def flow(tmp_path: Path, backend: FakeBackend) -> CaptureFlow:
    return CaptureFlow(
        service=CaptureService(backend=backend, monitors_provider=lambda: MONITORS),
        settings=Settings(save_directory=tmp_path),
    )


def test_build_application_configures_names_and_tray_survival(qapp: QApplication) -> None:
    # setQuitOnLastWindowClosed(False) is what keeps a tray-only app alive once the editor
    # window is closed; losing it would make the app exit after the first capture.
    app = configure_application(qapp)

    assert app.applicationName() == APP_NAME
    assert not app.quitOnLastWindowClosed()


def test_the_tray_menu_reaches_the_capture_flow(
    qapp: QApplication, flow: CaptureFlow, tmp_path: Path
) -> None:
    tray = Tray(APP_NAME)
    instance = SingleInstance("snipline-test-wire-tray")
    try:
        wire(qapp, flow, tray, instance)
        tray.capture_requested.emit()
    finally:
        instance.close()

    assert list(tmp_path.glob("*.png"))


def test_the_hotkey_reaches_the_capture_flow(
    qapp: QApplication, flow: CaptureFlow, tmp_path: Path
) -> None:
    tray = Tray(APP_NAME)
    instance = SingleInstance("snipline-test-wire-hotkey")
    try:
        hotkey = wire(qapp, flow, tray, instance)
        hotkey.triggered.emit()
    finally:
        instance.close()

    assert list(tmp_path.glob("*.png"))


def test_a_second_launch_reaches_the_capture_flow(
    qapp: QApplication, flow: CaptureFlow, tmp_path: Path
) -> None:
    tray = Tray(APP_NAME)
    instance = SingleInstance("snipline-test-wire-second")
    try:
        wire(qapp, flow, tray, instance)
        instance.command_received.emit(CAPTURE_COMMAND)
    finally:
        instance.close()

    assert list(tmp_path.glob("*.png"))


def test_quitting_releases_the_hotkey_and_the_instance_lock(
    qapp: QApplication, flow: CaptureFlow
) -> None:
    # A leaked registration would make the next launch report the hotkey as taken -- by
    # itself.
    tray = Tray(APP_NAME)
    instance = SingleInstance("snipline-test-wire-quit")
    instance.try_become_primary()

    hotkey = wire(qapp, flow, tray, instance)
    tray.quit_requested.emit()

    assert hotkey.registered is None
    assert not instance.is_primary


def test_the_tray_icon_is_drawn_not_loaded(qapp: QApplication) -> None:
    # Drawn at runtime so there is no icon file for PyInstaller to leave out of the bundle.
    icon = build_icon()

    assert not icon.isNull()
    assert icon.availableSizes()


def test_notifying_never_raises_when_the_shell_suppresses_balloons(
    qapp: QApplication,
) -> None:
    # Notifications being unavailable is not a reason for a capture to fail.
    Tray(APP_NAME).notify("title", "message", is_error=True)
