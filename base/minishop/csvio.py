"""Importing orders from CSV text.

The format is deliberately boring: a header row, then one row per line item.

.. code-block:: csv

    order_id,sku,quantity,unit_price
    A-1001,sku-1,2,12.50
    A-1001,sku-2,1,3.00

Rules:

* the header names are matched case-insensitively and may appear in any order,
  but every name in ``REQUIRED_COLUMNS`` must be there and nothing else may be;
* blank rows are skipped, and a UTF-8 byte-order mark is ignored;
* ``quantity`` is a positive integer and ``unit_price`` is money in the format
  :func:`minishop.pricing.parse_cents` accepts;
* two rows with the same ``order_id`` and ``sku`` are merged by adding their
  quantities, provided the unit price agrees. Disagreeing prices are an error
  rather than a guess.

Every error is a :class:`CsvError` that names the physical line it came from.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from .pricing import parse_cents

__all__ = ["CsvError", "ImportedOrderLine", "REQUIRED_COLUMNS", "parse_orders"]

REQUIRED_COLUMNS = ("order_id", "sku", "quantity", "unit_price")


class CsvError(ValueError):
    """A malformed CSV import, with the line number that caused it."""

    def __init__(self, message: str, line_number: int) -> None:
        super().__init__(f"line {line_number}: {message}")
        self.line_number = line_number


@dataclass(frozen=True)
class ImportedOrderLine:
    """One validated line item from the CSV file."""

    order_id: str
    sku: str
    quantity: int
    unit_cents: int

    @property
    def total_cents(self) -> int:
        """``quantity * unit_cents``."""
        return self.quantity * self.unit_cents


def _parse_header(row: list[str], line_number: int) -> dict[str, int]:
    names = [cell.strip().casefold() for cell in row]
    if len(names) != len(set(names)):
        raise CsvError("duplicate column in header", line_number)
    missing = [column for column in REQUIRED_COLUMNS if column not in names]
    if missing:
        raise CsvError(f"missing column(s): {', '.join(missing)}", line_number)
    unknown = [name for name in names if name not in REQUIRED_COLUMNS]
    if unknown:
        raise CsvError(f"unknown column(s): {', '.join(unknown)}", line_number)
    return {name: index for index, name in enumerate(names)}


def parse_orders(text: str) -> list[ImportedOrderLine]:
    """Parse CSV text into validated order lines, in file order.

    Duplicate (order, sku) rows are merged, and the merged line keeps the
    position of its first occurrence.
    """
    if text.startswith("\ufeff"):
        text = text[1:]
    reader = csv.reader(io.StringIO(text, newline=""))
    header: dict[str, int] | None = None
    merged: dict[tuple[str, str], ImportedOrderLine] = {}
    order: list[tuple[str, str]] = []

    for row in reader:
        line_number = reader.line_num
        if not row or all(not cell.strip() for cell in row):
            continue
        if header is None:
            header = _parse_header(row, line_number)
            continue
        if len(row) != len(REQUIRED_COLUMNS):
            raise CsvError(f"expected {len(REQUIRED_COLUMNS)} cells, found {len(row)}", line_number)
        raw = {name: row[index].strip() for name, index in header.items()}
        order_id, sku = raw["order_id"], raw["sku"]
        if not order_id:
            raise CsvError("order_id must not be empty", line_number)
        if not sku:
            raise CsvError("sku must not be empty", line_number)
        try:
            quantity = int(raw["quantity"])
        except ValueError:
            raise CsvError(f"quantity is not an integer: {raw['quantity']!r}", line_number) from None
        if quantity < 1:
            raise CsvError("quantity must be at least 1", line_number)
        try:
            unit_cents = parse_cents(raw["unit_price"])
        except ValueError as exc:
            raise CsvError(str(exc), line_number) from None
        key = (order_id, sku)
        if key in merged:
            previous = merged[key]
            if previous.unit_cents != unit_cents:
                raise CsvError(
                    f"{sku!r} appears twice in {order_id!r} with different unit prices",
                    line_number,
                )
            merged[key] = ImportedOrderLine(
                order_id=order_id,
                sku=sku,
                quantity=previous.quantity + quantity,
                unit_cents=unit_cents,
            )
            continue
        merged[key] = ImportedOrderLine(
            order_id=order_id, sku=sku, quantity=quantity, unit_cents=unit_cents
        )
        order.append(key)

    if header is None:
        raise CsvError("missing header row", 1)
    return [merged[key] for key in order]
