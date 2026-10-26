from decimal import Decimal
from io import BytesIO
import pytest
from PIL import Image
from pydantic import ValidationError
from backend.models import Product, Queue, Geometry
from backend.layout import rows
from backend.render import label, raster_row, tspl
from backend.importer import inspect_file, propose, convert, parse_price
from openpyxl import Workbook


def product(**kw):
    return Product(
        **(
            {
                "name": "Coaster",
                "barcode": "1000111",
                "price": "1200",
                "symbol": "Rs.",
                "quantity": 1,
            }
            | kw
        )
    )


def valid():
    return Geometry(width=33, backing=107, left=2, right=2, gap_x=2)


@pytest.mark.parametrize("n", [1, 2, 3, 4, 5, 6, 7, 8, 10, 25, 50, 100])
def test_quantities(n):
    p = product(quantity=n)
    rr = rows([p])
    assert len(rr) == (n + 2) // 3
    assert sum(x is not None for r in rr for x in r) == n
    assert all(x is p for r in rr for x in r if x)
    assert rows([product()])[0][1:] == [None, None]
    assert len(rr[-1]) == 3


@pytest.mark.parametrize("counts", [(1, 2), (2, 4), (1, 2, 4)])
def test_mixed(counts):
    ps = [product(name=chr(65 + i), quantity=q) for i, q in enumerate(counts)]
    assert [p.name for r in rows(ps) for p in r if p] == [
        p.name for p in ps for _ in range(p.quantity)
    ]


def test_empty():
    assert rows([]) == []


@pytest.mark.parametrize(
    "code", ["1000111", "1000111-1", "AMZ-1012", "1000000223", "0001234567"]
)
def test_barcodes(code):
    p = product(barcode=code)
    assert p.barcode == code
    assert label(p, Geometry()).convert("L").getextrema() == (0, 255)


def test_long_barcode_cannot_shrink():
    with pytest.raises(ValueError, match="needs"):
        label(product(barcode="ABCD-1234-AC2026"), Geometry())


@pytest.mark.parametrize("value", [123, "中文", "a\nb", ""])
def test_invalid_barcodes(value):
    with pytest.raises(ValidationError):
        product(barcode=value)


@pytest.mark.parametrize("q", [0, -1, 1.5, "1", True])
def test_bad_quantities(q):
    with pytest.raises(ValidationError):
        product(quantity=q)


def test_geometry():
    assert "113" in Geometry().errors()[0]
    assert valid().errors() == []
    assert Geometry(offset_x=-10).errors()
    assert Geometry(top=20, safe=3).errors()
    assert valid().dots(25.4) == 203
    with pytest.raises(ValueError):
        tspl(Queue(products=[product()]))


def test_raster_and_commands():
    q = Queue(products=[product(quantity=4)], geometry=valid())
    rr = rows(q.products)
    image = raster_row(rr[1], q.geometry, True)
    start = q.geometry.dots(q.geometry.left + q.geometry.width + q.geometry.gap_x)
    assert image.crop((start, 0, image.width, image.height)).convert(
        "L"
    ).getextrema() == (255, 255)
    cmd = tspl(q)
    assert cmd.count(b"PRINT 1,1\r\n") == 2
    assert cmd.count(b"CLS\r\n") == 2
    assert b"GAP 2 mm" in cmd


def test_currency_only():
    p = product(price="1200.50")
    other = p.model_copy(update={"symbol": "€"})
    assert p.price == other.price == Decimal("1200.50")
    label(other, Geometry())
    with pytest.raises(ValueError, match="glyphs"):
        label(product(symbol="𐀀"), Geometry())


def convert_table(table, **kw):
    proposal = propose(table)
    args = dict(
        table=table,
        header=proposal["header"],
        mapping=proposal["mapping"],
        quantity_mode="fixed",
        default_quantity=2,
        confirmed=True,
        numeric_confirmed=False,
        decimal_separator=".",
    )
    return convert(**(args | kw))


def test_supplied_workbook():
    from pathlib import Path

    file = Path(__file__).parent / "fixtures" / "odoo.xlsx"
    data = inspect_file(file.read_bytes(), "odoo.xlsx")
    table = data["sheets"]["Sheet1"]
    assert propose(table)["confirmation_required"]
    r = convert_table(table)
    assert len(r["products"]) == 1 and len(r["errors"]) == 1
    assert r["products"][0].quantity == 2  # stock 636 is deliberately ignored
    assert r["products"][0].price == 0
    r = convert_table(table, numeric_confirmed=True)
    assert len(r["products"]) == 2
    assert r["products"][1].barcode == "1000037"


def test_mapping_and_prices():
    data = b"Note\nProduct,Barcode,Quantity,Sales Price,Currency\nCoaster,0001234567,5,1200,Rs.\n"
    t = inspect_file(data, "p.csv")["sheets"]["CSV"]
    assert propose(t)["header"] == 1
    r = convert_table(t, quantity_mode="column")
    assert r["products"][0].barcode == "0001234567"
    assert r["products"][0].quantity == 5
    with pytest.raises(ValueError):
        convert_table(t, confirmed=False)
    assert parse_price("Rs. 1,200.50")[0] == Decimal("1200.50")
    assert parse_price("1.200,50", ",")[0] == Decimal("1200.50")
    for value in ["", None, "1,20", "NaN", "1e3", "-3"]:
        with pytest.raises(ValueError):
            parse_price(value)


def test_excel_formula():
    w = Workbook()
    w.active.append(["Product", "Barcode", "Price", "Currency"])
    w.active.append(["A", "=1+1", 5, "$"])
    w.create_sheet("Other").append(["Product"])
    b = BytesIO()
    w.save(b)
    r = inspect_file(b.getvalue(), "p.xlsx")
    assert set(r["sheets"]) == {"Sheet", "Other"}
    assert r["warnings"]
    assert convert_table(r["sheets"]["Sheet"])["errors"]


@pytest.mark.parametrize(
    "name,data", [("x.exe", b"x"), ("x.xlsx", b"bad"), ("x.csv", b"\xff")]
)
def test_malformed_files(name, data):
    with pytest.raises(Exception):
        inspect_file(data, name)


def test_legacy_xls():
    from pathlib import Path

    d = inspect_file(
        (Path(__file__).parent / "fixtures/products.xls").read_bytes(), "products.xls"
    )
    r = convert_table(d["sheets"]["Products"], quantity_mode="column")
    assert not r["errors"]
    assert r["products"][0].barcode == "0001234567"
    assert r["products"][0].quantity == 2
