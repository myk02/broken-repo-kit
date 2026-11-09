# Walkthrough

This document explains the project in plain English. It defines every technical
word it uses. If you can explain this page, you can explain the repository.

## The idea in one paragraph

A coding challenge needs a starting problem, a correct answer, and a test that
can tell correct answers from wrong ones. This repository builds five such
challenges around a small fake shop library. For each challenge it stores the
problem as a **patch** (a text file that describes changes to source code), the
correct answer as another patch, and a **verifier** (a set of automatic tests)
that checks a solution. A command-line tool builds a workspace for a solver,
then grades the solver's work in a clean temporary folder.

## Words used in this repository

- **Repository**: this folder, tracked by the `git` version-control tool.
- **Base**: the clean, correct version of the shop library in `base/minishop/`.
- **Task**: one challenge, stored in `tasks/<id>/`.
- **Defect**: the mistake that makes a task hard.
- **Patch**: a small text file in unified-diff format. It says "remove these
  lines, add these lines". `inject.patch` turns the base into the broken state;
  `golden.patch` turns the broken state into the correct state.
- **Workspace**: the folder a solver works in. It contains the broken library,
  the visible tests, and `task.md` (the instructions). It does not contain the
  answer or the hidden tests.
- **Visible tests**: the 95 ordinary tests in `base/tests/`. A solver can read
  and run them. They pass before and after a correct fix.
- **Verifier**: the hidden tests plus the code that runs them safely. It lives
  in `tasks/<id>/verifier/`.
- **Fail-to-pass test**: a hidden test that fails on the broken code and passes
  on a correct fix. It proves the problem was fixed.
- **Pass-to-pass test**: a hidden test that passes on the broken code and must
  still pass after the fix. It proves nothing else broke.
- **Deterministic**: the same input always gives the same result. No real clock,
  no unseeded randomness, no network, no dependence on how fast the computer is.
- **Operation count**: a number of actions, such as comparisons or hashes,
  counted by a small instrumented object. It is used instead of seconds.
- **Manifest**: a list of every file and a fingerprint (hash) of its contents.
- **Hash**: a short fixed-size value computed from file contents. If the
  contents change, the hash changes.
- **Temp directory**: a throw-away folder outside the repository. It is deleted
  after grading.

## The flow, step by step

1. `python -m kit build 001-discount-stacking --out build/demo`
   copies `base/minishop/` and `base/tests/` into the output folder, applies
   `inject.patch`, and copies `task.md`. The result is the workspace.
2. The solver reads `task.md`, runs the visible tests, and edits files under
   `minishop/`. The solver may not edit the tests; the metadata says only
   `minishop/` is allowed.
3. `python -m kit verify 001-discount-stacking --workspace build/demo` grades it.
4. The grader first compares the workspace with a freshly built broken
   workspace. Any added, changed or deleted file outside `minishop/` is a
   **violation**, and grading stops.
5. The grader creates a temp folder. It copies only `minishop/` from the
   workspace. It copies the visible tests and the hidden verifier files from
   the kit, not from the workspace.
6. It runs pytest in that temp folder with a cleaned environment. pytest writes
   a JUnit XML report, which lists every test and whether it passed.
7. The grader splits the results into fail-to-pass and pass-to-pass. The task
   passes only when both suites have at least one test, zero failures, and no
   violations. `duration_seconds` is printed but never used in the decision.

The important sentence is step 5: **the solver's tests never run**. Only the
solver's library code runs, against the kit's own tests.

## The five tasks

### 001 — Discount stacking

**What the shop does.** A cart has line items and discounts. Money is integer
cents. A percentage discount has order 0; a fixed-amount discount has order 1.
The correct code sorts discounts by that order, so a percentage always runs
before a fixed amount. Sorting is stable, so two discounts of the same kind keep
the order the user listed them.

**The defect.** `inject.patch` deletes the sort. Discounts now run in the order
they appear. If a fixed discount is listed first, the percentage is taken from
the already-reduced amount, and the customer loses money. A one-cent rounding
difference can also appear.

**The fix.** `golden.patch` restores
`sorted(cart.discounts, key=lambda discount: discount.order)`.

**How it is checked.** `task.md` shows three carts. The hidden tests add more:
fixed-first, mixed kinds, repeated percentages, zero-value discounts, tax and
shipping, and a seeded corpus of two hundred carts compared with an independent
calculation of the documented rule. The verifier observes only `Quote` fields.

**Why other correct fixes pass.** One shipped alternative buckets the discounts
by `order` and applies the buckets in sequence. Another sorts with an explicit
comparison key. All three produce the same quotes, so all three pass.

### 002 — Cache recency and expiry

**What the shop does.** `TtlLruCache` holds a limited number of entries. It is
given a **clock**: a function that returns an integer tick. Tests advance the
tick by hand, so no test sleeps. Reading with `get` makes an entry the most
recently used. Reading with `peek` deliberately does not. An entry written at
tick `t` with lifetime `ttl` is alive while `now < t + ttl`.

**The defect.** `inject.patch` makes two changes. It removes `move_to_end` from
`get`, so reads no longer refresh recency and the cache evicts the wrong entry.
It also changes `>=` to `>` in two expiry checks, so an entry survives one tick
too long, and a `ttl=0` entry is readable at the tick it was written.

**The fix.** `golden.patch` restores the `move_to_end` call and both `>=`
comparisons.

**How it is checked.** The hidden tests use a fake clock and check:
which key survives eviction, that `peek` does not change recency, that `get`
does, that `len`, `in`, `keys` and `purge_expired` agree at the exact boundary,
and that `ttl=0` is dead immediately. The two shipped alternatives reinsert the
key instead of moving it, or compare relative age instead of absolute times.

### 003 — Path traversal

**What the shop does.** `PublicFiles` serves downloads from one directory. A
request is a URL-style relative path such as `images/logo.png`. Percent escapes
are decoded once, because browsers send `%2e` where a user typed `.`.

**The defect.** `inject.patch` removes two checks: the rejection of absolute
paths, and the check that the resolved path is still inside the public folder.
Now `../secret.txt`, `C:\Windows\...`, `%2e%2e/secret.txt` and a symlink can
reach outside the folder.

**The fix.** `golden.patch` restores both checks. It resolves the candidate path
and uses `Path.is_relative_to` to prove containment. Absolute paths are rejected
even when they point inside the public folder, because the prompt says so.

**How it is checked.** The verifier builds a public folder, a secret file next
to it, and a sibling folder whose name starts with the same letters
(`public-evil`). It tries dot-dot in several positions, backslashes, encoded
dots, encoded slashes, absolute paths inside and outside the root, a symlink,
and a directory path. Dangerous requests must raise `UnsafePath`; a safe path
that does not exist must raise `MissingPublicFile`; legitimate nested and
unicode files must still be readable.

**Why other correct fixes pass.** One alternative rejects bad segments up front
and compares `os.path.realpath` results with `os.path.commonpath`. The other
resolves the path and checks `relative_to`. Different mechanisms, same
behaviour.

### 004 — Slow duplicate detection

**What the shop does.** `find_duplicates` groups products that share a key,
returns only groups of two or more, sorts each group by sku, and keeps groups in
the order their first member appeared.

**The defect.** `inject.patch` replaces the dictionary-based grouping with two
nested loops. The answer is still correct. It just compares every pair, which is
quadratic: doubling the catalogue quadruples the work. The visible tests use
small inputs, so they stay green.

**The fix.** `golden.patch` restores the dictionary: one lookup per product,
then collect the groups in first-seen order.

**How it is checked.** The verifier passes a custom `key` function whose return
value counts every hash, equality and ordering operation. It runs the function
at 64, 128 and 256 products. A 4× input must grow the count by roughly 4×, not
16×, and must stay under an absolute budget. The output is compared with an
independent oracle, including the order of groups and the order inside a group.

### 005 — Coupons

**What the shop does.** This is a feature, not a bug. The base library has no
coupons at all, so `inject.patch` is empty.

**The specification.** A `Coupon` has exactly one of a percentage or a fixed
amount, plus a minimum spend and an optional last valid tick. A `CouponBook`
holds coupons and a clock. `quote_cart` accepts an optional coupon book and one
code. Cart discounts run first, then the coupon on the remaining amount, then
tax, then shipping. The minimum spend is measured before any discount. Expiry
is inclusive. An unknown code raises `UnknownCoupon`; an expired one raises
`ExpiredCoupon`; a basket below the minimum raises `CouponMinimumNotMet`.

**The fix.** `golden.patch` adds the data classes, the error classes, the coupon
book, and the new `quote_cart` arguments and fields.

**How it is checked.** The verifier tests validation (both kinds set, neither
set, bad values), duplicate codes differing only by case, trimming, case-
insensitive lookup, unknown and blank codes, inclusive expiry on the last tick,
minimum spend before discounts, percentage rounding, fixed coupon clamping,
tax after the coupon, shipping never taxed, and a seeded set of quotes compared
with a reference calculation. One shipped alternative moves the feature into a
separate `minishop/coupons.py` module; it still passes, which proves the
verifier does not care about file layout.

## Questions an interviewer might ask, with short answers

**1. What is this project, in one sentence?**
It is a toolkit that builds reproducible coding challenges, with a correct
reference solution and an automatic checker for every challenge.

**2. Why store the defect as a patch instead of two copies of the code?**
A patch is small, readable, and shows exactly what changed. There is only one
copy of the base library, so the versions cannot drift apart.

**3. How do you know a checker accepts other correct solutions?**
Every task has two alternative solutions written in a different style, and the
quality gate requires both to pass.

**4. How do you stop someone from editing the tests?**
The grader copies only `minishop/` from the solver's folder. The tests come from
the kit. It also compares a fingerprint of every file and rejects any change
outside `minishop/` before running pytest.

**5. How do you stop someone hard-coding the example in the prompt?**
The prompt shows a few examples; the hidden tests use many more inputs,
including a seeded corpus and inputs of different sizes. A hard-coded answer
fails those.

**6. Why not measure seconds for the performance task?**
Seconds depend on the computer, other programs, and even the temperature. The
test would be flaky. Counting operations measures the algorithm itself and is
repeatable.

**7. What does deterministic mean here?**
The same repository and the same Python version give the same result every
time. There is no sleeping, no real clock, no unseeded randomness and no
network.

**8. What is the difference between fail-to-pass and pass-to-pass?**
Fail-to-pass tests must fail before the fix and pass after it. Pass-to-pass
tests must pass both before and after. The first proves the fix worked; the
second proves it did not break something else.

**9. How do you know the checker itself is correct?**
The `selftest` command runs the broken state, the golden patch, every valid
solution, and every invalid solution. It requires the expected result from each.
It repeats the whole thing three times and compares the results.

**10. What is the mutation check in the design document?**
I temporarily deleted the hidden tests that catch a wrong fix. The wrong fix
then passed. That proves those tests are the reason it is rejected, so the
invalid solutions are not just decoration.

**11. How would I add a sixth task?**
Run `python -m kit new-task 006-my-idea`. It creates the folders and files with
`TODO` markers. Fill in the prompt, the defect, the fix, the tests and the
solutions, change the status to `ready`, and run `python -m kit selftest
--task 006-my-idea`.

**12. What is the biggest limitation?**
The checker protects against dishonest edits to tests and metadata, but a
deliberately malicious solution runs in the same Python process as the tests.
For untrusted code you also need a container or a stronger sandbox.

**13. Why integer cents instead of floats?**
Floating point cannot represent every decimal fraction exactly. Repeated
rounding can lose a cent. Integers make the arithmetic exact and the tests
stable.

**14. Why inject a clock into the cache and the coupons?**
So tests can jump to an exact tick without sleeping. Sleeping makes tests slow
and flaky; reading the real clock makes them depend on the date.

**15. What would you do next?**
Add the optional refactor task, run the Docker image and CI on a machine that
has Docker, and add a task that spans two modules so `allowed_paths` has to be
more than one folder.

## How to demo it in five minutes

```powershell
python -m kit list
python -m kit build 003-path-traversal --out build/demo-003
cd build/demo-003
python -m pytest tests                          # visible tests are green
cd ../..
python -m kit verify 003-path-traversal --workspace build/demo-003   # fails
# edit build/demo-003/minishop/files.py, or apply the reference:
python -m kit verify 003-path-traversal --patch tasks/003-path-traversal/golden.patch
python -m kit selftest --repeat 3
```

The first verify shows the hidden tests failing for the right reason. The second
shows the reference solution passing. The last command shows that every task's
own quality checks are green.
