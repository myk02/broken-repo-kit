# 005-coupon-feature - reasoning

## Root cause

There is no defect: this is a feature. The base pricing module has no concept
of a coupon, so every coupon test fails with `TypeError` or `AttributeError`.
The golden patch adds the public surface and wires it into `quote_cart`.

## Why this verifier is fair

The checks use only `Coupon`, `CouponBook`, the documented error classes and
`quote_cart`. They do not import private helpers or inspect source text. Both
shipped alternatives pass with different internals:

- one makes `Coupon.apply_to` do the arithmetic and splits validation into
  private methods;
- one moves the whole feature into `minishop/coupons.py` and imports it from
  pricing, proving the verifier does not care where the code lives.

## What valid variation it allows

Different module layout, different private helper names, different order of
validation (unknown before expired before minimum, as long as the documented
error wins for each case), and any implementation of the percentage rounding
that matches half-up on integer cents.

## Cheats it blocks

- Case-sensitive lookup fails the whitespace/case check.
- Treating `expires_on` as exclusive fails the last-tick check.
- Measuring the minimum on the post-discount amount fails the 1000/950 case.
- Applying the coupon to the pre-discount subtotal fails the rounding and
  ordering cases.
- Letting a fixed coupon go negative fails the clamp case.
- Returning `None` for an unknown code fails the error-type checks.
- Editing the visible tests is a violation before pytest starts.
