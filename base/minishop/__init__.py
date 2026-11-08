"""minishop: a small, correct shop backend library.

The package is split by concern so that each module can be read on its own:

* :mod:`minishop.pricing` - carts, discounts, tax, totals (integer cents only)
* :mod:`minishop.inventory` - stock levels and reservations
* :mod:`minishop.cache` - a TTL + LRU cache driven by an injected clock
* :mod:`minishop.search` - filtering, sorting, pagination, duplicate detection
* :mod:`minishop.files` - serving downloads from one public directory
* :mod:`minishop.csvio` - importing orders from CSV text
"""

from __future__ import annotations

from .cache import CacheStats, TtlLruCache
from .csvio import CsvError, ImportedOrderLine, parse_orders
from .files import MissingPublicFile, PublicFileError, PublicFiles, UnsafePath
from .inventory import (
    Inventory,
    InventoryError,
    OutOfStock,
    Reservation,
    ReservationError,
    UnknownSku,
)
from .pricing import (
    Cart,
    FixedOff,
    LineItem,
    PercentOff,
    Quote,
    QuoteLine,
    format_cents,
    parse_cents,
    quote_cart,
    round_half_up,
)
from .search import (
    Page,
    Product,
    dedupe_key,
    filter_products,
    find_duplicates,
    normalize_name,
    paginate,
    sort_products,
)

__all__ = [
    "CacheStats",
    "Cart",
    "CsvError",
    "FixedOff",
    "ImportedOrderLine",
    "Inventory",
    "InventoryError",
    "LineItem",
    "MissingPublicFile",
    "OutOfStock",
    "Page",
    "PercentOff",
    "Product",
    "PublicFileError",
    "PublicFiles",
    "Quote",
    "QuoteLine",
    "Reservation",
    "ReservationError",
    "TtlLruCache",
    "UnknownSku",
    "UnsafePath",
    "dedupe_key",
    "filter_products",
    "find_duplicates",
    "format_cents",
    "normalize_name",
    "paginate",
    "parse_cents",
    "parse_orders",
    "quote_cart",
    "round_half_up",
    "sort_products",
]
