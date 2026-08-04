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
- [ ] Arrow keys nudge the selection edge by exactly one physical pixel; Shift+arrow moves the
      opposite edge.
- [ ] The size readout shows **physical** pixels — it must match the dimensions of the image
      that actually lands on the clipboard, not the logical size on a scaled monitor.
- [ ] Clicking without dragging captures the whole monitor under the cursor.
- [ ] Quitting while the overlay is open leaves no frozen image stuck on screen.

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

## Editor (M4)

- [ ] Ctrl+Z and Ctrl+Y (and Ctrl+Shift+Z) undo and redo arrows in mixed order.
- [ ] An arrow drawn while the window is scrolled lands under the cursor, not offset by the
      scroll position.
- [ ] Saving twice from one editor session produces two files, not one overwritten file.
- [ ] A 4K capture saved from the editor is 4K in the file — not the size of the window it
      was displayed in.
- [ ] Closing the editor with unsaved annotations does not crash or leave a stray window.

## Tools and redaction (M5)

- [ ] Every tool in the toolbar draws, and each annotation undoes with one Ctrl+Z.
- [ ] Colour and width changes affect the *next* annotation, not ones already drawn.
- [ ] Text tool accepts IME composition (Japanese/Chinese input) and emoji.
- [ ] A solid or pixelate redaction dragged across the image re-processes the area it now
      covers — inspect the vacated area, which must show the original capture again.
- [ ] Open an exported file in an image editor and confirm no recoverable pixels remain
      beneath a solid or pixelate redaction.
- [ ] Blur is labelled as a cosmetic effect everywhere it appears, never as redaction (D7).

## Export, settings, packaging (M6)

- [ ] A rebound hotkey and a chosen save directory both survive a restart.
- [ ] Corrupting the settings (registry or INI) by hand still lets the app start, falling back
      to defaults for the damaged values only.
- [ ] The `--onedir` build launches on a clean Windows VM with no Python installed.
- [ ] Startup to tray-ready is under one second on that VM.
- [ ] Windows Defender does not quarantine the executable (UPX is deliberately off; packed
      binaries are a common false positive).
- [ ] `python -m snipline.tools.benchmark` runs on a multi-monitor mixed-DPI machine and the
      results are recorded in `docs/BENCHMARKS.md` against the right configuration ID.

## Overlay chrome and item editing

These cover behaviour that only exists on a real screen. The geometry behind the first three
is unit tested; what they are checking is that the geometry reaches the display intact.

- [ ] The selection's own bottom row and right column are **not** dimmed — drag a selection
      over a sharp horizontal edge and confirm the bottom row inside the border matches the
      captured output rather than the darker surround.
- [ ] The selection border sits outside the selection: the pixels it is aligned against stay
      visible while dragging.
- [ ] Dragging a selection quickly leaves no stale border, band, or size label behind. Drag
      out, back, and across the screen; the only chrome visible is the current selection's.
      Repaints are now partial, so anything left over shows up here and nowhere else.
- [ ] The size label stays legible when the selection is against the top edge, where it flips
      to sit inside the selection.
- [ ] Every monitor gets an overlay window on a mixed-DPI desktop. Screens are matched to
      monitors by nearest origin within a tolerance, so a missing overlay on one panel means
      the tolerance is wrong, not that the panel is unsupported.
- [ ] In the editor, the Select tool picks up a placed annotation and moves it; the drawing
      tools do not.
- [ ] A redaction moved with the Select tool re-processes the area it now covers, and the
      area it vacated shows the original capture again (D7).
- [ ] With the Select tool, clicking into a text annotation positions the caret.
- [ ] Delete removes the selected annotations and one Ctrl+Z brings them back.

## Appearance and the magnifier

The loupe and the chrome are geometry-tested (`tests/overlay/test_chrome.py`) but only ever
*look* right on a real screen, and the mixed-DPI cases below cannot be reached on the
single-display development machine at all.

- [ ] The executable shows the Snipline mark in Explorer, the taskbar, and Alt-Tab — not the
      generic Python or default-application icon. Check at both small and extra-large icon
      sizes in Explorer, which read different images out of the `.ico`.
- [ ] The tray icon is legible against a **light** taskbar as well as a dark one, and is not a
      filled square.
- [ ] Editor chrome is dark throughout: no light native spin box, combo drop-down, menu, or
      tooltip left over from the Windows style. These are what the Fusion style exists to
      prevent, and a light one means the style was applied too late.
- [ ] The selected tool is visibly distinct from the unselected ones at a glance, without
      reading the labels.
- [ ] Every tool is reachable without a toolbar overflow chevron at the default window size —
      in particular the redaction row, which is the group that must never be hidden.
- [ ] The loupe follows the pointer and flips to stay fully on screen at all four edges and all
      four corners.
- [ ] Magnified pixels are hard squares, not a smooth blur (D14), and the readout's colour
      matches the pixel under the crosshair — check against a known flat colour.
- [ ] The coordinates in the readout are **physical** pixels: on a 150% monitor they must match
      what `snipline-grab --list` reports, not the logical numbers.
- [ ] On a mixed-DPI desktop the loupe magnifies the pixels actually under the pointer on
      *each* monitor. A wrong scale factor here shows up as the loupe drifting further from the
      pointer the further right it moves.
- [ ] The hint pill reads in full before the first drag and disappears once dragging starts. It
      must not be overlapped by the loupe.
- [ ] No handle, border, or readout covers any part of the selected area — compare the pixels
      inside the selection against the exported file.
