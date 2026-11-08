"""Pass-to-pass checks for 004-slow-duplicates."""

from __future__ import annotations

from minishop.search import Product, find_duplicates


def test_group_order_is_first_occurrence_order() -> None:
    products = [
        Product("z2", "Zed", 100),
        Product("a2", "Alpha", 100),
        Product("z1", "Zed", 100),
        Product("a1", "Alpha", 100),
        Product("q1", "Unique", 100),
    ]
    assert find_duplicates(products) == [["z1", "z2"], ["a1", "a2"]]


def test_group_members_are_sorted_by_sku() -> None:
    products = [
        Product("c", "Tea", 500),
        Product("a", "Tea", 500),
        Product("b", "Tea", 500),
    ]
    assert find_duplicates(products) == [["a", "b", "c"]]


def test_empty_unique_and_singleton_inputs() -> None:
    assert find_duplicates([]) == []
    assert find_duplicates([Product("a", "A", 1)]) == []
    assert find_duplicates([Product("a", "A", 1), Product("b", "B", 2)]) == []


def test_custom_key_is_supported() -> None:
    products = [
        Product("sku-1", "Mug", 1200),
        Product("sku-2", "Mug", 900),
        Product("sku-3", "Tea", 900),
    ]
    assert find_duplicates(products, key=lambda product: product.price_cents) == [
        ["sku-2", "sku-3"]
    ]


def test_one_shot_iterable_is_consumed_once() -> None:
    products = [Product("a", "Tea", 1), Product("b", "Tea", 1)]

    def stream():
        yield from products

    assert find_duplicates(stream()) == [["a", "b"]]


def test_large_corpus_matches_the_oracle() -> None:
    products = [Product(f"p-{index:04d}", f"Name {index % 13}", 100 + index % 3) for index in range(320)]
    expected_order: list[int] = []
    expected: dict[int, list[str]] = {}
    for product in products:
        signature = (product.name.casefold(), product.price_cents)
        if signature not in expected:
            expected[signature] = []
            expected_order.append(signature)
        expected[signature].append(product.sku)
    oracle = [sorted(expected[s]) for s in expected_order if len(expected[s]) > 1]
    assert find_duplicates(products) == oracle


def test_input_list_is_not_mutated() -> None:
    products = [Product("b", "Tea", 1), Product("a", "Tea", 1)]
    before = list(products)
    find_duplicates(products)
    assert products == before
