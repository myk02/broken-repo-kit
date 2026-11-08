"""Visible tests for minishop.inventory."""

from __future__ import annotations

import pytest

from minishop.inventory import (
    COMMITTED,
    HELD,
    RELEASED,
    Inventory,
    OutOfStock,
    ReservationError,
    UnknownSku,
)


def make_inventory() -> Inventory:
    """A two-sku inventory used by most tests."""
    return Inventory({"sku-1": 5, "sku-2": 0})


def test_fresh_inventory_reports_stock_and_availability() -> None:
    inventory = make_inventory()
    assert inventory.stock_of("sku-1") == 5
    assert inventory.available("sku-1") == 5
    assert inventory.available("sku-2") == 0


def test_reserve_holds_units_without_taking_them_off_the_shelf() -> None:
    inventory = make_inventory()
    reservation = inventory.reserve("sku-1", 2)
    assert reservation.status == HELD
    assert reservation.quantity == 2
    assert inventory.stock_of("sku-1") == 5
    assert inventory.available("sku-1") == 3


def test_reservations_have_deterministic_ids() -> None:
    inventory = make_inventory()
    assert inventory.reserve("sku-1", 1).id == "res-1"
    assert inventory.reserve("sku-1", 1).id == "res-2"


def test_reserve_more_than_available_raises_out_of_stock() -> None:
    inventory = make_inventory()
    with pytest.raises(OutOfStock) as excinfo:
        inventory.reserve("sku-1", 6)
    assert excinfo.value.sku == "sku-1"
    assert excinfo.value.requested == 6
    assert excinfo.value.available == 5
    assert inventory.available("sku-1") == 5


def test_release_returns_the_units() -> None:
    inventory = make_inventory()
    reservation = inventory.reserve("sku-1", 4)
    released = inventory.release(reservation.id)
    assert released.status == RELEASED
    assert inventory.available("sku-1") == 5


def test_commit_removes_units_from_stock() -> None:
    inventory = make_inventory()
    reservation = inventory.reserve("sku-1", 2)
    committed = inventory.commit(reservation.id)
    assert committed.status == COMMITTED
    assert inventory.stock_of("sku-1") == 3
    assert inventory.available("sku-1") == 3


def test_commit_twice_is_rejected() -> None:
    inventory = make_inventory()
    reservation = inventory.reserve("sku-1", 1)
    inventory.commit(reservation.id)
    with pytest.raises(ReservationError):
        inventory.commit(reservation.id)


def test_release_after_commit_is_rejected() -> None:
    inventory = make_inventory()
    reservation = inventory.reserve("sku-1", 1)
    inventory.commit(reservation.id)
    with pytest.raises(ReservationError):
        inventory.release(reservation.id)


def test_unknown_sku_and_reservation_are_reported() -> None:
    inventory = make_inventory()
    with pytest.raises(UnknownSku):
        inventory.reserve("nope", 1)
    with pytest.raises(ReservationError):
        inventory.release("res-404")


def test_low_stock_lists_skus_below_the_threshold() -> None:
    inventory = Inventory({"a": 1, "b": 5, "c": 3})
    inventory.reserve("b", 3)
    assert inventory.low_stock(3) == ("a", "b")


def test_snapshot_is_a_sorted_copy() -> None:
    inventory = Inventory({"b": 1, "a": 2})
    snapshot = inventory.snapshot()
    assert snapshot == {"a": 2, "b": 1}
    snapshot["a"] = 99
    assert inventory.stock_of("a") == 2


def test_inventory_rejects_bad_initial_state() -> None:
    with pytest.raises(ValueError):
        Inventory({"a": -1})
    with pytest.raises(ValueError):
        Inventory([("a", 1), ("a", 2)])
    with pytest.raises(ValueError):
        Inventory({"": 1})


def test_reserve_rejects_non_positive_quantity() -> None:
    inventory = make_inventory()
    with pytest.raises(ValueError):
        inventory.reserve("sku-1", 0)
