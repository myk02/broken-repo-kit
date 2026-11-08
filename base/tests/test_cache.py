"""Visible tests for minishop.cache.

The clock is a plain counter. No test in this file reads the wall clock or
sleeps, so results are identical on every machine.
"""

from __future__ import annotations

import pytest

from minishop.cache import TtlLruCache


class FakeClock:
    """A clock that only moves when a test moves it."""

    def __init__(self) -> None:
        self.now = 0

    def __call__(self) -> int:
        return self.now

    def advance(self, ticks: int = 1) -> None:
        """Move the clock forward."""
        self.now += ticks


def make_cache(clock: FakeClock, *, capacity: int = 3, ttl: int = 10) -> TtlLruCache[str, str]:
    """Build a cache wired to ``clock``."""
    return TtlLruCache(capacity=capacity, ttl=ttl, clock=clock)


def test_set_then_get_returns_the_value() -> None:
    cache = make_cache(FakeClock())
    cache.set("a", "alpha")
    assert cache.get("a") == "alpha"


def test_missing_key_raises_or_returns_the_default() -> None:
    cache = make_cache(FakeClock())
    with pytest.raises(KeyError):
        cache.get("nope")
    assert cache.get("nope", "fallback") == "fallback"


def test_peek_reads_without_raising() -> None:
    cache = make_cache(FakeClock())
    cache.set("a", "alpha")
    assert cache.peek("a") == "alpha"
    assert cache.peek("missing", "fallback") == "fallback"


def test_capacity_evicts_the_oldest_entry() -> None:
    cache = make_cache(FakeClock(), capacity=2)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.set("c", 3)
    assert "a" not in cache
    assert cache.get("b") == 2
    assert cache.get("c") == 3
    assert cache.stats().evictions == 1


def test_writing_an_existing_key_replaces_the_value() -> None:
    cache = make_cache(FakeClock())
    cache.set("a", 1)
    cache.set("a", 2)
    assert cache.get("a") == 2
    assert len(cache) == 1


def test_entries_expire_after_the_ttl() -> None:
    clock = FakeClock()
    cache = make_cache(clock, ttl=5)
    cache.set("a", "alpha")
    clock.advance(2)
    assert cache.get("a") == "alpha"
    clock.advance(8)
    assert cache.get("a", "gone") == "gone"
    assert cache.stats().expirations == 1


def test_purge_expired_reports_how_many_were_dropped() -> None:
    clock = FakeClock()
    cache = make_cache(clock, ttl=3)
    cache.set("a", 1)
    cache.set("b", 2)
    clock.advance(100)
    assert cache.purge_expired() == 2
    assert len(cache) == 0


def test_stats_count_hits_and_misses() -> None:
    cache = make_cache(FakeClock())
    cache.set("a", 1)
    cache.get("a")
    cache.get("b", None)
    stats = cache.stats()
    assert stats.hits == 1
    assert stats.misses == 1
    assert stats.lookups == 2


def test_delete_reports_whether_anything_was_removed() -> None:
    cache = make_cache(FakeClock())
    cache.set("a", 1)
    assert cache.delete("a") is True
    assert cache.delete("a") is False


def test_clear_empties_the_cache() -> None:
    cache = make_cache(FakeClock())
    cache.set("a", 1)
    cache.set("b", 2)
    cache.clear()
    assert len(cache) == 0


def test_keys_lists_live_entries() -> None:
    cache = make_cache(FakeClock())
    cache.set("a", 1)
    cache.set("b", 2)
    assert cache.keys() == ("b", "a")


def test_constructor_validates_its_arguments() -> None:
    with pytest.raises(ValueError):
        TtlLruCache(capacity=0, ttl=1, clock=lambda: 0)
    with pytest.raises(ValueError):
        TtlLruCache(capacity=1, ttl=-1, clock=lambda: 0)
    with pytest.raises(TypeError):
        TtlLruCache(capacity=1, ttl=1, clock=42)  # type: ignore[arg-type]
