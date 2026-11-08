"""Fail-to-pass checks for 004-slow-duplicates.

Cost is measured in operations through the injected key, never in seconds.
"""

from __future__ import annotations

from minishop.search import Product, dedupe_key, find_duplicates


class Counter:
    """A mutable operation counter shared by probes."""

    def __init__(self) -> None:
        self.ops = 0


class Probe:
    """A hashable key value that counts every operation done on it."""

    __slots__ = ("value", "counter")

    def __init__(self, value: int, counter: Counter) -> None:
        self.value = value
        self.counter = counter

    def __hash__(self) -> int:
        self.counter.ops += 1
        return hash(self.value)

    def __eq__(self, other: object) -> bool:
        self.counter.ops += 1
        if isinstance(other, Probe):
            return self.value == other.value
        return NotImplemented

    def __lt__(self, other: object) -> bool:
        self.counter.ops += 1
        if isinstance(other, Probe):
            return self.value < other.value
        return NotImplemented


def group_of(index: int) -> int:
    """Mostly-unique keys, with a duplicate every 97th product."""
    return index if index % 97 else index - 1


def catalogue(size: int) -> list[Product]:
    """A deterministic catalogue with sparse duplicates spread through the input."""
    return [
        Product(f"sku-{index:05d}", f"Item {index}", 100 + index % 17)
        for index in range(size)
    ]


def measure(size: int) -> tuple[int, int]:
    """Return (probe operations, key calls) for one input size."""
    counter = Counter()
    calls = 0
    products = catalogue(size)

    def key(product: Product) -> Probe:
        nonlocal calls
        calls += 1
        return Probe(group_of(int(product.sku.split("-")[1])), counter)

    find_duplicates(products, key=key)
    return counter.ops, calls


def test_work_grows_near_linearly_not_quadratically() -> None:
    small_ops, _ = measure(64)
    medium_ops, _ = measure(256)
    large_ops, _ = measure(768)

    assert small_ops > 0
    # 4x the input. Linear-ish work stays near 4x; every-pair work is ~16x.
    assert medium_ops <= 8 * small_ops, (small_ops, medium_ops)
    # 3x the input. Quadratic work is ~9x; n log n stays below 6x.
    assert large_ops <= 6 * medium_ops, (medium_ops, large_ops)


def test_absolute_operation_budget() -> None:
    for size in (64, 256, 768):
        ops, _ = measure(size)
        # Generous: n hashes plus an O(n log n) sort is far below this.
        assert ops <= 12 * size * size.bit_length() + 500, (size, ops)


def test_key_is_not_called_for_every_pair() -> None:
    for size in (64, 256, 768):
        _, calls = measure(size)
        assert calls <= 3 * size, (size, calls)


def test_default_key_also_stays_within_budget() -> None:
    class CountingString(str):
        """A string that counts comparisons, for the default dedupe key."""

        ops = 0

        def __eq__(self, other: object) -> bool:
            type(self).ops += 1
            return str.__eq__(self, other)

        def __hash__(self) -> int:
            type(self).ops += 1
            return str.__hash__(self)

    products = [
        Product(
            f"s-{index}",
            f"Name {index - 1 if index and index % 50 == 0 else index}",
            100,
        )
        for index in range(512)
    ]
    find_duplicates(products, key=lambda product: (CountingString(product.name), product.price_cents))
    assert CountingString.ops <= 12 * 512 * 10 + 500
