"""Fail-to-pass checks for 005-coupon-feature."""

from __future__ import annotations

import random

import pytest

from minishop import pricing
from minishop.pricing import Cart, FixedOff, LineItem, PercentOff, quote_cart


class Clock:
    """A clock that only moves when a test moves it."""

    def __init__(self, now: int = 0) -> None:
        self.now = now

    def __call__(self) -> int:
        return self.now


def cart(
    subtotal: int,
    *discounts: object,
    tax_rate_bp: int = 0,
    shipping_cents: int = 0,
) -> Cart:
    return Cart(
        lines=(LineItem("a", 1, subtotal),),
        discounts=discounts,  # type: ignore[arg-type]
        tax_rate_bp=tax_rate_bp,
        shipping_cents=shipping_cents,
    )


def book(*coupons: pricing.Coupon, now: int = 0) -> pricing.CouponBook:
    return pricing.CouponBook(coupons, clock=Clock(now))


def test_percent_coupon_applies_after_cart_discounts() -> None:
    quote = quote_cart(
        cart(1000, PercentOff(10), tax_rate_bp=1000),
        coupons=book(pricing.Coupon("SAVE10", percent=10)),
        coupon_code="save10",
    )
    assert quote.discount_cents == 100
    assert quote.coupon_discount_cents == 90
    assert quote.taxable_cents == 810
    assert quote.tax_cents == 81
    assert quote.total_cents == 891
    assert quote.coupon_code == "SAVE10"


def test_fixed_coupon_and_shipping() -> None:
    quote = quote_cart(
        cart(1000, FixedOff(100), tax_rate_bp=1000, shipping_cents=499),
        coupons=book(pricing.Coupon("TENNER", fixed_cents=250)),
        coupon_code="TENNER",
    )
    assert quote.coupon_discount_cents == 250
    assert quote.taxable_cents == 650
    assert quote.tax_cents == 65
    assert quote.total_cents == 1214


def test_coupon_is_capped_at_the_remaining_amount() -> None:
    quote = quote_cart(
        cart(300, tax_rate_bp=1000),
        coupons=book(pricing.Coupon("BIG", fixed_cents=1000)),
        coupon_code="BIG",
    )
    assert quote.coupon_discount_cents == 300
    assert quote.taxable_cents == 0
    assert quote.tax_cents == 0
    assert quote.total_cents == 0


def test_percentage_coupon_rounds_half_up() -> None:
    quote = quote_cart(
        cart(1005),
        coupons=book(pricing.Coupon("TEN", percent=10)),
        coupon_code="TEN",
    )
    assert quote.coupon_discount_cents == 101
    assert quote.taxable_cents == 904


def test_minimum_spend_is_measured_before_discounts() -> None:
    coupon = pricing.Coupon("MIN950", fixed_cents=50, min_spend_cents=950)
    quote = quote_cart(
        cart(1000, PercentOff(10)),
        coupons=book(coupon),
        coupon_code="min950",
    )
    assert quote.taxable_cents == 850
    assert quote.coupon_discount_cents == 50

    with pytest.raises(pricing.CouponMinimumNotMet) as excinfo:
        quote_cart(cart(949), coupons=book(coupon), coupon_code="MIN950")
    assert excinfo.value.code == "MIN950"
    assert excinfo.value.required_cents == 950
    assert excinfo.value.actual_cents == 949


def test_expiry_is_inclusive_on_the_last_tick() -> None:
    clock = Clock(10)
    coupons = pricing.CouponBook([pricing.Coupon("LAST", percent=10, expires_on=10)], clock=clock)
    assert quote_cart(cart(1000), coupons=coupons, coupon_code="LAST").coupon_discount_cents == 100
    clock.now = 11
    with pytest.raises(pricing.ExpiredCoupon) as excinfo:
        quote_cart(cart(1000), coupons=coupons, coupon_code="LAST")
    assert excinfo.value.expires_on == 10
    assert excinfo.value.now == 11


def test_unknown_blank_and_case_insensitive_codes() -> None:
    coupons = book(pricing.Coupon("  Save10  ", percent=10))
    assert quote_cart(cart(1000), coupons=coupons, coupon_code=" sAvE10 ").coupon_code == "Save10"
    for code in ("nope", "   "):
        with pytest.raises(pricing.UnknownCoupon):
            coupons.resolve(code, subtotal_cents=1000)


def test_duplicate_codes_differing_only_by_case_are_rejected() -> None:
    with pytest.raises(ValueError):
        book(pricing.Coupon("DUP", percent=10), pricing.Coupon("dup", fixed_cents=100))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"code": ""},
        {"code": "x", "percent": 0},
        {"code": "x", "percent": 101},
        {"code": "x", "fixed_cents": 0},
        {"code": "x", "fixed_cents": -1},
        {"code": "x", "percent": 10, "fixed_cents": 100},
        {"code": "x", "min_spend_cents": -1},
    ],
)
def test_invalid_coupon_definitions_are_rejected(kwargs: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        pricing.Coupon(**kwargs)  # type: ignore[arg-type]


def test_expiry_must_be_an_integer_tick_or_none() -> None:
    with pytest.raises(TypeError):
        pricing.Coupon("X", percent=10, expires_on="2026-01-01")  # type: ignore[arg-type]


def test_coupon_needs_a_book_and_a_string_code() -> None:
    with pytest.raises(pricing.CouponError):
        quote_cart(cart(1000), coupon_code="SAVE10")
    with pytest.raises(pricing.CouponError):
        quote_cart(cart(1000), coupons=book(pricing.Coupon("SAVE10", percent=10)), coupon_code=["SAVE10"])  # type: ignore[arg-type]


def test_coupon_book_requires_a_callable_clock() -> None:
    with pytest.raises(TypeError):
        pricing.CouponBook([], clock=42)  # type: ignore[arg-type]


def test_coupon_on_an_empty_cart() -> None:
    empty = Cart(lines=())
    quote = quote_cart(
        empty,
        coupons=book(pricing.Coupon("FREE", percent=50)),
        coupon_code="FREE",
    )
    assert quote.coupon_discount_cents == 0
    assert quote.total_cents == 0


def test_seeded_coupon_quotes_match_the_reference() -> None:
    rng = random.Random(20260202)
    clock = Clock(0)
    for _ in range(60):
        subtotal = rng.randrange(0, 50_001)
        percent = rng.randrange(10, 60)
        fixed = rng.randrange(0, 5001)
        minimum = rng.randrange(0, max(1, subtotal + 1))
        tax_rate = rng.randrange(0, 3001)
        shipping = rng.randrange(0, 1001)
        coupon = pricing.Coupon("C", percent=percent, min_spend_cents=minimum)
        coupons = pricing.CouponBook([coupon], clock=clock)
        quote = quote_cart(
            cart(subtotal, PercentOff(7), FixedOff(3), tax_rate_bp=tax_rate, shipping_cents=shipping),
            coupons=coupons,
            coupon_code="c",
        )

        def half_up(numerator: int, denominator: int) -> int:
            return (2 * numerator + denominator) // (2 * denominator)

        after_cart = subtotal - half_up(subtotal * 7, 100)
        after_cart = max(0, after_cart - 3)
        expected_coupon = min(after_cart, half_up(after_cart * percent, 100))
        expected_taxable = after_cart - expected_coupon
        expected_tax = half_up(expected_taxable * tax_rate, 10_000)
        assert quote.coupon_discount_cents == expected_coupon
        assert quote.taxable_cents == expected_taxable
        assert quote.tax_cents == expected_tax
        assert quote.total_cents == expected_taxable + expected_tax + shipping
