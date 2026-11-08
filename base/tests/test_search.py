"""Visible tests for minishop.search."""

from __future__ import annotations

import pytest

from minishop.search import (
    Product,
    dedupe_key,
    filter_products,
    find_duplicates,
    normalize_name,
    paginate,
    sort_products,
)


def catalogue() -> list[Product]:
    """A small fixed catalogue, deliberately in a non-alphabetical order."""
    return [
        Product("sku-3", "Blue Mug", 1200, ("kitchen", "ceramic"), 450),
        Product("sku-1", "blue  mug", 1200, ("kitchen",), 300),
        Product("sku-2", "Red Kettle", 3500, ("kitchen", "steel"), 400),
        Product("sku-4", "Green Tea", 800, ("drink",), 350),
        Product("sku-5", "Green Tea", 900, ("drink",), 350),
    ]


def test_normalize_name_folds_case_and_whitespace() -> None:
    assert normalize_name("  Blue   MUG ") == "blue mug"
    assert normalize_name("Café Latte") == normalize_name("café  latte")


def test_filter_by_substring_query() -> None:
    found = filter_products(catalogue(), query="MUG")
    assert [product.sku for product in found] == ["sku-3", "sku-1"]


def test_filter_by_tags_requires_all_of_them() -> None:
    found = filter_products(catalogue(), tags=["Kitchen", "STEEL"])
    assert [product.sku for product in found] == ["sku-2"]
    assert filter_products(catalogue(), tags=["kitchen", "drink"]) == []


def test_filter_by_inclusive_price_bounds() -> None:
    found = filter_products(catalogue(), min_price_cents=900, max_price_cents=1200)
    assert [product.sku for product in found] == ["sku-3", "sku-1", "sku-5"]


def test_filter_without_filters_keeps_input_order() -> None:
    assert [product.sku for product in filter_products(catalogue())] == [
        "sku-3",
        "sku-1",
        "sku-2",
        "sku-4",
        "sku-5",
    ]


def test_sort_by_name_breaks_ties_by_sku() -> None:
    ordered = sort_products(catalogue(), key="name")
    assert [product.sku for product in ordered] == ["sku-1", "sku-3", "sku-4", "sku-5", "sku-2"]


def test_sort_by_price_descending_keeps_sku_ties_ascending() -> None:
    ordered = sort_products(catalogue(), key="price", descending=True)
    assert [product.sku for product in ordered] == ["sku-2", "sku-1", "sku-3", "sku-5", "sku-4"]


def test_sort_by_rating() -> None:
    ordered = sort_products(catalogue(), key="rating", descending=True)
    assert [product.sku for product in ordered][0] == "sku-3"


def test_sort_rejects_unknown_keys() -> None:
    with pytest.raises(ValueError):
        sort_products(catalogue(), key="colour")


def test_paginate_slices_and_counts_pages() -> None:
    products = catalogue()
    first = paginate(products, page=1, per_page=2)
    assert [product.sku for product in first.items] == ["sku-3", "sku-1"]
    assert first.total_items == 5
    assert first.total_pages == 3
    assert first.has_next is True

    last = paginate(products, page=3, per_page=2)
    assert [product.sku for product in last.items] == ["sku-5"]
    assert last.has_next is False


def test_paginate_beyond_the_end_is_empty() -> None:
    page = paginate(catalogue(), page=9, per_page=2)
    assert page.items == ()
    assert page.total_items == 5


def test_paginate_validates_its_arguments() -> None:
    with pytest.raises(ValueError):
        paginate(catalogue(), page=0, per_page=2)
    with pytest.raises(ValueError):
        paginate(catalogue(), page=1, per_page=0)


def test_dedupe_key_ignores_case_and_spacing() -> None:
    first = Product("a", "Blue Mug", 1200)
    second = Product("b", " blue   mug", 1200)
    assert dedupe_key(first) == dedupe_key(second)


def test_find_duplicates_groups_and_sorts() -> None:
    groups = find_duplicates(
        [
            Product("sku-3", "Blue Mug", 1200),
            Product("sku-1", "blue  mug", 1200),
            Product("sku-2", "Red Kettle", 3500),
            Product("sku-5", "Green Tea", 900),
            Product("sku-4", "Green Tea", 900),
        ]
    )
    assert groups == [["sku-1", "sku-3"], ["sku-4", "sku-5"]]


def test_find_duplicates_returns_empty_for_unique_products() -> None:
    products = catalogue()
    unique = [products[1], products[2], products[3]]
    assert find_duplicates(unique) == []


def test_find_duplicates_accepts_a_custom_key() -> None:
    groups = find_duplicates(
        [
            Product("sku-1", "Mug", 1200),
            Product("sku-2", "Mug", 900),
            Product("sku-3", "Tea", 900),
        ],
        key=lambda product: product.price_cents,
    )
    assert groups == [["sku-2", "sku-3"]]


def test_product_validation() -> None:
    with pytest.raises(ValueError):
        Product("", "Mug", 100)
    with pytest.raises(ValueError):
        Product("a", "   ", 100)
    with pytest.raises(ValueError):
        Product("a", "Mug", -1)
    with pytest.raises(ValueError):
        Product("a", "Mug", 100, rating_bp=501)
