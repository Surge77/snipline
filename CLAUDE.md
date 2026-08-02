# Snipline — Project Instructions

> Overrides `~/.claude/CLAUDE.md` and `~/.claude/rules/*` where they conflict.

## Stack

Python 3.11+ only. PySide6 (Qt 6) desktop app for Windows. No web server, no FastAPI, no frontend
framework.

- Type gate: `pyright` (`pyrightconfig.json`, strict)
- Tests: `pytest` (`pytest.ini`, `QT_QPA_PLATFORM=offscreen`)
- Lint: `ruff`
- Deps: `requirements.txt` / `requirements-dev.txt`, pinned exact

## Read first

`docs/ARCHITECTURE.md` for layering, `docs/PLAN.md` for milestone order, `docs/DECISIONS.md` before
proposing any stack or design change. The decision records exist to prevent re-litigating settled
choices.

## Hard rules

- **Never commit or push directly to `main`.** Branch first, PR always.
- **300-line limit per file.** Split by responsibility.
- **Win32 / `ctypes` only inside `src/snipline/platform/`.** Nothing else imports them. This is
  what keeps the codebase headless-testable.
- **No real screen capture in tests.** Everything goes through `CaptureBackend`; tests use
  `FakeBackend`. Untestable OS-boundary behaviour goes in `docs/MANUAL_TESTS.md`, not into a
  mock-heavy test.
- **Never mix logical and physical coordinates.** `LogicalRect` and `PhysicalRect` in
  `platform/geometry.py` are distinct types on purpose. Convert only at explicit boundaries, using
  the owning screen's device pixel ratio.
- **DPI awareness is declared before `QApplication` is constructed.** Declared late, Windows
  returns virtualised coordinates and every capture is silently wrong.
- **No network code.** v1 has no upload, telemetry, or update check (D11). Adding any requires a new
  decision record, not a quiet import.
- **Redaction means pixelate or solid fill.** Blur is cosmetic and must stay labelled as such (D7).
  Export is always flattened (D8).

## Agent routing

| Situation | Use |
|---|---|
| Plan a feature / refactor (>3 files) | `planner`, then `architect` if structural |
| Python code review | `python-reviewer` |
| Tests-first / coverage | `tdd-guide` |
| pyright or build failure | `build-error-resolver` |
| Runtime bug (wrong output, not a crash) | `debugger` |
| Redaction, export, clipboard, or any new dependency | `security-reviewer` |
| New pin in `requirements*.txt` | `dependency-auditor` |
| Capture hot path | `performance-auditor` |
| Read-only "where is X" | `caveman:cavecrew-investigator` or `Explore` |

Do not use non-Python reviewers or build resolvers, `fastapi-reviewer`, or any web/research agent —
wrong stack for this project.

## Milestone discipline

Work the milestones in `docs/PLAN.md` in order. Each is independently shippable. Do not start the
next until the current one is merged with green tests. M1 (capture correctness) carries the whole
project — most bugs that later look like editor bugs are M1 coordinate bugs.
