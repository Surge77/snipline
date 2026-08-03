# Manual Test Checklist

Covers what cannot be unit tested: OS-boundary behaviour with no meaningful seam. Run before
tagging any release. Record pass/fail and the machine configuration.

Writing mock-heavy tests for these — asserting that `ctypes` was called with certain arguments —
would break on every refactor and catch nothing. Hence a checklist.

## Capture path (M1)

Everything here runs through `snipline-grab`, which has no UI. When a capture looks wrong
anywhere else in the app, run these first: they say whether the bug is in M1 or in something
built on top of it.

- [ ] `snipline-grab --list` reports every connected monitor with correct physical bounds and
      scale percentages, matching Windows' own Display settings.
- [ ] On a scaled monitor, the reported size is the **physical** panel resolution, not the
      virtualised logical one — a 1920×1080 panel at 125% must report 1920×1080, not
      1536×864. A wrong number here means DPI awareness was declared too late.
- [ ] `snipline-grab --all` writes a PNG whose dimensions equal the virtual desktop, with each
      monitor's content in the right place and no black bands between them.
- [ ] `snipline-grab --monitor N` writes exactly that panel, for every N.
- [ ] `snipline-grab --region L,T,W,H` on a monitor with a **negative** origin crops the
      intended area rather than one offset by a whole monitor.
- [ ] The written image is real screen content, not blank or fully transparent (the GDI
      zero-alpha trap).
- [ ] An off-desktop region and an unknown monitor index both fail with a one-line message and
      exit code 1 — no traceback.

## Hotkey

- [ ] Hotkey fires while a full-screen application has focus.
- [ ] Hotkey fires while a UAC-elevated application has focus, or fails visibly with an explanation
      (an unelevated process cannot receive hotkeys over an elevated foreground window).
- [ ] Registering a combination already owned by another app shows an error and offers a rebind.
      It must not fail silently.
- [ ] Rebinding takes effect without restarting the app.
- [ ] Hotkey is released on quit; relaunching registers cleanly.
- [ ] Pressing the hotkey while a *different* application has focus writes a capture — this is
      the whole point of `RegisterHotKey` over `QShortcut` (D4) and cannot be verified while
      Snipline itself is focused.
- [ ] The tray balloon names the written file, and the file is where it says.
- [ ] Quitting from the tray menu leaves no registered hotkey behind: relaunching must not
      report the combination as already taken *by Snipline itself*.

## Multi-monitor

Run on each of the configurations `C1`–`C5` defined in `BENCHMARKS.md`.

- [ ] Overlay covers every monitor with no gap or double-dimming on the seam.
- [ ] A selection starting on one monitor and ending on another produces one correct region.
- [ ] Output dimensions equal the selected region in physical pixels on the high-DPI monitor.
- [ ] Selection on a monitor with negative coordinates crops the right area, not an offset one.
- [ ] Hot-plugging a monitor between two captures is handled — monitor state is re-enumerated, not
      cached from startup.
- [ ] Changing display scaling while the app runs does not corrupt the next capture.

## Capture content

- [ ] An open context menu is captured (this is the freeze-then-overlay guarantee).
- [ ] A tooltip or hover state is captured.
- [ ] The app's own dimming overlay never appears in the output.
- [ ] A video playing in a browser captures a frame rather than black.
- [ ] `Esc` cancels with nothing written to clipboard or disk.

## Editor

- [ ] Undo/redo covers every tool, in mixed order, without leaving orphaned items.
- [ ] A redaction dragged across the image re-processes the newly covered area rather than smearing
      the originally sampled pixels.
- [ ] Text tool handles IME input and emoji.
- [ ] Editor opens on the monitor the selection was made on.

## Export

- [ ] Clipboard paste into Word, Slack, Paint, and a browser all produce the same image.
- [ ] A capture with transparency pasted into an app that discards alpha composites predictably
      rather than producing black fringing.
- [ ] File export at 4K produces full-resolution output, not a view-resolution downscale.
- [ ] Exported file contains no recoverable pixels beneath a redaction — verify by opening the
      output in an image editor and inspecting the redacted region.

## Packaging

- [ ] The PyInstaller build runs on a clean Windows VM with no Python installed.
- [ ] Qt platform plugins load (a missing `platforms/qwindows.dll` fails at startup with an opaque
      error — check explicitly).
- [ ] Windows Defender does not quarantine the executable.
- [ ] Startup to tray-ready is under one second on the clean VM.

## Single instance

- [ ] Launching a second time triggers a capture in the running instance and exits.
- [ ] Killing the process leaves no stale lock that blocks the next launch.
