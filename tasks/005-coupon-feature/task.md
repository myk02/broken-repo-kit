# Add coupon codes to pricing

The marketing team wants coupon codes. Add them to `minishop.pricing` and
export the names from the `minishop` package.

## Public API

```python
Coupon(code, percent=None, fixed_cents=None, min_spend_cents=0, expires_on=None)
CouponBook(coupons, *, clock)              # clock is a callable returning an int tick
CouponBook.resolve(code, *, subtotal_cents) -> Coupon
quote_cart(cart, *, coupons=None, coupon_code=None) -> Quote
```

- A `Coupon` has **exactly one** of `percent` (1..100) or `fixed_cents` (>= 1).
  A blank code, a negative minimum spend or an `expires_on` that is not an
  integer raise `ValueError` (or `TypeError` for the wrong type).
  Codes are trimmed of surrounding whitespace.
- `CouponBook` rejects two coupons whose codes differ only by case, with
  `ValueError`. Lookup is case-insensitive and ignores surrounding whitespace.
- `expires_on` is the **last tick on which the coupon is valid** (inclusive).
  At `clock() == expires_on` it still works; at `clock() > expires_on` it
  raises `ExpiredCoupon`.
- `resolve` raises `UnknownCoupon` for an unknown or blank code,
  `ExpiredCoupon` for an expired one, and `CouponMinimumNotMet` when
  `subtotal_cents` is below the coupon's minimum. All three subclass
  `CouponError`, which subclasses `ValueError`.
- `quote_cart` accepts at most one `coupon_code`. Passing a non-string, or a
  code without a coupon book, raises `CouponError`.

## Pricing rules

1. Cart discounts run first, in the documented percentage-then-fixed order.
2. The coupon is applied to the **amount left after those cart discounts**.
   A percentage coupon rounds half up; a fixed coupon is capped so the amount
   can never go below zero.
3. The minimum spend is measured on the cart **subtotal before any discount**.
4. Tax is charged once on the amount left after the cart discounts and the
   coupon. Shipping is added after tax and is never taxed.
5. `Quote.discount_cents` still means cart discounts only. The coupon's amount
   is reported separately in `Quote.coupon_discount_cents`, and
   `Quote.coupon_code` is the coupon's canonical code (or `None`).

## Examples

```python
cart = Cart(lines=(LineItem("a", 1, 1000),), discounts=(PercentOff(10),), tax_rate_bp=1000)
book = CouponBook([Coupon("SAVE10", percent=10)], clock=lambda: 0)
q = quote_cart(cart, coupons=book, coupon_code="save10")
# q.discount_cents == 100, q.coupon_discount_cents == 90
# q.taxable_cents == 810, q.tax_cents == 81, q.coupon_code == "SAVE10"
```

```python
book = CouponBook([Coupon("MIN950", fixed_cents=50, min_spend_cents=950)], clock=lambda: 0)
# a 949-cent basket raises CouponMinimumNotMet; a 950-cent basket is fine
```

## Constraints

- Integer cents only; no floats.
- Do not change existing pricing behaviour when no coupon is supplied.
- Do not edit the visible tests.
- Keep the injected-clock design; do not call `time` or read the real date.
