# broken-repo-kit

A small, complete example of the work behind reproducible coding environments:
a realistic Python library (`minishop`), five seeded defects or missing
capabilities, a **golden** reference patch for each, and a **deterministic
verifier** that accepts any reasonable correct fix while rejecting the
tempting wrong ones. Everything runs offline through one CLI:
`python -m kit`.

The point is not the shop. The point is the loop: **base → inject → broken →
solver → verifier → pass/fail**, with the verifier treated as a piece of
software that itself has to be tested.

## 60-second quickstart

Requirements: Python 3.12 and nothing else (pytest is the only dev dependency).

```powershell
git clone https://github.com/<your-account>/broken-repo-kit.git
cd broken-repo-kit
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt

python -m pytest                          # 152 tests, all green
python -m kit list                        # the five tasks
python -m kit build 001-discount-stacking --out build/demo-001
python -m kit verify 001-discount-stacking --workspace build/demo-001
```

The last command fails on purpose: the workspace contains the defect. Read
`build/demo-001/task.md`, fix `build/demo-001/minishop/`, and run it again. To
see a passing run immediately, verify the reference solution instead:

```powershell
python -m kit verify 001-discount-stacking --patch tasks/001-discount-stacking/golden.patch
```

On macOS or Linux replace the activation line with
`source .venv/bin/activate`. The kit itself uses only `pathlib`, never shell
scripts, so the same commands work in PowerShell, cmd, bash and zsh.

## The flow

```
                 tasks/<id>/inject.patch
 base/minishop ──────────────────────────► broken workspace
 (correct)                                  + task.md
                                            + visible tests
                                                  │
                                     solver edits minishop/
                                                  │
                                                  ▼
                                          candidate solution
                                                  │
        pristine verifier + pristine tests       │
        copied into a throw-away directory  ◄─────┘
        clean environment, no workspace tests
                                                  │
                                                  ▼
                         fail-to-pass  +  pass-to-pass  ──►  JSON result
```

The solver never receives `metadata.json` (it names the touched files), the
verifier, or the golden patch. The verifier never trusts anything in the
workspace except the library code under `minishop/`.

## Tasks

| ID | Type | Difficulty | What it tests |
|----|------|------------|---------------|
| `001-discount-stacking` | bug fix | medium | Ordering rules and cent-exact rounding across mixed discounts |
| `002-cache-recency` | bug fix | medium | LRU recency and an off-by-one TTL boundary, with an injected clock |
| `003-path-traversal` | security | hard | Path containment against `..`, absolute paths, encoded dots and symlinks |
| `004-slow-duplicates` | performance | medium-hard | Replacing O(n²) pair comparison with near-linear work, proved by operation counts |
| `005-coupon-feature` | feature | hard | Adding coupons with validation, precedence, minimum spend and inclusive expiry |

Every task ships:

- `task.md` — the prompt a solver sees (symptom, spec, examples, constraints);
- `metadata.json` — type, difficulty, touched files, allowed paths, time limit;
- `inject.patch` — base → broken;
- `golden.patch` — the reference solution;
- `verifier/test_fail_to_pass.py` and `verifier/test_pass_to_pass.py`;
- two genuinely different valid solutions and at least three tempting invalid
  ones under `solutions/`;
- `reasoning.md` — root cause, fairness argument, allowed variation, blocked cheats.

## What makes a good verifier

These are the rules the kit enforces, not aspirations:

1. **Behaviour through the public API only.** No private names, no source-text
   matching, no "you must call this helper".
2. **Two suites.** Fail-to-pass proves the problem is fixed; pass-to-pass proves
   nothing else broke. Both are reported separately.
3. **The spec space, not the example.** Boundaries, empty and large inputs,
   unicode, ordering and error types. Seeded property checks are deterministic.
4. **The verifier is not editable.** Only `minishop/` is copied from the
   workspace. Verifier files and visible tests come fresh from the kit. A
   manifest diff rejects edits, additions or deletions anywhere else.
5. **Hidden cases.** `task.md` shows a few examples; the verifier has many more.
6. **Fast and idempotent.** One task verifies in a few seconds; `selftest`
   repeats every run three times and compares a timing-free signature.
7. **Operation counts, not seconds**, for the performance task.
8. **A machine-readable result** whose pass/fail logic never looks at time:

```json
{
  "task": "001-discount-stacking",
  "passed": true,
  "fail_to_pass": {"passed": 5, "failed": 0},
  "pass_to_pass": {"passed": 101, "failed": 0},
  "violations": [],
  "duration_seconds": 7.58
}
```

`duration_seconds` is informational. It is excluded from the stability
signature and from `passed`.

## The quality gate

`python -m kit selftest --repeat 3` proves, for every task, that the base is
green, the broken state is green on the visible tests but red on every
fail-to-pass test, the golden patch and both alternatives pass, every invalid
patch is rejected, three repeats agree, and `task.md` does not leak a line of
the fix. Real output from this repository (the invalid-patch list is abridged
here; the command prints every case):

```text
task                   struct   base     visible  broken   golden   valid    invalid  stable   leak
------------------------------------------------------------------------------------------------------
001-discount-stacking  ok       ok       ok       ok       ok       ok       ok       ok       ok
002-cache-recency      ok       ok       ok       ok       ok       ok       ok       ok       ok
003-path-traversal     ok       ok       ok       ok       ok       ok       ok       ok       ok
004-slow-duplicates    ok       ok       ok       ok       ok       ok       ok       ok       ok
005-coupon-feature     ok       ok       ok       ok       ok       ok       ok       ok       ok

invalid solutions and what rejected them:
  001-discount-stacking  hardcodes_the_example_cart.patch: test_one_cent_rounding_does_not_decide_the_order: AssertionError: assert 904 == 903; test_several_discounts_of_both_kinds: AssertionError: assert 1472 == 1387
  002-cache-recency      only_fixes_read_recency.patch: test_entry_is_gone_at_the_exact_expiry_tick: AssertionError: assert 'A' == 'gone'; test_ttl_zero_is_immediately_dead: AssertionError: assert 'A' == 'gone'
  003-path-traversal     only_blocks_dotdot_segments.patch: test_encoded_absolute_slash: minishop.files.MissingPublicFile: ...; test_absolute_path_outside_the_root: Failed: DID NOT RAISE <class 'minishop.files.UnsafePath'>
  004-slow-duplicates    compares_only_adjacent_products.patch: test_group_order_is_first_occurrence_order: AssertionError: assert [] == [['z1', 'z2'], ['a1', 'a2']]
  005-coupon-feature     expiry_rejects_its_last_day.patch: test_expiry_is_inclusive_on_the_last_tick: minishop.pricing.ExpiredCoupon: ...

5/5 tasks passed all checks (3 repeats each)
```

The full list of invalid patches and the exact failing assertion of each is
printed by the same command.

## Adding a task

```powershell
python -m kit new-task 006-my-idea
```

That creates the complete folder layout with `TODO` markers and
`"status": "draft"`; drafts are skipped by `selftest` and shown by
`python -m kit list`, so a half-written task is never mistaken for a finished
one. Fill in `task.md`, make the fix in `base/minishop/`, generate
`inject.patch`, add the verifier and solutions, flip the status to `"ready"`,
then run:

```powershell
python -m kit selftest --task 006-my-idea
```

`docs/DESIGN.md` explains the patch format and the anti-cheat model;
`docs/WALKTHROUGH.md` explains the whole project in plain English.

## Docker

```powershell
docker build -t broken-repo-kit .
docker run --rm --network none broken-repo-kit python -m kit list
docker run --rm --network none broken-repo-kit python -m kit selftest
```

Verification needs no network. Build a workspace into a mounted folder, edit it
on the host, then verify it inside the container:

```powershell
mkdir build\demo
docker run --rm -v "${PWD}/build/demo:/demo" broken-repo-kit python -m kit build 003-path-traversal --out /demo/task
# edit build/demo/task/minishop/files.py on the host
docker run --rm --network none -v "${PWD}/build/demo:/demo" broken-repo-kit python -m kit verify 003-path-traversal --workspace /demo/task
```

The image runs as an unprivileged user and the application directory is
read-only for that user; verification writes only to the system temp directory.
On Linux, add `--user "$(id -u):$(id -g)"` to the two `run` commands so the
container can write to the bind mount.

## Repository layout

```text
base/minishop/          the clean library (pricing, inventory, cache, search, files, csvio)
base/tests/             the visible suite (95 tests), green on the base
kit/                    patch engine, workspace builder, runner, anti-cheat, CLI, selftest
tasks/<id>/             one folder per challenge, including verifier and solutions
tests/                  tests for the kit itself (57 tests)
docs/                   design, decisions, walkthrough, plan
Dockerfile              pinned Python 3.12 image, non-root user
.github/workflows/ci.yml tests + selftest + offline Docker run
```

## Limitations

- This machine had **no Docker installed**, so the Dockerfile and the CI Docker
  step are written carefully but were not executed here. Everything else was
  run locally on Windows 11 with Python 3.12.10 and pytest 8.3.4.
- CI is configured for Ubuntu and the code avoids OS-specific paths, but macOS
  was not available to test.
- The verifier defends against editing tests and workspace metadata, not against
  deliberately malicious solution code running in the same process (it could,
  for example, inspect the test process at import time). Run untrusted code in a
  container or sandbox if that is the threat you care about; `--network none`
  removes the network, not the process.
- Time limits are per verification and coarse. They exist to stop hangs, not to
  measure speed; the performance task uses operation counts.
- The optional `006-refactor-pricing` stretch task was not built. The framework
  supports it, but shipping five airtight tasks beat shipping six uneven ones.
  See `docs/DECISIONS.md`.

## License

MIT. See `LICENSE`.
