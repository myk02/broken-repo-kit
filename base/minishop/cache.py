"""A tiny TTL + LRU cache with an injected clock.

The cache never reads the wall clock itself. It asks the callable passed as
``clock`` for an integer "tick", which makes every expiry test exact and
repeatable: tests advance a counter, they never sleep.

Two rules define the behaviour:

* **Expiry.** An entry written at tick ``t`` with ``ttl`` lives for ticks
  ``t, t + 1, ..., t + ttl - 1``. At ``t + ttl`` it is gone. In other words it
  is live while ``now < written_at + ttl``.
* **Recency.** Reading an entry with :meth:`TtlLruCache.get` makes it the most
  recently used entry, so it is the last one to be evicted. Inspecting the
  cache without touching recency is what :meth:`TtlLruCache.peek` is for.

When the cache is full, the least recently used entry is evicted. Writes count
as use, so rewriting a key makes it the most recent entry again.
"""

from __future__ import annotations

from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Generic, TypeVar, overload

__all__ = ["CacheStats", "TtlLruCache"]

K = TypeVar("K")
V = TypeVar("V")


@dataclass(frozen=True)
class CacheStats:
    """Counters describing how the cache has been used."""

    hits: int
    misses: int
    evictions: int
    expirations: int

    @property
    def lookups(self) -> int:
        """Total number of ``get`` calls that were counted."""
        return self.hits + self.misses


_MISSING: object = object()


@dataclass(frozen=True)
class _Entry(Generic[V]):
    value: V
    written_at: int
    expires_at: int


class TtlLruCache(Generic[K, V]):
    """A bounded cache where entries expire after a number of clock ticks."""

    def __init__(self, *, capacity: int, ttl: int, clock: Callable[[], int]) -> None:
        if capacity < 1:
            raise ValueError("capacity must be at least 1")
        if ttl < 0:
            raise ValueError("ttl must not be negative")
        if not callable(clock):
            raise TypeError("clock must be callable")
        self._capacity = capacity
        self._ttl = ttl
        self._clock = clock
        self._entries: OrderedDict[K, _Entry[V]] = OrderedDict()
        self._hits = 0
        self._misses = 0
        self._evictions = 0
        self._expirations = 0

    @property
    def capacity(self) -> int:
        """Maximum number of entries held at once."""
        return self._capacity

    @property
    def ttl(self) -> int:
        """Lifetime of an entry, in clock ticks."""
        return self._ttl

    def __len__(self) -> int:
        """Number of live entries right now."""
        self.purge_expired()
        return len(self._entries)

    def __contains__(self, key: object) -> bool:
        """True if ``key`` is present and still live. Does not touch recency."""
        entry = self._entries.get(key)  # type: ignore[arg-type]
        if entry is None:
            return False
        if self._is_expired(entry):
            del self._entries[key]  # type: ignore[arg-type]
            self._expirations += 1
            return False
        return True

    @overload
    def get(self, key: K) -> V: ...

    @overload
    def get(self, key: K, default: V) -> V: ...

    def get(self, key: K, default: V | object = _MISSING) -> V:
        """Return the live value for ``key`` and mark it as most recently used.

        Raises :class:`KeyError` when the key is missing or expired, unless a
        ``default`` is given.
        """
        entry = self._entries.get(key)
        if entry is None or self._is_expired(entry):
            if entry is not None:
                del self._entries[key]
                self._expirations += 1
            self._misses += 1
            if default is _MISSING:
                raise KeyError(key)
            return default  # type: ignore[return-value]
        self._hits += 1
        self._entries.move_to_end(key)
        return entry.value

    def peek(self, key: K, default: V | object = _MISSING) -> V:
        """Like :meth:`get`, but does not change which entry is most recent."""
        entry = self._entries.get(key)
        if entry is None or self._is_expired(entry):
            if entry is not None:
                del self._entries[key]
                self._expirations += 1
            self._misses += 1
            if default is _MISSING:
                raise KeyError(key)
            return default  # type: ignore[return-value]
        self._hits += 1
        return entry.value

    def set(self, key: K, value: V) -> None:
        """Store ``value`` and make ``key`` the most recently used entry."""
        now = self._clock()
        if key in self._entries:
            del self._entries[key]
        self._entries[key] = _Entry(value=value, written_at=now, expires_at=now + self._ttl)
        while len(self._entries) > self._capacity:
            self._entries.popitem(last=False)
            self._evictions += 1

    def delete(self, key: K) -> bool:
        """Remove ``key`` if present. Returns whether anything was removed."""
        return self._entries.pop(key, None) is not None

    def clear(self) -> None:
        """Drop every entry. Counters are kept."""
        self._entries.clear()

    def purge_expired(self) -> int:
        """Drop expired entries and return how many were dropped."""
        now = self._clock()
        stale = [key for key, entry in self._entries.items() if now >= entry.expires_at]
        for key in stale:
            del self._entries[key]
        self._expirations += len(stale)
        return len(stale)

    def keys(self) -> tuple[K, ...]:
        """Live keys, most recently used first. Does not change recency."""
        self.purge_expired()
        return tuple(reversed(self._entries))

    def stats(self) -> CacheStats:
        """A snapshot of the counters."""
        return CacheStats(
            hits=self._hits,
            misses=self._misses,
            evictions=self._evictions,
            expirations=self._expirations,
        )

    def _is_expired(self, entry: _Entry[V]) -> bool:
        return self._clock() >= entry.expires_at
