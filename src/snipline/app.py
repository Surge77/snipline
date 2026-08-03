"""Application entry point.

The ordering constraint in ``main`` is load-bearing: DPI awareness must be declared before
``QApplication`` exists. Qt queries screen geometry during construction, and a process that
is not yet DPI-aware receives virtualised numbers that stay wrong for the rest of its life.

Selection overlay arrives in M3. Until then the hotkey captures the whole desktop, which is
the click-free fallback path that survives into v1 anyway.
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
    app: QApplication, flow: CaptureFlow, tray: Tray, instance: SingleInstance
) -> GlobalHotkey:
    """Connect the tray, the second-launch channel, and the hotkey to the capture flow.

    Returns the hotkey so the caller can register it and decide how to report failure.
    """
    tray.capture_requested.connect(flow.capture_desktop)
    def on_second_launch(_payload: bytes) -> None:
        flow.capture_desktop()

    instance.command_received.connect(on_second_launch)

    hotkey = GlobalHotkey(parent=app)
    app.installNativeEventFilter(hotkey)
    hotkey.triggered.connect(flow.capture_desktop)

    def shutdown() -> None:
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
    flow = CaptureFlow(
        service=CaptureService(backend=MssBackend()),
        settings=settings,
        reporter=tray.notify,
    )

    hotkey = wire(app, flow, tray, instance)
    try:
        hotkey.register(parse_hotkey(settings.hotkey))
    except (HotkeyError, ValueError) as error:
        # Never swallowed: a hotkey that does nothing, with no error shown, is the worst
        # failure mode this application has.
        tray.notify("Hotkey unavailable", str(error), is_error=True)

    tray.show()
    tray.notify(APP_NAME, f"Ready. Press {settings.hotkey} to capture.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
