"""Pass-to-pass checks for 001-discount-stacking.

These cover behaviour that already worked and must keep working.
"""

from __future__ import annotations

import pytest

from minishop.pricing import (
    Cart,
    FixedOff,
    LineItem,
    PercentOff,
    format_cents,
    parse_cents,
    quote_cart,
    round_half_up,
)


def test_subtotal_tax_and_shipping() -> None:
    quote = quote_cart(
        Cart(
            lines=(LineItem("a", 2, 1250), LineItem("b", 1, 300)),
            tax_rate_bp=1000,
            shipping_cents=499,
        )
    )
    assert quote.subtotal_cents == 2800
    assert quote.tax_cents == 280
    assert quote.total_cents == 3579


def test_percentage_only_and_fixed_only_carts_are_unchanged() -> None:
    percent = quote_cart(
        Cart(lines=(LineItem("a", 1, 1000),), discounts=(PercentOff(10), PercentOff(10)))
    )
    fixed = quote_cart(
        Cart(lines=(LineItem("a", 1, 1000),), discounts=(FixedOff(100), FixedOff(50)))
    )
    assert percent.taxable_cents == 810
    assert fixed.taxable_cents == 850


def test_percentage_discount_rounds_half_up() -> None:
    quote = quote_cart(
        Cart(lines=(LineItem("a", 1, 1005),), discounts=(PercentOff(10),))
    )
    assert quote.discount_cents == 101
    assert quote.total_cents == 904


def test_fixed_discount_stops_at_zero() -> None:
    quote = quote_cart(
        Cart(lines=(LineItem("a", 1, 300),), discounts=(FixedOff(1000),))
    )
    assert quote.taxable_cents == 0
    assert quote.total_cents == 0


def test_money_helpers_still_round_trip() -> None:
    assert format_cents(-5) == "-0.05"
    assert parse_cents("12.34") == 1234
    assert round_half_up(5, 2) == 3
    assert round_half_up(-5, 2) == -3


def test_invalid_money_and_discounts_are_still_rejected() -> None:
    with pytest.raises(ValueError):
        LineItem("a", 1, -1)
    with pytest.raises(ValueError):
        PercentOff(101)
    with pytest.raises(ValueError):
        FixedOff(-1)
