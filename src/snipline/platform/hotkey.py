"""Global hotkey registration (D4).

``RegisterHotKey`` receives exactly one combination and nothing else, which is why it is used
here instead of a low-level keyboard hook -- see D4 for the full argument.

Registration is done against the *thread* (a null window handle) rather than a hidden message
window. ``WM_HOTKEY`` is then posted to the thread's message queue, which Qt's event
dispatcher pumps and hands to installed native event filters. A hidden window would work
identically and cost an extra HWND to create, own, and destroy.

The failure path is the important part of this module. A hotkey that does nothing is the
worst failure mode this app has: the user presses it, nothing happens, and there is no error
to search for. So registration failure raises with a specific reason, and the caller is
expected to show it.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QAbstractNativeEventFilter, QByteArray, QObject, Signal

from snipline.platform.keys import HotkeySpec, format_hotkey

__all__ = ["GlobalHotkey", "HotkeyError", "describe_registration_failure"]

WM_HOTKEY = 0x0312
ERROR_HOTKEY_ALREADY_REGISTERED = 1409
DEFAULT_HOTKEY_ID = 1


class HotkeyError(RuntimeError):
    """Registration failed. Carries a reason fit to show to a user."""


def describe_registration_failure(spec: HotkeySpec, error_code: int) -> str:
    """Turn a Win32 error code into something a user can act on."""
    combination = format_hotkey(spec)
    if error_code == ERROR_HOTKEY_ALREADY_REGISTERED:
        return (
            f"{combination} is already registered by another application. "
            f"Choose a different combination in Settings."
        )
    return f"Windows refused to register {combination} (error {error_code})."


class GlobalHotkey(QObject, QAbstractNativeEventFilter):
    """One registered combination, re-emitted as a Qt signal.

    Install on the application with ``app.installNativeEventFilter(hotkey)`` before calling
    ``register``.
    """

    triggered = Signal()

    def __init__(self, hotkey_id: int = DEFAULT_HOTKEY_ID, parent: QObject | None = None) -> None:
        QObject.__init__(self, parent)
        QAbstractNativeEventFilter.__init__(self)
        self._hotkey_id = hotkey_id
        self._registered: HotkeySpec | None = None

    @property
    def registered(self) -> HotkeySpec | None:
        return self._registered

    def register(self, spec: HotkeySpec) -> None:
        """Claim ``spec`` system-wide, replacing any previous registration.

        Raises ``HotkeyError`` when Windows refuses -- most often because another
        application already owns the combination.
        """
        if sys.platform != "win32":
            raise HotkeyError("global hotkeys are Windows-only")

        import ctypes

        self.unregister()

        # use_last_error is required: without it ctypes does not capture GetLastError()
        # around the call, and the code read afterwards is whatever unrelated Win32 call
        # happened to run last -- which would turn "already registered" into noise exactly
        # when the message needs to be precise.
        user32 = ctypes.WinDLL("user32", use_last_error=True)  # type: ignore[attr-defined]
        if not user32.RegisterHotKey(None, self._hotkey_id, spec.modifiers, spec.vk):
            raise HotkeyError(describe_registration_failure(spec, ctypes.get_last_error()))
        self._registered = spec

    def unregister(self) -> None:
        """Release the combination. Safe to call when nothing is registered."""
        if self._registered is None or sys.platform != "win32":
            self._registered = None
            return

        import ctypes

        ctypes.windll.user32.UnregisterHotKey(None, self._hotkey_id)  # type: ignore[attr-defined]
        self._registered = None

    def nativeEventFilter(  # noqa: N802 - Qt's camelCase override
        self,
        # Widened to match Qt's own stub exactly; a narrower type is an invalid override.
        eventType: QByteArray | bytes | bytearray | memoryview[int],  # noqa: N803 - Qt name
        message: int,
    ) -> tuple[bool, int]:
        """Translate ``WM_HOTKEY`` into ``triggered``.

        Returns ``(False, 0)`` in every case: the message is observed, never consumed, so
        Qt's own handling of the message queue is left intact.
        """
        if bytes(eventType.data() if isinstance(eventType, QByteArray) else eventType) != (
            b"windows_generic_MSG"
        ):
            return (False, 0)

        import ctypes
        from ctypes import wintypes

        class MSG(ctypes.Structure):
            _fields_ = (
                ("hwnd", wintypes.HWND),
                ("message", wintypes.UINT),
                ("wParam", wintypes.WPARAM),
                ("lParam", wintypes.LPARAM),
                ("time", wintypes.DWORD),
                ("pt", wintypes.POINT),
            )

        msg = ctypes.cast(int(message), ctypes.POINTER(MSG)).contents
        if msg.message == WM_HOTKEY and msg.wParam == self._hotkey_id:
            self.triggered.emit()
        return (False, 0)
