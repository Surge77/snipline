"""Application entry point.

The ordering constraint in ``main`` is load-bearing: DPI awareness must be declared before
``QApplication`` exists. Qt queries screen geometry during construction, and a process that
is not yet DPI-aware receives virtualised numbers that stay wrong for the rest of its life.

The hotkey opens the selection overlay. Capturing the whole desktop remains available
through ``CaptureFlow`` and is the fallback when no overlay can be shown.
"""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from snipline.capture.service import CaptureService
from snipline.capture_flow import CaptureFlow
from snipline.config import Settings
from snipline.platform.dpi import declare_dpi_awareness
from snipline.platform.hotkey import GlobalHotkey, HotkeyError
from snipline.platform.keys import parse_hotkey
from snipline.region_capture import RegionCapture
from snipline.single_instance import SingleInstance
from snipline.tray import Tray

APP_NAME = "Snipline"
ORG_NAME = "Snipline"
INSTANCE_KEY = "snipline-single-instance"

# A second launch that hands its request to the running copy has done its job.
EXIT_HANDED_OFF = 0


def configure_application(app: QApplication) -> QApplication:
    """Apply application-wide settings.

    Separate from construction because Qt permits exactly one QApplication per process,
    which would otherwise leave this configuration untestable.
    """
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG_NAME)
    app.setQuitOnLastWindowClosed(False)  # the tray outlives every window
    return app


def build_application(argv: list[str]) -> QApplication:
    return configure_application(QApplication(argv))


def wire(
    app: QApplication,
    flow: CaptureFlow,
    tray: Tray,
    instance: SingleInstance,
    region: RegionCapture | None = None,
) -> GlobalHotkey:
    """Connect the tray, the second-launch channel, and the hotkey to a capture.

    With a ``RegionCapture`` the hotkey opens the selection overlay. Without one it falls
    back to capturing the whole desktop -- what M2 did, and still the behaviour when no
    overlay can be shown.

    Returns the hotkey so the caller can register it and decide how to report failure.
    """
    start_capture = region.start if region is not None else flow.capture_desktop

    def on_second_launch(_payload: bytes) -> None:
        start_capture()

    tray.capture_requested.connect(start_capture)
    instance.command_received.connect(on_second_launch)

    hotkey = GlobalHotkey(parent=app)
    app.installNativeEventFilter(hotkey)
    hotkey.triggered.connect(start_capture)

    def shutdown() -> None:
        # Before anything else: an overlay outliving the app leaves a frozen, unclickable
        # image covering the screen, with no tray icon left to quit from.
        if region is not None:
            region.abort()
        hotkey.unregister()
        instance.close()
        tray.hide()
        app.quit()

    tray.quit_requested.connect(shutdown)
    return hotkey


def main() -> int:
    # First statement for a reason -- see the module docstring and M1 in docs/PLAN.md.
    declare_dpi_awareness()

    app = build_application(sys.argv)

    instance = SingleInstance(INSTANCE_KEY)
    if not instance.try_become_primary():
        # Another copy already owns the hotkey. Hand it the request rather than starting a
        # second tray icon whose own registration would fail anyway.
        instance.send_command()
        return EXIT_HANDED_OFF

    from snipline.capture.mss_backend import MssBackend

    settings = Settings()
    tray = Tray(APP_NAME)
    service = CaptureService(backend=MssBackend())
    flow = CaptureFlow(service=service, settings=settings, reporter=tray.notify)
    region = RegionCapture(service=service, flow=flow, parent=app)

    hotkey = wire(app, flow, tray, instance, region)
    try:
        hotkey.register(parse_hotkey(settings.hotkey))
    except (HotkeyError, ValueError) as error:
        # Never swallowed: a hotkey that does nothing, with no error shown, is the worst
        # failure mode this application has.
        tray.notify("Hotkey unavailable", str(error), is_error=True)

    tray.show()
    tray.notify(APP_NAME, f"Ready. Press {settings.hotkey} to select a region.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
