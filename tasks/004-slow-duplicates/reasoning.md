# 004-slow-duplicates - reasoning

## Root cause

`find_duplicates` is implemented as two nested loops: for every product it
scans every later product and compares keys. That is ``n * (n - 1) / 2``
comparisons. Doubling the catalogue quadruples the work.

The result is correct, which is why the visible tests pass: they use small
inputs where ``n^2`` is invisible.

## Why this verifier is fair

The verifier never reads the clock. It supplies a custom ``key`` whose return
value is a probe object counting every ``__hash__``, ``__eq__`` and ``__lt__``
call, then measures three sizes. Two independent approaches pass:

- a dict keyed by the probe performs ~2 hashes per product;
- sort-then-group performs O(n log n) comparisons and stays under the budget.

The correctness checks compare against an independent oracle and pin group
order and sku order.

## The maths

Pairwise: ``T(4n) / T(n) = (4n)(4n-1) / (n(n-1))``, which is close to 16.

Hashing: ``T(n) ~ c * n``, so ``T(4n) / T(n) ~ 4``.

Sorting: ``T(n) ~ c * n log n``; at n=64 to 256 the ratio is about 4.7, well
below the 8x ceiling. The absolute budget ``12 * n * bit_length(n) + 500`` is
also generous enough for a sort-based solution and still far below the
quadratic count.

## What valid variation it allows

Grouping with a dict, counting first and collecting second, sorting by key and
walking the runs, or any other scheme with the same output. All are accepted.

## Cheats it blocks

- Caching the keys once but still comparing all pairs: the probe's equality
  count still grows quadratically.
- Comparing only adjacent entries: fast, but misses a duplicate separated by a
  unique product.
- Sorting the finished groups: output order changes and the oracle catches it.
- Truncating inputs above 120 products: the large-corpus check fails.
- Editing the visible tests is a violation before pytest starts.
