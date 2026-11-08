"""Visible tests for minishop.pricing."""

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


def cart(*lines: LineItem, **kwargs: object) -> Cart:
    """Build a cart from lines and keyword arguments."""
    return Cart(lines=tuple(lines), **kwargs)  # type: ignore[arg-type]


def test_subtotal_and_total_for_one_line() -> None:
    quote = quote_cart(cart(LineItem("sku-1", 2, 1250)))
    assert quote.subtotal_cents == 2500
    assert quote.discount_cents == 0
    assert quote.tax_cents == 0
    assert quote.total_cents == 2500


def test_subtotal_adds_every_line() -> None:
    quote = quote_cart(cart(LineItem("a", 1, 999), LineItem("b", 3, 100)))
    assert quote.subtotal_cents == 1299
    assert quote.lines[1].subtotal_cents == 300


def test_empty_cart_still_pays_shipping() -> None:
    quote = quote_cart(cart(shipping_cents=499))
    assert quote.subtotal_cents == 0
    assert quote.tax_cents == 0
    assert quote.total_cents == 499


def test_percent_discount_rounds_half_up() -> None:
    # 10% of 1005 is 100.5 cents, which rounds up to 101.
    quote = quote_cart(cart(LineItem("a", 1, 1005), discounts=(PercentOff(10),)))
    assert quote.discount_cents == 101
    assert quote.total_cents == 904


def test_fixed_discount_is_subtracted() -> None:
    quote = quote_cart(cart(LineItem("a", 1, 5000), discounts=(FixedOff(1200),)))
    assert quote.discount_cents == 1200
    assert quote.taxable_cents == 3800


def test_fixed_discount_never_makes_the_total_negative() -> None:
    quote = quote_cart(cart(LineItem("a", 1, 300), discounts=(FixedOff(1000),)))
    assert quote.taxable_cents == 0
    assert quote.total_cents == 0


def test_percentage_then_fixed_discount() -> None:
    quote = quote_cart(
        cart(LineItem("a", 1, 1000), discounts=(PercentOff(10), FixedOff(100)))
    )
    assert quote.discount_cents == 200
    assert quote.taxable_cents == 800


def test_two_percent_discounts_compound() -> None:
    # 1000 -> 900 -> 810; adding the percentages first would give 800.
    quote = quote_cart(
        cart(LineItem("a", 1, 1000), discounts=(PercentOff(10), PercentOff(10)))
    )
    assert quote.taxable_cents == 810


def test_tax_is_charged_once_on_the_discounted_amount() -> None:
    lines = (LineItem("a", 1, 333), LineItem("b", 1, 333), LineItem("c", 1, 333))
    quote = quote_cart(cart(*lines, tax_rate_bp=825))
    assert quote.subtotal_cents == 999
    assert quote.tax_cents == 82  # 999 * 0.0825 = 82.4175
    assert quote.total_cents == 1081


def test_tax_uses_the_discounted_amount() -> None:
    quote = quote_cart(
        cart(LineItem("a", 1, 10_000), discounts=(PercentOff(50),), tax_rate_bp=2000)
    )
    assert quote.taxable_cents == 5000
    assert quote.tax_cents == 1000
    assert quote.total_cents == 6000


def test_shipping_is_not_taxed() -> None:
    quote = quote_cart(cart(LineItem("a", 1, 1000), tax_rate_bp=1000, shipping_cents=500))
    assert quote.tax_cents == 100
    assert quote.total_cents == 1600


def test_full_discount_leaves_zero_tax() -> None:
    quote = quote_cart(cart(LineItem("a", 1, 700), discounts=(PercentOff(100),), tax_rate_bp=1000))
    assert quote.taxable_cents == 0
    assert quote.tax_cents == 0
    assert quote.total_cents == 0


def test_quote_exposes_one_line_per_cart_line() -> None:
    quote = quote_cart(cart(LineItem("a", 2, 100), LineItem("b", 1, 50)))
    assert [line.sku for line in quote.lines] == ["a", "b"]
    assert [line.quantity for line in quote.lines] == [2, 1]
    assert [line.unit_cents for line in quote.lines] == [100, 50]


def test_cart_helpers() -> None:
    basket = cart(LineItem("a", 2, 100), LineItem("b", 3, 100))
    assert basket.total_units() == 5
    assert basket.skus() == ("a", "b")


def test_round_half_up_handles_negatives_and_exact_halves() -> None:
    assert round_half_up(5, 2) == 3
    assert round_half_up(-5, 2) == -3
    assert round_half_up(4, 2) == 2
    assert round_half_up(1, 3) == 0
    assert round_half_up(2, 3) == 1


def test_money_formatting_round_trip() -> None:
    assert format_cents(1234) == "12.34"
    assert format_cents(-5) == "-0.05"
    assert format_cents(0) == "0.00"
    assert parse_cents("12.34") == 1234
    assert parse_cents(" 7 ") == 700
    assert parse_cents("-0.05") == -5


@pytest.mark.parametrize("text", ["12.3", "1,234.56", "abc", "", "1.234", "+5"])
def test_parse_cents_rejects_sloppy_input(text: str) -> None:
    with pytest.raises(ValueError):
        parse_cents(text)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"tax_rate_bp": 10_001},
        {"tax_rate_bp": -1},
        {"shipping_cents": -1},
    ],
)
def test_cart_rejects_impossible_values(kwargs: dict[str, int]) -> None:
    with pytest.raises(ValueError):
        Cart(lines=(), **kwargs)


@pytest.mark.parametrize(
    ("sku", "quantity", "unit_cents"),
    [("", 1, 100), ("a", 0, 100), ("a", 1, -1)],
)
def test_line_item_rejects_impossible_values(sku: str, quantity: int, unit_cents: int) -> None:
    with pytest.raises(ValueError):
        LineItem(sku, quantity, unit_cents)


def test_discounts_validate_their_own_arguments() -> None:
    with pytest.raises(ValueError):
        PercentOff(101)
    with pytest.raises(ValueError):
        PercentOff(-1)
    with pytest.raises(ValueError):
        FixedOff(-1)
