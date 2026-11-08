"""Product search: filtering, sorting, pagination and duplicate detection.

Everything here is pure: the functions take a sequence of products and return
new lists. Input order is preserved by :func:`filter_products`, and every sort
has a deterministic tie-break on sku so that equal prices never come back in an
order that depends on how the input happened to be built.
"""

from __future__ import annotations

from collections.abc import Callable, Hashable, Iterable, Sequence
from dataclasses import dataclass

__all__ = [
    "Page",
    "Product",
    "dedupe_key",
    "filter_products",
    "find_duplicates",
    "normalize_name",
    "paginate",
    "sort_products",
]


@dataclass(frozen=True)
class Product:
    """One catalogue entry. Prices are integer cents, ratings basis points."""

    sku: str
    name: str
    price_cents: int
    tags: tuple[str, ...] = ()
    rating_bp: int = 0

    def __post_init__(self) -> None:
        if not self.sku:
            raise ValueError("sku must not be empty")
        if not self.name.strip():
            raise ValueError("name must not be blank")
        if self.price_cents < 0:
            raise ValueError("price must not be negative")
        if not 0 <= self.rating_bp <= 500:
            raise ValueError("rating_bp must be between 0 and 500")
        object.__setattr__(self, "tags", tuple(tag.strip().casefold() for tag in self.tags))


def normalize_name(name: str) -> str:
    """Fold a product name for comparison.

    Case is folded, runs of whitespace collapse to one space and the ends are
    trimmed, so ``"  Café   Latte "`` and ``"café latte"`` compare equal.
    """
    return " ".join(name.casefold().split())


def dedupe_key(product: Product) -> tuple[str, int]:
    """The signature used to decide whether two products are duplicates."""
    return (normalize_name(product.name), product.price_cents)


def filter_products(
    products: Iterable[Product],
    *,
    query: str | None = None,
    tags: Sequence[str] | None = None,
    min_price_cents: int | None = None,
    max_price_cents: int | None = None,
) -> list[Product]:
    """Return the products that match every supplied filter, in input order.

    ``query`` is matched as a case-insensitive substring of the normalised
    name. ``tags`` must *all* be present (also case-insensitive). Price bounds
    are inclusive.
    """
    wanted_query = normalize_name(query) if query else ""
    wanted_tags = {tag.strip().casefold() for tag in tags or ()}
    result: list[Product] = []
    for product in products:
        if wanted_query and wanted_query not in normalize_name(product.name):
            continue
        if wanted_tags and not wanted_tags.issubset(set(product.tags)):
            continue
        if min_price_cents is not None and product.price_cents < min_price_cents:
            continue
        if max_price_cents is not None and product.price_cents > max_price_cents:
            continue
        result.append(product)
    return result


_PRIMARY_KEYS: dict[str, Callable[[Product], object]] = {
    "name": lambda product: normalize_name(product.name),
    "price": lambda product: product.price_cents,
    "rating": lambda product: product.rating_bp,
}


def sort_products(
    products: Iterable[Product], *, key: str = "name", descending: bool = False
) -> list[Product]:
    """Sort products by ``name``, ``price`` or ``rating``.

    ``descending`` reverses the primary key only. Ties are broken by sku in
    ascending order either way, so the result never depends on input order.
    """
    try:
        primary = _PRIMARY_KEYS[key]
    except KeyError:
        raise ValueError(f"unknown sort key: {key!r}") from None
    ordered = sorted(products, key=lambda product: product.sku)
    ordered.sort(key=primary, reverse=descending)
    return ordered


@dataclass(frozen=True)
class Page:
    """One page of results plus the numbers a pager widget needs."""

    items: tuple[Product, ...]
    page: int
    per_page: int
    total_items: int

    @property
    def total_pages(self) -> int:
        """Number of pages, at least 1 even for an empty result."""
        if self.per_page < 1:  # pragma: no cover - guarded by paginate
            return 0
        return max(1, -(-self.total_items // self.per_page))

    @property
    def has_next(self) -> bool:
        """True when there is a page after this one."""
        return self.page < self.total_pages


def paginate(products: Sequence[Product], *, page: int, per_page: int) -> Page:
    """Slice ``products`` into one page. ``page`` is 1-based, ``per_page`` >= 1."""
    if page < 1:
        raise ValueError("page must be at least 1")
    if per_page < 1:
        raise ValueError("per_page must be at least 1")
    start = (page - 1) * per_page
    return Page(
        items=tuple(products[start : start + per_page]),
        page=page,
        per_page=per_page,
        total_items=len(products),
    )


def find_duplicates(
    products: Iterable[Product],
    *,
    key: Callable[[Product], Hashable] = dedupe_key,
) -> list[list[str]]:
    """Group skus that share the same ``key``.

    Only groups of two or more are returned. Each group is sorted by sku, and
    groups appear in the order in which their first member appeared in the
    input. The ``key`` callable exists so callers can dedupe on a different
    rule (for example ignoring the price) without forking this function.
    """
    seen: dict[Hashable, list[str]] = {}
    order: list[Hashable] = []
    for product in products:
        signature = key(product)
        if signature in seen:
            seen[signature].append(product.sku)
            continue
        seen[signature] = [product.sku]
        order.append(signature)
    return [sorted(seen[signature]) for signature in order if len(seen[signature]) > 1]
