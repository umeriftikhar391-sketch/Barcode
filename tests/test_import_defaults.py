from io import BytesIO
from openpyxl import Workbook
import pytest
from backend.importer import propose, convert, inspect_file


def conversion(table):
    p = propose(table)
    return convert(
        table=table,
        header=p["header"],
        mapping=p["mapping"],
        quantity_mode=p["quantity_mode"],
        default_quantity=p["default_quantity"],
        confirmed=True,
        numeric_confirmed=True,
        decimal_separator=".",
    )


@pytest.mark.parametrize(
    "header", ["Print Qty", "Print Quantity", "Label Qty", "Labels", "Copies"]
)
def test_explicit_print_count_is_used_automatically(header):
    table = [
        ["Product", "Barcode", "Quantity", header, "Sales Price", "Currency"],
        ["Coaster", "000123", 636, 3, 22, "$"],
    ]
    p = propose(table)
    assert p["quantity_mode"] == "column" and p["mapping"]["quantity"] == 3
    r = conversion(table)
    assert not r["errors"]
    assert r["products"][0].quantity == 3
    assert r["products"][0].barcode == "000123"


@pytest.mark.parametrize("header", ["Quantity", "Qty", "On Hand", "Available", "Stock"])
def test_ambiguous_or_stock_counts_default_to_one_label(header):
    table = [
        ["Product", "Barcode", header, "Price", "Currency"],
        ["Coaster", 1000037, 636, 22, "$"],
    ]
    assert propose(table)["quantity_mode"] == "fixed"
    r = conversion(table)
    assert not r["errors"]
    assert r["products"][0].quantity == 1


def test_numeric_prices_and_quantities_do_not_create_barcode_warnings():
    w = Workbook()
    w.active.append(["Product", "Barcode", "Print Qty", "Price", "Currency"])
    w.active.append(["Text code", "000123", 3, 22, "$"])
    w.active.append(["Numeric code", 1000037, 2, 25, "$"])
    out = BytesIO()
    w.save(out)
    data = inspect_file(out.getvalue(), "products.xlsx")
    assert len(data["warnings"]) == 1
    assert "row 3" in data["warnings"][0]
    r = conversion(data["sheets"]["Sheet"])
    assert not r["errors"] and [p.quantity for p in r["products"]] == [3, 2]


def test_each_sheet_gets_its_own_quantity_default():
    assert propose([["Product", "Barcode", "Print Qty"]])["quantity_mode"] == "column"
    other = [
        ["Product", "Barcode", "Price", "Currency"],
        ["Coaster", "000123", 22, "$"],
    ]
    assert propose(other)["quantity_mode"] == "fixed"
    assert conversion(other)["products"][0].quantity == 1
