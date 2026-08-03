"""What happens when the hotkey is pressed.

Deliberately not a Qt class and deliberately not aware of the tray. It takes a capture
service, settings, and somewhere to report to, so the entire M2 user journey -- hotkey to
written file to notification -- runs in tests with no tray, no hotkey, and no real screen.

From M3 this grows a branch that shows the selection overlay instead of writing the whole
desktop; the full-desktop path stays as the click-free fallback.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from snipline.capture.frame import Frame
from snipline.capture.service import CaptureService
from snipline.config import DefaultSink, ExportFormat, Settings
from snipline.export.clipboard import copy_to_clipboard
from snipline.export.encode import save_frame

__all__ = ["CaptureFlow", "CaptureOutcome", "build_filename", "default_save_directory"]

FILENAME_PREFIX = "Snipline"
TIMESTAMP_FORMAT = "%Y-%m-%d %H%M%S"

# Reporter takes (title, message, is_error). Kept as a plain callable so the tray, a test
# spy, and the CLI can all satisfy it without a shared base class.
Reporter = Callable[[str, str, bool], None]


class CaptureOutcome:
    """Result of one capture attempt. Not an exception: a failed capture is a normal
    outcome to report to the user, not a crash to propagate into the Qt event loop."""

    __slots__ = ("error", "path")

    def __init__(self, path: Path | None = None, error: str | None = None) -> None:
        self.path = path
        self.error = error

    @property
    def succeeded(self) -> bool:
        return self.error is None


def default_save_directory() -> Path:
    """Where captures go when settings do not say otherwise."""
    return Path.home() / "Pictures" / FILENAME_PREFIX


def build_filename(moment: datetime, export_format: ExportFormat) -> str:
    """A sortable, human-readable filename.

    Colons are not usable in Windows filenames, which rules out ISO-8601 time directly.
    """
    return f"{FILENAME_PREFIX} {moment.strftime(TIMESTAMP_FORMAT)}.{export_format.value}"


def _unique(destination: Path) -> Path:
    """Avoid overwriting an existing capture.

    Two captures inside the same second are easy to trigger by holding the hotkey, and
    silently replacing the first one destroys the user's data.
    """
    if not destination.exists():
        return destination

    for counter in range(2, 1000):
        candidate = destination.with_stem(f"{destination.stem} ({counter})")
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"too many captures with the same name: {destination}")


class CaptureFlow:
    """Capture the desktop and write it where the settings say."""

    def __init__(
        self,
        service: CaptureService,
        settings: Settings,
        reporter: Reporter | None = None,
        clock: Callable[[], datetime] = datetime.now,
    ) -> None:
        self._service = service
        self._settings = settings
        self._reporter = reporter
        self._clock = clock

    def capture_desktop(self) -> CaptureOutcome:
        """Grab the whole virtual desktop, write it, and report the result.

        Every foreseeable failure -- a disconnected monitor mid-capture, a read-only save
        directory, a full disk -- is turned into a reported outcome. An exception escaping
        here would reach the Qt event loop from a hotkey handler and take the app down
        while it sits in the tray.
        """
        try:
            frame = self._service.grab_desktop()
            written = self._write(frame)
        except (OSError, ValueError, RuntimeError) as error:
            outcome = CaptureOutcome(error=str(error))
            self._report("Capture failed", str(error), is_error=True)
            return outcome

        self._report("Capture saved", str(written), is_error=False)
        return CaptureOutcome(path=written)

    def deliver(self, frame: Frame) -> CaptureOutcome:
        """Send an already-captured frame to the configured destination.

        The overlay path lands here with a frame cropped out of the frozen desktop, so no
        second capture is taken and the pixels stay the ones from before the overlay
        appeared (D5).
        """
        try:
            if self._settings.default_sink is DefaultSink.CLIPBOARD:
                if not copy_to_clipboard(frame):
                    raise RuntimeError("no clipboard is available")
                size = f"{frame.width} x {frame.height}"
                self._report("Copied to clipboard", size, is_error=False)
                return CaptureOutcome()

            written = self._write(frame)
        except (OSError, ValueError, RuntimeError) as error:
            self._report("Capture failed", str(error), is_error=True)
            return CaptureOutcome(error=str(error))

        self._report("Capture saved", str(written), is_error=False)
        return CaptureOutcome(path=written)

    def _write(self, frame: Frame) -> Path:
        directory = self._settings.save_directory or default_save_directory()
        destination = _unique(
            directory / build_filename(self._clock(), self._settings.export_format)
        )
        return save_frame(
            frame,
            destination,
            export_format=self._settings.export_format,
            quality=self._settings.jpeg_quality,
        )

    def report_failure(self, message: str) -> CaptureOutcome:
        """Report a failure raised before there was anything to deliver."""
        self._report("Capture failed", message, is_error=True)
        return CaptureOutcome(error=message)

    def _report(self, title: str, message: str, *, is_error: bool) -> None:
        if self._reporter is not None:
            self._reporter(title, message, is_error)
