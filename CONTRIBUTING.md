# Contributing

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt -r requirements-dev.txt
```

## Gates

All three must pass before a PR is opened. CI enforces them.

```bash
pytest            # headless; QT_QPA_PLATFORM=offscreen is set by pytest.ini
pyright           # strict mode
ruff check .
```

A change that runs but fails the type gate is not finished.

## Rules

- **300-line hard limit per file.** Split by responsibility before adding more.
- **No real screen capture in tests.** Use `FakeBackend`. If a test needs the real screen, it
  belongs in `docs/MANUAL_TESTS.md` instead.
- **No Win32 calls outside `src/snipline/platform/`.** That package is the only thing standing
  between this codebase and an untestable one.
- **Never mix logical and physical coordinates.** Use the distinct types in `platform/geometry.py`
  and convert only at explicit boundaries.
- **New annotation tool = one new file** under `editor/tools/` plus a registration. If it forces a
  change to the editor, fix the tool interface rather than working around it.
- No commented-out code. Comments explain *why*, never *what*.

## Commits

Conventional commits: `<type>(<scope>): <description>`

```
feat(capture): add per-monitor DPI scale resolution
fix(overlay): correct crop origin on negative-coordinate monitors
docs(plan): record the freeze-then-overlay rationale
```

Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`.

One logical change per commit. Branch names: `feature/…`, `fix/…`.

## Pull requests

Never commit directly to `main`. Branch, open a PR, and let CI run.

A PR touching capture, geometry, or DPI must state which monitor configurations
(`C1`–`C5` in `docs/BENCHMARKS.md`) it was verified against. "Works on my machine" is
specifically not sufficient for this project, since single-monitor machines cannot reproduce the
entire class of bugs the project exists to avoid.

## Design decisions

If you want to change something recorded in `docs/DECISIONS.md`, open an issue arguing against the
recorded rationale first. Those records exist so the same debates are not repeated silently in code
review.

## Security-relevant changes

Anything touching redaction, export, or the introduction of network access needs explicit
discussion. Redaction that fails against a motivated reader is worse than no redaction, because
users rely on it. See D7, D8, and D11 in `docs/DECISIONS.md`.
