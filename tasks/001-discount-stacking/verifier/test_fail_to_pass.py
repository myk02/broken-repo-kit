"""Fail-to-pass checks for 001-discount-stacking.

Every test here uses the public API and fails while the defect is present.
"""

from __future__ import annotations

import random

from minishop.pricing import Cart, FixedOff, LineItem, PercentOff, quote_cart


def price(
    lines: tuple[LineItem, ...],
    discounts: tuple[object, ...],
    *,
    tax_rate_bp: int = 0,
    shipping_cents: int = 0,
):
    """Price one cart through the public API."""
    cart = Cart(
        lines=lines,
        discounts=discounts,  # type: ignore[arg-type]
        tax_rate_bp=tax_rate_bp,
        shipping_cents=shipping_cents,
    )
    return quote_cart(cart)


def reference_taxable(subtotal: int, discounts: tuple[object, ...]) -> int:
    """Apply all percentages, then all fixed amounts, each in listed order."""
    running = subtotal
    for discount in discounts:
        if isinstance(discount, PercentOff):
            running = discount.apply(running)
    for discount in discounts:
        if isinstance(discount, FixedOff):
            running = discount.apply(running)
    return running


def test_fixed_discount_listed_first_is_still_applied_after_percentage() -> None:
    quote = price((LineItem("a", 1, 1000),), (FixedOff(100), PercentOff(10)))
    assert quote.taxable_cents == 800
    assert quote.discount_cents == 200


def test_one_cent_rounding_does_not_decide_the_order() -> None:
    # 10% of 1005 is 100.5 -> 101 half up; the fixed cent comes off afterwards.
    quote = price((LineItem("a", 1, 1005),), (FixedOff(1), PercentOff(10)))
    assert quote.taxable_cents == 903
    assert quote.discount_cents == 102


def test_tax_and_shipping_see_the_correct_discounted_amount() -> None:
    quote = price(
        (LineItem("a", 1, 1000),),
        (FixedOff(100), PercentOff(10)),
        tax_rate_bp=825,
        shipping_cents=499,
    )
    assert quote.taxable_cents == 800
    assert quote.tax_cents == 66
    assert quote.total_cents == 1365


def test_several_discounts_of_both_kinds() -> None:
    quote = price(
        (LineItem("a", 1, 2500),),
        (FixedOff(500), PercentOff(10), FixedOff(250), PercentOff(5)),
    )
    assert quote.taxable_cents == 1387
    assert quote.discount_cents == 1113


def test_seeded_mixed_carts_match_the_reference_order() -> None:
    rng = random.Random(20260101)
    for _ in range(80):
        subtotal = rng.randrange(0, 200_001)
        lines = (LineItem("a", 1, subtotal),)
        discounts: list[object] = []
        for _ in range(rng.randrange(1, 4)):
            discounts.append(PercentOff(rng.randrange(0, 51)))
        for _ in range(rng.randrange(1, 4)):
            discounts.append(FixedOff(rng.randrange(0, max(1, subtotal // 2 + 1))))
        rng.shuffle(discounts)
        quote = price(tuple(lines), tuple(discounts))
        assert quote.taxable_cents == reference_taxable(subtotal, tuple(discounts))
