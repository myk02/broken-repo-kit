"""Stock levels and reservations.

A shop cannot simply decrement stock when a customer opens the checkout: the
customer may never pay, and meanwhile the last unit is held hostage. This
module keeps *stock* (what the warehouse has) and *holds* (what open checkouts
have claimed) apart. ``available`` is the difference.

Reservation identifiers are generated from a per-instance counter rather than
from a UUID so that behaviour is reproducible in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping

__all__ = [
    "Inventory",
    "InventoryError",
    "OutOfStock",
    "Reservation",
    "ReservationError",
    "UnknownSku",
]

HELD = "held"
COMMITTED = "committed"
RELEASED = "released"


class InventoryError(Exception):
    """Base class for every inventory problem."""


class UnknownSku(InventoryError):
    """Raised when a sku is not in the catalogue at all."""

    def __init__(self, sku: str) -> None:
        super().__init__(f"unknown sku: {sku!r}")
        self.sku = sku


class OutOfStock(InventoryError):
    """Raised when a reservation asks for more units than are available."""

    def __init__(self, sku: str, requested: int, available: int) -> None:
        super().__init__(f"cannot reserve {requested} of {sku!r}: only {available} available")
        self.sku = sku
        self.requested = requested
        self.available = available


class ReservationError(InventoryError):
    """Raised when a reservation is used in a state that does not allow it."""


@dataclass(frozen=True)
class Reservation:
    """A claim on a number of units of one sku."""

    id: str
    sku: str
    quantity: int
    status: str

    @property
    def is_open(self) -> bool:
        """True while the reservation still holds stock."""
        return self.status == HELD


class Inventory:
    """Stock levels for a small catalogue, with reservations on top."""

    def __init__(self, stock: Mapping[str, int] | Iterable[tuple[str, int]]) -> None:
        items = stock.items() if isinstance(stock, Mapping) else stock
        self._stock: dict[str, int] = {}
        for sku, quantity in items:
            if not sku:
                raise ValueError("sku must not be empty")
            if quantity < 0:
                raise ValueError(f"stock for {sku!r} must not be negative")
            if sku in self._stock:
                raise ValueError(f"duplicate sku: {sku!r}")
            self._stock[sku] = quantity
        self._reservations: dict[str, Reservation] = {}
        self._counter = 0

    def stock_of(self, sku: str) -> int:
        """Units physically in the warehouse, ignoring open reservations."""
        self._require_sku(sku)
        return self._stock[sku]

    def available(self, sku: str) -> int:
        """Units that a new reservation could take right now."""
        self._require_sku(sku)
        held = sum(
            reservation.quantity
            for reservation in self._reservations.values()
            if reservation.sku == sku and reservation.is_open
        )
        return self._stock[sku] - held

    def reserve(self, sku: str, quantity: int) -> Reservation:
        """Hold ``quantity`` units of ``sku`` and return the reservation."""
        if quantity < 1:
            raise ValueError("quantity must be at least 1")
        self._require_sku(sku)
        available = self.available(sku)
        if quantity > available:
            raise OutOfStock(sku, quantity, available)
        self._counter += 1
        reservation = Reservation(
            id=f"res-{self._counter}",
            sku=sku,
            quantity=quantity,
            status=HELD,
        )
        self._reservations[reservation.id] = reservation
        return reservation

    def release(self, reservation_id: str) -> Reservation:
        """Drop a hold, returning the units to availability."""
        reservation = self._require_reservation(reservation_id)
        if reservation.status != HELD:
            raise ReservationError(
                f"reservation {reservation_id!r} is {reservation.status}, not {HELD}"
            )
        updated = Reservation(reservation.id, reservation.sku, reservation.quantity, RELEASED)
        self._reservations[reservation.id] = updated
        return updated

    def commit(self, reservation_id: str) -> Reservation:
        """Turn a hold into a real sale, removing the units from stock."""
        reservation = self._require_reservation(reservation_id)
        if reservation.status != HELD:
            raise ReservationError(
                f"reservation {reservation_id!r} is {reservation.status}, not {HELD}"
            )
        self._stock[reservation.sku] -= reservation.quantity
        updated = Reservation(
            reservation.id, reservation.sku, reservation.quantity, COMMITTED
        )
        self._reservations[reservation.id] = updated
        return updated

    def reservation(self, reservation_id: str) -> Reservation:
        """Look up one reservation by id."""
        return self._require_reservation(reservation_id)

    def low_stock(self, threshold: int) -> tuple[str, ...]:
        """Skus whose available count is strictly below ``threshold``, sorted."""
        return tuple(sorted(sku for sku in self._stock if self.available(sku) < threshold))

    def snapshot(self) -> dict[str, int]:
        """A copy of the stock levels, for logging and admin screens."""
        return dict(sorted(self._stock.items()))

    def _require_sku(self, sku: str) -> None:
        if sku not in self._stock:
            raise UnknownSku(sku)

    def _require_reservation(self, reservation_id: str) -> Reservation:
        try:
            return self._reservations[reservation_id]
        except KeyError:
            raise ReservationError(f"no such reservation: {reservation_id!r}") from None
