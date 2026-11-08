"""Visible tests for minishop.csvio."""

from __future__ import annotations

import pytest

from minishop.csvio import CsvError, parse_orders

HEADER = "order_id,sku,quantity,unit_price\n"


def test_parse_two_lines() -> None:
    text = HEADER + "A-1,sku-1,2,12.50\nA-1,sku-2,1,3.00\n"
    lines = parse_orders(text)
    assert [(line.order_id, line.sku, line.quantity) for line in lines] == [
        ("A-1", "sku-1", 2),
        ("A-1", "sku-2", 1),
    ]
    assert lines[0].unit_cents == 1250
    assert lines[0].total_cents == 2500


def test_header_is_case_insensitive_and_may_be_reordered() -> None:
    text = "SKU,Order_ID,Unit_Price,Quantity\nsku-9,A-9,1.00,4\n"
    lines = parse_orders(text)
    assert lines[0].sku == "sku-9"
    assert lines[0].order_id == "A-9"
    assert lines[0].quantity == 4


def test_blank_lines_and_whitespace_are_tolerated() -> None:
    text = HEADER + "\n  \nA-2,sku-1,1,0.99\n"
    assert len(parse_orders(text)) == 1


def test_quoted_fields_with_commas_are_kept_whole() -> None:
    text = HEADER + '"A,3",sku-1,1,1.00\n'
    assert parse_orders(text)[0].order_id == "A,3"


def test_duplicate_rows_merge_quantities() -> None:
    text = HEADER + "A-4,sku-1,2,1.00\nA-4,sku-1,3,1.00\n"
    lines = parse_orders(text)
    assert len(lines) == 1
    assert lines[0].quantity == 5


def test_duplicate_rows_with_different_prices_are_an_error() -> None:
    text = HEADER + "A-5,sku-1,2,1.00\nA-5,sku-1,3,1.50\n"
    with pytest.raises(CsvError) as excinfo:
        parse_orders(text)
    assert excinfo.value.line_number == 3


def test_missing_column_is_an_error() -> None:
    with pytest.raises(CsvError, match="missing column"):
        parse_orders("order_id,sku,quantity\nA-1,sku-1,1\n")


def test_unknown_column_is_an_error() -> None:
    with pytest.raises(CsvError, match="unknown column"):
        parse_orders("order_id,sku,quantity,unit_price,colour\nA-1,sku-1,1,1.00,red\n")


def test_bad_quantity_names_the_line() -> None:
    text = HEADER + "A-6,sku-1,1,1.00\nA-6,sku-2,two,1.00\n"
    with pytest.raises(CsvError) as excinfo:
        parse_orders(text)
    assert excinfo.value.line_number == 3
    assert "quantity" in str(excinfo.value)


def test_non_positive_quantity_is_an_error() -> None:
    with pytest.raises(CsvError, match="at least 1"):
        parse_orders(HEADER + "A-7,sku-1,0,1.00\n")


def test_bad_price_is_an_error() -> None:
    with pytest.raises(CsvError) as excinfo:
        parse_orders(HEADER + "A-8,sku-1,1,1.234\n")
    assert excinfo.value.line_number == 2


def test_empty_order_id_and_sku_are_errors() -> None:
    with pytest.raises(CsvError, match="order_id"):
        parse_orders(HEADER + ",sku-1,1,1.00\n")
    with pytest.raises(CsvError, match="sku"):
        parse_orders(HEADER + "A-9,,1,1.00\n")


def test_byte_order_mark_is_ignored() -> None:
    text = "\ufeff" + HEADER + "A-10,sku-1,1,1.00\n"
    assert parse_orders(text)[0].order_id == "A-10"


def test_header_only_file_returns_no_lines() -> None:
    assert parse_orders(HEADER) == []


def test_empty_text_is_an_error() -> None:
    with pytest.raises(CsvError, match="header"):
        parse_orders("")
