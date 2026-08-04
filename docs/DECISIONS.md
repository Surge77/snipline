# Decision Records

Short records of choices that would otherwise be re-litigated. Each states what was chosen, what
was rejected, and what would justify revisiting.

---

## D1 — PySide6, not PyQt6

**Chosen:** PySide6 (Qt for Python, official, LGPL).

**Rejected:** PyQt6 (Riverbank, GPL or paid commercial licence).

The APIs are near-identical; the licences are not. PyQt6 under the GPL would force this project and
anything distributing its binary to be GPL. PySide6 under the LGPL allows a closed or permissively
licensed binary provided Qt stays dynamically linked — which is the default for both PyInstaller
and Nuitka.

**Revisit if:** never, unless a PySide6 bug has no workaround. This is the single most
consequential dependency choice in the project.

---

## D2 — Toolkit: Qt, not Electron or Tauri

**Chosen:** Qt via PySide6.

**Rejected:** Electron, Tauri, and any web-based shell.

The stated purpose of the project is OS-boundary work — overlay windows, DPI handling, global
hotkeys, monitor geometry. A web shell abstracts away exactly the layer that makes the project
worth building, and costs 100 MB+ of bundle to do it. Qt gives direct access to native window
flags, per-screen device pixel ratios, and the scene graph used by the editor.

Python was chosen over C++ for iteration speed and because the surrounding tooling (pytest,
pyright, ruff) is already familiar. The performance-sensitive paths are pixel copies inside `mss`
and Qt, not Python-level loops.

---

## D3 — Capture via `mss`, not `PIL.ImageGrab` or WinRT

**Chosen:** `mss` — thin `ctypes` wrapper over GDI `BitBlt`, roughly 5–15 ms per monitor, returns a
raw BGRA buffer.

**Rejected — `PIL.ImageGrab`:** several times slower and historically careless about DPI, which is
the exact axis this project cares about.

**Deferred — Windows Graphics Capture (WinRT):** more correct for HDR content and for windows that
opt out of GDI capture, but a substantially larger integration. Revisit if HDR captures come out
visibly wrong, which is the symptom that would justify the cost.

---

## D4 — Global hotkey via `RegisterHotKey`, not a keyboard hook

**Chosen:** Win32 `RegisterHotKey` with a hidden message window, plus a Qt native event filter for
`WM_HOTKEY`.

**Rejected — `QShortcut`:** only fires when the application has keyboard focus. A screenshot tool
is used while something *else* is focused, so this cannot work by construction.

**Rejected — the `keyboard` PyPI package (and `SetWindowsHookEx` generally):** installs a
low-level global keyboard hook that observes every keystroke system-wide. That is far more
privilege than one hotkey requires, needs elevation in some configurations, and is routinely
quarantined by endpoint protection — a fatal property for a tool people are meant to install.

`RegisterHotKey` registers exactly one combination and receives nothing else. The tradeoff is that
registration fails if another application already owns the combination; that failure is surfaced in
the UI with a rebind prompt rather than swallowed.

---

## D5 — Freeze the desktop before showing the overlay

**Chosen:** capture the full virtual desktop first, then display that frozen pixmap in the overlay.

**Rejected:** showing a transparent overlay over the live desktop and capturing after selection.

The rejected approach has two unfixable problems: the overlay's own dimming appears in the output,
and taking focus dismisses any open menu, tooltip, or hover state the user was trying to capture.
Freezing first solves both, and makes selection instant since no pixels are read during the drag.

---

## D6 — Editor as a scene graph, not raster painting

**Chosen:** `QGraphicsScene` with one item per annotation; flatten once at export.

**Rejected:** painting strokes directly into a `QImage`.

Raster painting makes undo a matter of snapshotting the entire image per operation — memory grows
with edit count, and on a 4K capture each snapshot is tens of megabytes. It also makes every
annotation permanent the instant it is drawn.

The scene graph costs moderate extra complexity and buys cheap undo, re-editable annotations,
z-ordering, and hit testing. Both undo and re-editability are core features rather than extras, so
the complexity is bought deliberately.

---

## D7 — Redaction is pixelate and solid fill; blur is cosmetic

**Chosen:** ship pixelate and solid fill as redaction tools, with solid fill as the default. Blur
exists but is labelled a cosmetic effect, not a privacy tool.

**Rejected:** presenting Gaussian blur as redaction, which is what the original one-line spec
implied and what many tools do.

Blurred text is frequently recoverable: an attacker who knows or guesses the font, size, and blur
radius can render candidate strings, apply the same blur, and compare against the image. This has
exposed real credentials and personal data in published screenshots. A privacy feature that fails
against a motivated reader is worse than no feature, because users rely on it.

---

## D8 — No layered project format in v1

**Chosen:** export is always flattened.

**Rejected:** a `.snipline` file preserving annotation layers for later editing.

A layered file necessarily retains the original pixels underneath every redaction. Sharing that
file leaks precisely the data the redaction was applied to hide, and users would reasonably assume
otherwise. If layering is added later it must either strip redacted regions destructively at save
time or carry a loud, unavoidable warning — that design work is the price of the feature.

---

## D9 — Capture behind a `Protocol`, with a fake for tests

**Chosen:** `CaptureBackend` protocol; `MssBackend` real, `FakeBackend` synthetic.

This is the seam that keeps the test suite headless. Geometry, DPI conversion, cropping, undo, and
export are all testable in CI with `QT_QPA_PLATFORM=offscreen` and zero real screen access — the
same principle as stubbing at the network boundary rather than mocking HTTP libraries.

The corollary: do **not** write tests that assert `ctypes` was called with particular arguments.
Such tests break on every refactor and have never caught a real bug. The genuinely untestable
surface — `RegisterHotKey`, the system clipboard, real monitor enumeration — is covered by a manual
checklist and by dogfooding from M3 onward.

---

## D10 — PyInstaller `--onedir`, not `--onefile`

**Chosen:** `--onedir`.

`--onefile` unpacks the entire bundle to a temporary directory on every launch, adding seconds of
startup. For a tool whose whole value proposition is sub-second response to a hotkey, that is
self-defeating. An installer can hide the directory from the user; startup latency cannot be
hidden.

**Revisit if:** Nuitka produces a genuinely fast single binary, in which case it replaces
PyInstaller entirely rather than changing this flag.

---

## D11 — No network access in v1

**Chosen:** no upload, no telemetry, no update check.

A screenshot tool sees whatever is on screen, which is among the most sensitive data on a machine.
Shipping with zero network capability makes that guarantee trivially auditable — there is no code
path to inspect. Adding any network feature later changes the tool's trust model and requires its
own decision record, not a quiet dependency addition.

---

## D12 — Dark chrome only, not a theme that follows the OS

**Chosen:** one committed dark surface for every window and the overlay.

A screenshot annotator draws its chrome over arbitrary pixels it did not choose. A theme following
the OS would put light chrome over a light screenshot, which is exactly when the toolbar most needs
to separate from the content underneath it. One surface colour is a smaller compromise than a
contrast guarantee that only holds half the time.

The accent is the blue the selection border already used, so the overlay and the editor read as one
application rather than two that happen to launch together.

**Revisit if:** Windows exposes a reliable per-window backdrop that keeps chrome legible over
arbitrary content, or users on light desktops report the editor reads as a foreign application.

---

## D13 — Icons drawn in code; the `.ico` is a build input, not a runtime file

**Chosen:** every icon the running application shows is drawn with QPainter from one vector
definition in `ui/mark.py` and `ui/icons.py`. `assets/snipline.ico` exists, is committed, and is
consumed only by `snipline.spec`.

A missing icon resource is the classic PyInstaller failure: it works in development, where the file
sits next to the source, and breaks in the bundle, where it does not. Drawing the glyphs sidesteps
it for shapes this simple.

The executable's own icon cannot be procedural — PyInstaller needs a real `.ico` at build time. That
turns out not to weaken anything, and the distinction is the whole decision: **build-time assets are
embedded into the exe's resource table and never opened at runtime, so they cannot fail the way a
runtime resource can.** The file is deliberately absent from the spec's `datas`; shipping it beside
the exe would make it a runtime file again for no benefit.

It is committed rather than generated during the build so a fresh clone can run `pyinstaller
snipline.spec` without a Qt display first. Regenerate with `python -m snipline.tools.make_icons`.

**Revisit if:** the icon set grows past what is readable as geometry, at which point SVG assets and
an explicit bundling story are worth the risk that this avoids.

---

## D14 — The magnifier loupe samples nearest-neighbour

**Chosen:** no smoothing when magnifying, and a one-pixel outlined crosshair rather than a filled
one.

`config.show_magnifier` was persisted from M6 onward while nothing drew a loupe; the setting toggled
nothing until it was built. Now that it exists, the sampling rule matters more than it looks: a
smoothed magnifier is a picture of what the pixels nearly are. This application's claim is that the
region selected is the region captured, and the loupe exists so a user can put an edge on the right
pixel. Interpolating there is the same category of error as dimming the selected area — chrome
misrepresenting the capture.

The frozen pixmap is converted to a `QImage` once, at construction. `QPixmap::toImage` copies off
the graphics backend, and doing that per pointer-move to read one pixel's colour is a full-screen
copy on every event of a drag.
