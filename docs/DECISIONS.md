# Decisions

One line per judgment call, with the reason.

## Language and dependencies

- **Python 3.12 only.** The brief asks for it, and it gives `Path.is_relative_to`, `ast.end_lineno` and modern typing without back-compat shims.
- **Only `pytest==8.3.4` as a dev dependency.** Hypothesis was not needed: every property check is a seeded loop with a fixed corpus, which is easier to explain and has bounded runtime.
- **No runtime dependencies.** The kit, the base library and the verifiers are standard library only.
- **`ruff` configured but not required.** `pyproject.toml` carries the rules; CI does not fail if ruff is absent, per the brief.

## Repository shape

- **The library lives in `base/`, not at the repository root.** A workspace is then a clean copy of two folders, and the kit cannot accidentally ship its own tests into a solver's workspace.
- **`base/tests` is the visible suite and is never modified by a task.** That makes pass-to-pass a real safety net rather than a task-specific invention.
- **`inventory.py` and `csvio.py` are not touched by any task.** They exist so the base looks like a small real library and so the visible suite has breadth beyond the five defects.
- **Task folders are the unit of extension.** `new-task` creates the same layout as the hand-written tasks, and `status: draft` keeps incomplete work out of the gate.
- **Task ids are `NNN-kebab-case`.** The loader rejects anything else, so a typo cannot create a folder that is silently ignored.
- **`metadata.json` is not copied into a workspace.** It names the touched files, which is a hint.

## Patches and workspaces

- **A hand-written unified-diff applier, not `git apply` or `patch`.** The brief requires no external tools and Windows support; the applier is also unit-tested independently.
- **The applier checks every hunk against the file before writing anything.** A half-applied tree is worse than a clear failure.
- **Renames are rejected.** The kit never needs them, and supporting them would add a code path with no test value.
- **Patches and source files are LF via `.gitattributes`.** Windows checkouts still work because the applier normalises CRLF in patch text.
- **Workspaces are built in a temp directory and moved into place.** A failed build leaves no partial workspace.
- **`python -m kit build` defaults to `workspaces/<id>`, which is gitignored.** Demos do not dirty the repository.
- **Workspaces contain only `minishop/`, `tests/` and `task.md`.** No metadata, no verifier, no golden patch, no git history.
- **Feature tasks may have an empty `inject.patch`.** The starting point is the untouched base; the structure checker allows this only for `type: feature`.

## Verification

- **`allowed_paths` is `minishop/` for every task.** The brief's tasks all live in one module; expanding the editable surface would only create more ways to cheat.
- **Violations short-circuit before pytest runs.** A workspace that edited a test is rejected for that reason, not for a confusing import error.
- **The manifest is rebuilt from the task on every verification.** There is no cached baseline that could drift from `inject.patch`.
- **Caches and byte-code are ignored in the manifest.** A solver who ran the visible tests is not punished for `.pytest_cache` or `__pycache__`.
- **Verifier files and visible tests are copied from the kit into a fresh temp directory.** The workspace never supplies code that decides the score.
- **The pytest environment is scrubbed (`PYTEST_ADDOPTS`, `PYTHONPATH`, `PYTHONSTARTUP`, …).** Otherwise a single environment variable could change every result.
- **`PYTHONHASHSEED=0` is set for the verifier.** Several checks rely on insertion order, and the kit should not depend on hash randomisation even when the code is order-safe.
- **pytest is run with `-p no:cacheprovider`.** It keeps the temp directory clean and removes one more file a solution could tamper with.
- **JUnit XML is the source of per-test truth.** Parsing stdout would break on warnings, colours and pytest's formatting changes.
- **Suites are split by verifier filename.** `test_fail_to_pass.py` and `test_pass_to_pass.py` are a simple, explicit contract.
- **A suite with zero passing tests fails.** Deleting or skipping everything must not look like success.
- **The timeout comes from `metadata.json` per task.** Feature and performance tasks legitimately need more time than a one-line bug fix.
- **`duration_seconds` is informational and excluded from the stability signature.** The brief requires it, and no pass/fail logic may depend on it.
- **`selftest` repeats every verification three times by default and compares a timing-free signature.** That is the cheapest credible flakiness check.

## Verifier content and fairness

- **Tests assert exception types, not message text.** Messages are for humans and should be free to change.
- **Tests use seeded corpora and explicit oracles.** No `random` without a seed, no wall clock, no network.
- **003 rejects absolute paths even when they point inside the root.** The task prompt states this explicitly; allowing them would make the rule depend on where the root happens to be.
- **003 decodes percent escapes exactly once, then checks.** That matches browser behaviour and blocks double-encoding tricks without guessing.
- **003's symlink check skips itself if the OS refuses to create a symlink.** Windows without developer mode is a legitimate environment, not a test failure.
- **004 uses a probe object rather than a monkey-patched builtin.** The probe travels through the public `key` argument, so no implementation detail is assumed.
- **004's growth ceiling is 8× for a 4× input.** That accepts `n log n` (about 4.7× here) and rejects quadratic (about 16×), with room for implementation noise.
- **004's absolute budget is `12 * n * bit_length(n) + 500`.** It is explained in `reasoning.md` and deliberately leaves a sort-based solution comfortable room.
- **005 specifies the coupon order precisely: cart discounts, then coupon, then tax, then shipping.** Ambiguity here would make several correct implementations fail.
- **005 measures the minimum spend on the pre-discount subtotal.** It is the rule most likely to be implemented wrong, so the prompt says it twice and the verifier pins it.
- **002 bundles recency and expiry into one task.** Both defects produce the same user-visible complaint ("the cache keeps the wrong entry"), and the brief asks for them together.
- **001's valid alternatives use a stable sort and a bucket-by-order pass.** They are different mechanisms, not renamed copies.
- **Every task ships an `edits_the_visible_tests.patch` invalid solution.** It proves the anti-cheat path, not just the pytest assertions.
- **The leak check only flags added golden lines of 15+ characters that are not generic.** Shorter lines and imports are not hints; flagging them would create false positives.

## Operations

- **Docker uses `python:3.12.8-slim-bookworm`, not a digest.** No Docker daemon was available to resolve and verify a digest; a concrete patch tag is the honest pin. Record the digest when publishing.
- **The image runs as uid 10001 and makes `/app` read-only for that user.** Verification writes only to the temp directory.
- **CI runs pytest, `selftest --repeat 3`, then builds the image and runs `selftest` with `--network none`.** It mirrors the local acceptance checks.
- **The optional `006-refactor-pricing` task was not built.** The five required tasks are green and documented; a sixth would have been a thinner verifier for the same effort.
- **MIT license.** It is the least friction for a reviewer.
- **No remote is configured and nothing is pushed.** The brief asks for a local `main` repository.
