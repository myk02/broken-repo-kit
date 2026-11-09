# Design

## What problem this repository solves

A coding challenge is only useful if three things are true at once:

1. the starting state contains a real problem;
2. a correct solution exists and is written down;
3. an automatic check accepts every correct solution and rejects every
   incorrect one.

The third point is the hard one, and it is the part most challenge repositories
skip. `broken-repo-kit` treats the verifier as the product: it has its own
tests, its own threat model, and a quality gate that proves the verifier
behaves as claimed.

## Architecture

```
kit/
  paths.py        every path, derived from the repository root
  patching.py     pure-Python unified-diff parser and applier
  task.py         metadata schema, task loading, folder completeness
  workspace.py    base → broken → solver workspaces, tree hashing
  anticheat.py    manifest diff against a pristine broken tree
  runner.py       builds a clean verifier directory and runs pytest
  result.py       per-case results, suite tallies, stable JSON
  selftest.py     the quality gate and its matrix
  scaffold.py     `new-task` templates
  cli.py          argparse entry point
```

The data flows one way:

```
tasks/<id>/inject.patch  +  base/minishop  ──►  workspace (broken)
workspace + solver edits                     ──►  candidate
candidate's minishop/ + kit's tests/verifier ──►  temp dir
temp dir + clean env + pytest                ──►  JUnit XML
JUnit XML                                    ──►  VerifyResult ──► JSON
```

Nothing in `kit/` imports `minishop`. The verifier process imports it; the kit
only moves files around and reads pytest's machine-readable report.

## Why patches instead of branches or file copies

- A patch is reviewable. The whole defect is a few lines in `inject.patch`, and
  the whole fix is a few lines in `golden.patch`.
- A patch is portable. The applier is ~300 lines of standard library, so the
  kit does not require `git` or `patch` on the host (important on Windows).
- A patch is strict. Context mismatches fail with the file name and hunk number
  instead of silently producing a different starting state.
- The alternative solutions are also patches, which keeps the whole task
  corpus in one text format that `git diff` can display.

The applier understands the subset of unified diff the kit emits: multiple
files, multiple hunks, create, delete, `\ No newline at end of file`, and
git-style headers. It rejects renames, paths outside the workspace, hunks
outside the file, and body lengths that disagree with the header. Every change
is staged and only written if the whole patch applies, so a failed patch leaves
the tree untouched.

## Why operation counts for performance

Wall-clock assertions are flaky: CI CPUs throttle, virus scanners interfere,
and a busy laptop makes a correct solution fail. `004-slow-duplicates` therefore
never measures seconds. It passes a custom `key` callable whose return value is
a probe object:

- `__hash__`, `__eq__` and `__lt__` increment a counter;
- the verifier calls `find_duplicates` at sizes 64, 128 and 256;
- it checks the growth ratio and an absolute budget.

The maths, with `n` products and `T(n)` operations:

- The broken implementation compares every pair: `T(n) = n(n-1)/2`.
  `T(4n)/T(n)` tends to 16.
- Hashing every product once: `T(n) ≈ 2n` (one hash to insert, one to look up),
  so `T(4n)/T(n) ≈ 4`.
- Sort-then-group: `T(n) ≈ c·n log n`; between 64 and 256 the ratio is about
  4.7, comfortably below the 8× ceiling.

The absolute budget is `12 * n * bit_length(n) + 500`. It is generous enough
for a comparison sort and far below the pairwise count (32,421 at n=256). The
verifier also checks that the key callable is called once per product, not once
per pair, and compares the output against an independent oracle.

## Fairness rules

These are enforced by review and by `selftest`, not just documented:

- tests import only public names;
- no test reads source text, private attributes or module internals;
- error behaviour is specified by exception type, not message text;
- output order is part of the specification when the prompt says so;
- clocks are injected; randomness is seeded; no test sleeps;
- every task has at least two valid solutions that use different mechanisms,
  and they must pass;
- every task's invalid solutions are run, and each must fail for a recorded
  reason.

`selftest` requires all fail-to-pass tests to fail on the broken state (not
"some"), and all pass-to-pass tests to pass on it. That prevents the common
mistake where a task's "defect" already fails most of its own tests.

## Threat model

### Defended

| Attack | Defence |
|--------|---------|
| Edit, delete or add tests, `conftest.py`, `pytest.ini`, `sitecustomize.py` | Only `allowed_paths` (`minishop/`) are copied from the workspace. The visible tests and verifier files are copied fresh from the kit. |
| Change a file outside `minishop/` | The workspace is hashed and diffed against a freshly built broken tree; any add/change/delete is a violation and verification stops before pytest. |
| Hide a failure by changing pytest configuration | `PYTEST_ADDOPTS`, `PYTEST_PLUGINS`, `PYTHONPATH`, `PYTHONSTARTUP`, `PYTHONHOME` and `PYTHONWARNINGS` are removed/replaced; pytest runs with `-p no:cacheprovider` in a fresh temp directory. |
| Delete the verifier's tests | The verifier is not in the workspace at all, and a suite with zero passing tests is a failure. |
| Hard-code the examples | Each verifier has hidden cases, seeded corpora and an independent oracle. |
| Special-case the test input | The same behaviour is checked at several sizes, with different names, unicode, boundaries and orderings. |
| Slow the verifier down until it times out | A per-task `time_limit_seconds` fails the run; timeouts are violations, never passes. |
| Submit a huge tree | `copy_allowed_paths` rejects more than 2,000 files or 20 MB. |
| Win by editing `metadata.json` | Metadata comes from the kit, never from the workspace. |

### Not defended

- **Malicious code in the solution.** `minishop` is imported into the same
  Python process as pytest. Code that deliberately introspects the interpreter,
  monkey-patches pytest, or rewrites files could cheat. The kit is built for
  honest-but-wrong solvers, which is the normal case for an RL environment; run
  untrusted code in a container or a stronger sandbox if that is the threat.
- **Resource exhaustion inside the timeout.** A solution can allocate memory or
  burn CPU until the verifier times out. The timeout turns that into a failure,
  but it does not protect the host.
- **Side channels in the host filesystem.** Tests create their own temp
  directories, but a malicious solution can still read absolute paths the host
  exposes. `--network none` removes the network, not the filesystem.
- **Determinism across Python patch versions.** Results are deterministic for a
  pinned Python (3.12) and pytest (8.3.4). A different pytest could change the
  JUnit file names the runner parses.
- **Task quality by construction.** `selftest` proves the properties it knows
  how to check. It cannot prove that a task is interesting.

## Mutation check: are the invalid solutions meaningful?

If a wrong fix fails only because of one incidental assertion, the invalid set
is decoration. To test that, the failing fail-to-pass test functions were
temporarily removed from each verifier (the repository was restored afterwards)
and the same invalid patch was verified again. Every one then passed, which
shows those tests are what reject the wrong fix:

| Task | Invalid patch | Test functions removed | Result after weakening |
|------|---------------|------------------------|------------------------|
| 001 | `hardcodes_the_example_cart.patch` | `test_one_cent_rounding_does_not_decide_the_order`, `test_several_discounts_of_both_kinds`, `test_seeded_mixed_carts_match_the_reference_order` | **passed** (2 f2p, 101 p2p) |
| 002 | `only_fixes_the_expiry_boundary.patch` | `test_get_makes_an_entry_most_recent`, `test_several_reads_move_the_whole_recency_order` | **passed** (7 f2p, 100 p2p) |
| 003 | `allows_absolute_paths_inside_the_root.patch` | `test_absolute_path_inside_the_root_is_still_rejected` | **passed** (10 f2p, 103 p2p) |
| 004 | `caches_keys_but_still_compares_pairs.patch` | `test_work_grows_near_linearly_not_quadratically`, `test_absolute_operation_budget`, `test_default_key_also_stays_within_budget` | **passed** (1 f2p, 102 p2p) |
| 005 | `expiry_rejects_its_last_day.patch` | `test_expiry_is_inclusive_on_the_last_tick` | **passed** (19 f2p, 99 p2p) |

This is a mutation test of the verifier: weaken the check, and the wrong answer
slips through. The committed verifiers are the unweakened versions, and
`git status` is clean after the experiment.

## Idempotence and speed

`selftest --repeat 3` compares `VerifyResult.signature()` across runs. The
signature includes task, pass/fail, suite counts and violations; it excludes
`duration_seconds` and case order. No test uses the wall clock for an assertion.
One task's verification takes a few seconds; the full gate takes about eight
minutes on the development machine because it runs every solution for every
task three times.

## Deliberate limits

- Five tasks, not a benchmark. The value is the pattern and the proof, not the
  count.
- `base/tests` is copied into every workspace unchanged. A task may add verifier
  cases, but must not change the visible suite; that keeps pass-to-pass honest.
- Feature tasks may ship an empty `inject.patch`: the starting point is the base
  library, because the capability simply does not exist yet. `check_structure`
  allows this only for `type: feature`.
