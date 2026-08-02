# Snipline

A Windows screenshot tool with a real annotation editor. Global hotkey → region select across
any monitor → draw arrows, boxes, text, step badges, and redaction → clipboard or file.

Built to be correct on the setups most hobby screenshot tools break on: **multi-monitor at mixed
DPI** (a 4K 150% panel next to a 1080p 100% panel), negative-coordinate monitor layouts, and
per-monitor scaling changes while the app is running.

> **Status:** scaffolding. Nothing capturing yet. See [`docs/PLAN.md`](docs/PLAN.md) for the
> milestone-by-milestone build order and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the
> layer design.

---

## Why this exists

Screenshot tools are a solved problem in the sense that many exist, and an unsolved problem in the
sense that most of them get multi-monitor DPI wrong. This project takes the position that the
interesting engineering is not the drawing tools — it's the coordinate math at the OS boundary,
and proving it works with numbers rather than screenshots of screenshots.

## Target numbers

These are the acceptance criteria for v1. The README will state measured p50/p95 values here once
the benchmark harness lands (see [`docs/BENCHMARKS.md`](docs/BENCHMARKS.md)).

| Span | Target (p95) | Measured |
|---|---|---|
| hotkey press → overlay visible | < 120 ms | _pending_ |
| region release → editor ready | < 80 ms | _pending_ |
| export → clipboard populated | < 60 ms | _pending_ |
| monitors handled at mixed DPI | 3 @ 100/125/150% | _pending_ |

The first row is the one users feel. Everything else is comfort.

## Planned features (v1)

- Global hotkey capture that works while another application has focus
- Frozen-frame region selection overlay with a pixel-accurate magnifier loupe
- Vector annotation editor with full undo/redo: arrow, rectangle, ellipse, freehand, text,
  numbered step badges
- Redaction: pixelate and solid fill (see the security note below)
- Export to clipboard or file (PNG, WebP, JPEG)
- System tray, single-instance enforcement, configurable hotkey

## Redaction is not blur

Snipline ships **pixelate** and **solid fill** as its redaction tools, and solid fill is the
default. Gaussian blur is offered only as a cosmetic effect and is labelled as such in the UI.

Blurred text is frequently recoverable. An attacker who knows the font, size, and blur radius can
render candidate strings, apply the same blur, and compare — which has exposed real credentials,
account numbers, and personal data in published screenshots. Any tool that presents blur as a
privacy feature is making a promise it cannot keep.

Snipline also flattens all annotations into the output image on export. There is no layered project
format in v1, deliberately: a layered file would still contain the original unredacted pixels
underneath the redaction, so sharing it would leak exactly the data the user tried to hide.

## Stack

Python 3.11+ · PySide6 (Qt 6, LGPL) · mss · Pillow · NumPy · ctypes for Win32

Rationale for each choice, including the ones rejected, is recorded in
[`docs/DECISIONS.md`](docs/DECISIONS.md).

## Development

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt

pytest              # headless, no real screen capture
pyright             # type gate
ruff check .        # lint
```

Tests never touch the real screen. Capture is behind a `CaptureBackend` protocol with a
`FakeBackend` implementation, so the geometry, DPI, undo, and export logic is fully testable in CI
with `QT_QPA_PLATFORM=offscreen`.

## Platform support

Windows 10/11 only in v1. The Win32-specific code is confined to `src/snipline/platform/`, which
is the seam a future macOS or Linux port would implement — but no such port is planned or promised.

## Licence

MIT. See [LICENSE](LICENSE).

PySide6 is LGPL and is used as a dynamically linked dependency, which is what keeps this project
free to relicence or ship as a binary. Do not swap it for PyQt6 without reading
[`docs/DECISIONS.md`](docs/DECISIONS.md) first.
