"""Order pricing for minishop.

All money is handled in **integer cents**. There are no floats anywhere in this
module, on purpose: ``0.1 + 0.2 != 0.3`` is not a fun way to lose a customer's
cent.

A cart is priced in this order:

1. the subtotal is the sum of ``quantity * unit_cents`` over the lines;
2. discounts are applied to the running amount, percentage discounts first and
   fixed-amount discounts second (``Discount.order``), each rounded half up
   where it produces a fraction of a cent;
3. tax is charged once, on the amount that is left after every discount, at
   ``tax_rate_bp`` basis points, rounded half up;
4. shipping is added at the end and is never taxed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import ClassVar, Protocol

__all__ = [
    "BASIS_POINTS",
    "Cart",
    "Cents",
    "Discount",
    "FixedOff",
    "LineItem",
    "PercentOff",
    "Quote",
    "QuoteLine",
    "format_cents",
    "parse_cents",
    "quote_cart",
    "round_half_up",
]

Cents = int
BASIS_POINTS = 10_000
_CENTS_PATTERN = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]{2})?$")


def round_half_up(numerator: int, denominator: int) -> int:
    """Divide two integers and round exact halves away from zero.

    ``round_half_up(5, 2) == 3`` and ``round_half_up(-5, 2) == -3``. Python's
    built-in :func:`round` is not used because it rounds halves to even, which
    would make money depend on whether an amount happens to be odd.
    """
    if denominator <= 0:
        raise ValueError("denominator must be positive")
    sign = -1 if numerator < 0 else 1
    magnitude = abs(numerator)
    return sign * ((2 * magnitude + denominator) // (2 * denominator))


def parse_cents(text: str) -> Cents:
    """Parse a decimal money string such as ``"12.34"`` into integer cents.

    Only a plain optional minus sign, digits and (optionally) exactly two
    decimals are accepted. ``"12.3"`` is rejected rather than guessed at.
    """
    cleaned = text.strip()
    if not _CENTS_PATTERN.match(cleaned):
        raise ValueError(f"not a money amount: {text!r}")
    negative = cleaned.startswith("-")
    body = cleaned[1:] if negative else cleaned
    whole, _, fraction = body.partition(".")
    cents = int(whole) * 100 + int(fraction or "0")
    return -cents if negative else cents


def format_cents(cents: Cents) -> str:
    """Format integer cents as a decimal string, e.g. ``-5`` becomes ``"-0.05"``."""
    sign = "-" if cents < 0 else ""
    magnitude = abs(cents)
    return f"{sign}{magnitude // 100}.{magnitude % 100:02d}"


class Discount(Protocol):
    """Something that reduces a running amount.

    ``order`` decides when the discount is applied: lower values run first, and
    discounts with equal order keep the order they were listed in.
    """

    order: int

    def apply(self, amount_cents: Cents) -> Cents:
        """Return the amount that remains after this discount."""


@dataclass(frozen=True)
class PercentOff:
    """Take an integer percentage off the running amount."""

    percent: int
    order: ClassVar[int] = 0

    def __post_init__(self) -> None:
        if not 0 <= self.percent <= 100:
            raise ValueError("percent must be between 0 and 100")

    def apply(self, amount_cents: Cents) -> Cents:
        if amount_cents < 0:
            raise ValueError("cannot discount a negative amount")
        return amount_cents - round_half_up(amount_cents * self.percent, 100)


@dataclass(frozen=True)
class FixedOff:
    """Take a fixed number of cents off the running amount, never below zero."""

    cents: Cents
    order: ClassVar[int] = 1

    def __post_init__(self) -> None:
        if self.cents < 0:
            raise ValueError("a fixed discount cannot be negative")

    def apply(self, amount_cents: Cents) -> Cents:
        if amount_cents < 0:
            raise ValueError("cannot discount a negative amount")
        return max(0, amount_cents - self.cents)


@dataclass(frozen=True)
class LineItem:
    """One cart line: a sku, a quantity and a unit price in cents."""

    sku: str
    quantity: int
    unit_cents: Cents

    def __post_init__(self) -> None:
        if not self.sku:
            raise ValueError("sku must not be empty")
        if self.quantity < 1:
            raise ValueError("quantity must be at least 1")
        if self.unit_cents < 0:
            raise ValueError("unit price must not be negative")

    @property
    def subtotal_cents(self) -> Cents:
        """``quantity * unit_cents`` for this line."""
        return self.quantity * self.unit_cents


@dataclass(frozen=True)
class Cart:
    """A cart: lines, discounts, a tax rate in basis points and shipping."""

    lines: tuple[LineItem, ...] = ()
    discounts: tuple[Discount, ...] = ()
    tax_rate_bp: int = 0
    shipping_cents: Cents = 0

    def __post_init__(self) -> None:
        object.__setattr__(self, "lines", tuple(self.lines))
        object.__setattr__(self, "discounts", tuple(self.discounts))
        if not 0 <= self.tax_rate_bp <= BASIS_POINTS:
            raise ValueError("tax_rate_bp must be between 0 and 10000")
        if self.shipping_cents < 0:
            raise ValueError("shipping must not be negative")

    @property
    def subtotal_cents(self) -> Cents:
        """Sum of the line subtotals, before any discount."""
        return sum(line.subtotal_cents for line in self.lines)

    def total_units(self) -> int:
        """Total number of physical items in the cart."""
        return sum(line.quantity for line in self.lines)

    def skus(self) -> tuple[str, ...]:
        """Sku of every line, in cart order, without duplicates removed."""
        return tuple(line.sku for line in self.lines)


@dataclass(frozen=True)
class QuoteLine:
    """The priced view of one cart line."""

    sku: str
    quantity: int
    unit_cents: Cents
    subtotal_cents: Cents


@dataclass(frozen=True)
class Quote:
    """The result of pricing a cart. Every field is in integer cents."""

    subtotal_cents: Cents
    discount_cents: Cents
    taxable_cents: Cents
    tax_cents: Cents
    shipping_cents: Cents
    total_cents: Cents
    lines: tuple[QuoteLine, ...]


def quote_cart(cart: Cart) -> Quote:
    """Price a cart according to the rules at the top of this module."""
    subtotal = cart.subtotal_cents
    running = subtotal
    # Percentage discounts come before fixed ones because a percentage of the
    # full basket is what the customer was promised; taking the fixed amount
    # off first would quietly shrink the percentage. ``sorted`` is stable, so
    # discounts of the same kind keep the order they were listed in.
    for discount in sorted(cart.discounts, key=lambda discount: discount.order):
        running = discount.apply(running)
    discount_total = subtotal - running
    tax = round_half_up(running * cart.tax_rate_bp, BASIS_POINTS)
    total = running + tax + cart.shipping_cents
    lines = tuple(
        QuoteLine(
            sku=line.sku,
            quantity=line.quantity,
            unit_cents=line.unit_cents,
            subtotal_cents=line.subtotal_cents,
        )
        for line in cart.lines
    )
    return Quote(
        subtotal_cents=subtotal,
        discount_cents=discount_total,
        taxable_cents=running,
        tax_cents=tax,
        shipping_cents=cart.shipping_cents,
        total_cents=total,
        lines=lines,
    )
