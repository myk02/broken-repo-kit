"""Pass-to-pass checks for 002-cache-recency."""

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


def test_peek_does_not_refresh_recency() -> None:
    clock = Clock()
    store = cache(clock, capacity=2)
    store.set("a", "A")
    store.set("b", "B")
    assert store.peek("a") == "A"
    store.set("c", "C")
    with pytest.raises(KeyError):
        store.get("a")
    assert store.get("b") == "B"
    assert store.get("c") == "C"


def test_writing_an_existing_key_refreshes_recency() -> None:
    clock = Clock()
    store = cache(clock, capacity=2)
    store.set("a", "A")
    store.set("b", "B")
    store.set("a", "A2")
    store.set("c", "C")
    assert store.get("a") == "A2"
    with pytest.raises(KeyError):
        store.get("b")


def test_peek_and_delete_still_work() -> None:
    clock = Clock()
    store = cache(clock)
    store.set("a", "A")
    assert store.peek("a") == "A"
    assert store.peek("missing", "fallback") == "fallback"
    assert store.delete("a") is True
    assert store.delete("a") is False


def test_clear_and_stats_still_work() -> None:
    clock = Clock()
    store = cache(clock)
    store.set("a", "A")
    store.set("b", "B")
    assert store.stats().lookups == 0
    store.clear()
    assert len(store) == 0
    assert store.stats().evictions == 0


def test_constructor_validation_is_unchanged() -> None:
    with pytest.raises(ValueError):
        TtlLruCache(capacity=0, ttl=1, clock=lambda: 0)
    with pytest.raises(ValueError):
        TtlLruCache(capacity=1, ttl=-1, clock=lambda: 0)
    with pytest.raises(TypeError):
        TtlLruCache(capacity=1, ttl=1, clock=42)  # type: ignore[arg-type]
