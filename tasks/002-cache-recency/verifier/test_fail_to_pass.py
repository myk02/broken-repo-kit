"""Fail-to-pass checks for 002-cache-recency."""

from __future__ import annotations

import pytest

from minishop.cache import TtlLruCache


class Clock:
    """A clock that only moves when a test moves it."""

    def __init__(self) -> None:
        self.now = 0

    def __call__(self) -> int:
        return self.now

    def advance(self, ticks: int) -> None:
        self.now += ticks


def cache(clock: Clock, *, capacity: int = 3, ttl: int = 10) -> TtlLruCache[str, str]:
    return TtlLruCache(capacity=capacity, ttl=ttl, clock=clock)


def test_get_makes_an_entry_most_recent() -> None:
    clock = Clock()
    store = cache(clock, capacity=2)
    store.set("a", "A")
    store.set("b", "B")
    assert store.get("a") == "A"
    store.set("c", "C")
    assert store.get("a") == "A"
    assert store.get("c") == "C"
    with pytest.raises(KeyError):
        store.get("b")


def test_several_reads_move_the_whole_recency_order() -> None:
    clock = Clock()
    store = cache(clock, capacity=3)
    store.set("a", "A")
    store.set("b", "B")
    store.set("c", "C")
    store.get("a")
    store.get("b")
    store.set("d", "D")
    assert store.get("a") == "A"
    assert store.get("b") == "B"
    assert store.get("d") == "D"
    with pytest.raises(KeyError):
        store.get("c")


def test_entry_is_gone_at_the_exact_expiry_tick() -> None:
    clock = Clock()
    store = cache(clock, ttl=3)
    store.set("a", "A")
    clock.advance(2)
    assert store.get("a") == "A"
    clock.advance(1)
    assert store.get("a", "gone") == "gone"


def test_ttl_zero_is_immediately_dead() -> None:
    clock = Clock()
    store = cache(clock, ttl=0)
    store.set("a", "A")
    assert store.get("a", "gone") == "gone"
    assert len(store) == 0


def test_len_contains_and_keys_use_the_same_boundary() -> None:
    clock = Clock()
    store = cache(clock, ttl=2)
    store.set("a", "A")
    store.set("b", "B")
    clock.advance(2)
    assert "a" not in store
    assert len(store) == 0
    assert store.keys() == ()


def test_purge_reports_the_boundary_expiry() -> None:
    clock = Clock()
    store = cache(clock, ttl=3)
    store.set("a", "A")
    store.set("b", "B")
    clock.advance(3)
    assert store.purge_expired() == 2
    assert store.stats().expirations == 2


def test_boundary_read_is_a_miss_not_a_hit() -> None:
    clock = Clock()
    store = cache(clock, ttl=4)
    store.set("a", "A")
    clock.advance(4)
    assert store.get("a", None) is None
    assert store.stats().misses == 1
    assert store.stats().hits == 0
    assert store.stats().expirations == 1


def test_expiry_is_measured_from_the_last_write() -> None:
    clock = Clock()
    store = cache(clock, ttl=5)
    store.set("a", "old")
    clock.advance(4)
    store.set("a", "new")
    clock.advance(4)
    assert store.get("a") == "new"
    clock.advance(1)
    assert store.get("a", "gone") == "gone"


def test_get_does_not_extend_the_ttl() -> None:
    clock = Clock()
    store = cache(clock, ttl=5)
    store.set("a", "A")
    clock.advance(4)
    assert store.get("a") == "A"
    clock.advance(1)
    assert store.get("a", "gone") == "gone"
