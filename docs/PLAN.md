# Plan

Build order, and the reason for the order. Each stage is one commit.

| # | Stage | Files | Why here |
|---|-------|-------|----------|
| 0 | Skeleton | `LICENSE`, `pyproject.toml`, `requirements-dev.txt`, `.gitattributes`, `.gitignore`, `.dockerignore`, `docs/PLAN.md` | Nothing else can be tested before the tooling metadata exists. |
| 1 | Patch engine | `kit/patching.py`, `tests/test_patching.py` | Every task is expressed as a patch. If the applier is wrong, every other result is meaningless. It has no dependency on the task framework, so it can be tested first in isolation. |
| 2 | Base library | `base/minishop/*.py`, `base/tests/*.py` | The base must be correct and green before anything is injected into it. |
| 3 | Task framework | `kit/paths.py`, `kit/workspace.py`, `kit/runner.py`, `kit/result.py`, `kit/cli.py`, `kit/scaffold.py` | Needs a base tree to copy and a patch engine to apply. Tasks cannot be written until a workspace can be built and verified. |
| 4 | Tasks | `tasks/001..005/**` | One task per stage: fix first, derive the defect, verify, add alternates, add traps. |
| 5 | Quality gate | `kit/selftest.py` | Only meaningful once at least one task exists. |
| 6 | Kit tests | `tests/test_*.py` | Tests the framework through its public surface, including the anti-cheat path. |
| 7 | Docs, Docker, CI | `README.md`, `docs/*`, `Dockerfile`, `.github/workflows/ci.yml` | Written last so every pasted output is real. |

## Risks and how they are handled

- **Patch applier drift** — the patches are generated from real files with `difflib`, and the
  applier is strict about context. Any drift fails loudly with the file and hunk number.
- **Verifier that only accepts one implementation** — every task ships two alternative valid
  solutions written in a genuinely different style, and `selftest` proves they pass.
- **Verifier that accepts a fake fix** — every task ships three or more tempting wrong fixes, and
  `selftest` proves they are rejected. `docs/DESIGN.md` also records a mutation check: weaken one
  assertion and show a wrong fix slipping through.
- **Flaky or slow tests** — no clocks, no randomness, no network, no sleeps. The performance task
  counts operations through an injected key object, never seconds.
- **Windows-only or POSIX-only paths** — only `pathlib`, only `python -m kit`, no shell scripts.
  Symlink tests skip themselves when the OS refuses to create a symlink.
- **Verifier tampering** — the solver's library is copied into a throw-away directory and the
  verifier files are copied fresh from the kit, so editing the workspace tests has no effect.
- **Scope risk** — the stretch refactor task (`006`) is attempted only after the five required
  tasks are green; the decision is recorded in `docs/DECISIONS.md`.
