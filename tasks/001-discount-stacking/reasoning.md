# 001-discount-stacking - reasoning

## Root cause

`quote_cart` applies discounts in the order they appear on the cart. The
documented rule is that percentage discounts run before fixed-amount discounts,
with a stable order inside each kind. When a fixed discount is listed first the
percentage is taken from the already-reduced amount, so the customer loses the
percentage of the fixed amount. The cent drift is a consequence of the same
bug: 10% of 1005 rounds half up to 101, but 10% of 1004 rounds to 100.

## Why this verifier is fair

Every check goes through `Cart` and `quote_cart`. It never imports a private
helper or inspects source text. The seeded property check computes its expected
value with the documented two-pass rule, so any implementation that produces
the same observable quotes passes.

## What valid variation it allows

Any way of ordering the discounts is accepted: restoring the stable sort,
bucketing by `Discount.order`, or sorting with an explicit comparator. The
verifier only observes `taxable_cents`, `discount_cents`, `tax_cents` and
`total_cents`.

## Cheats it blocks

- Reversing the order fails the mixed-discount checks.
- Hard-coding the example cart fails the seeded corpus.
- Changing rounding to truncation fails the visible rounding test and the
  one-cent case.
- Editing the visible tests is rejected as a violation before pytest runs.
