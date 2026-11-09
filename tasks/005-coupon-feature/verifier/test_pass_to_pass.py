"""Pass-to-pass checks for 005-coupon-feature.

These only use behaviour that exists before the feature is added.
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
)


def test_ordinary_cart_still_prices_the_same() -> None:
    quote = quote_cart(
        Cart(
            lines=(LineItem("a", 2, 1250), LineItem("b", 1, 300)),
            discounts=(PercentOff(10), FixedOff(100)),
            tax_rate_bp=825,
            shipping_cents=499,
        )
    )
    assert quote.subtotal_cents == 2800
    assert quote.discount_cents == 380
    assert quote.taxable_cents == 2420
    assert quote.tax_cents == 200
    assert quote.total_cents == 3119


def test_percentage_rounding_is_unchanged() -> None:
    quote = quote_cart(Cart(lines=(LineItem("a", 1, 1005),), discounts=(PercentOff(10),)))
    assert quote.discount_cents == 101
    assert quote.total_cents == 904


def test_validation_and_money_helpers_are_unchanged() -> None:
    with pytest.raises(ValueError):
        LineItem("a", 1, -1)
    with pytest.raises(ValueError):
        PercentOff(101)
    with pytest.raises(ValueError):
        FixedOff(-1)
    assert parse_cents("12.34") == 1234
    assert format_cents(1234) == "12.34"


def test_empty_cart_still_pays_only_shipping() -> None:
    quote = quote_cart(Cart(lines=(), shipping_cents=499))
    assert quote.subtotal_cents == 0
    assert quote.tax_cents == 0
    assert quote.total_cents == 499
