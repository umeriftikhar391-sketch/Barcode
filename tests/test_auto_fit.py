import pytest
from barcode import Code128
from PIL import ImageDraw
from backend.models import Product, Geometry, Queue
from backend.render import label, render_label, raster_row, tspl


def profile():
    return Geometry(width=33, height=24, safe=2)


def product(code, **kw):
    return Product(
        **(
            {
                "name": "Stole",
                "barcode": code,
                "price": "22",
                "symbol": "$",
                "quantity": 1,
            }
            | kw
        )
    )


@pytest.mark.parametrize(
    "code,module",
    [("1", 2), ("000001", 2), ("0001234567", 2), ("1000459-1", 1), ("1000459-10", 1)],
)
def test_auto_uses_widest_whole_dot_bars_that_fit(code, module):
    g = profile()
    assert g.barcode_module == 0
    im, warnings, exception = render_label(product(code), g)
    assert not warnings and not exception
    bits = Code128(code).build()[0]
    expected = "".join(bit * module for bit in bits)
    start = (im.width - (len(bits) + 20) * module) // 2 + 10 * module
    y = g.dots(g.safe) + 52
    actual = "".join("1" if im.getpixel((x, y)) == 0 else "0" for x in range(im.width))
    assert actual == "0" * start + expected + "0" * (im.width - start - len(expected))


@pytest.mark.parametrize("code", ["ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", "W" * 128])
def test_impossible_code_gets_marked_exception_with_full_value(code, monkeypatch):
    texts = []
    draw_text = ImageDraw.ImageDraw.text

    def capture(self, xy, text, *args, **kw):
        texts.append(text)
        return draw_text(self, xy, text, *args, **kw)

    monkeypatch.setattr(ImageDraw.ImageDraw, "text", capture)
    p = product(code)
    im, warnings, exception = render_label(p, profile())
    assert exception and "no scannable barcode" in warnings[0]
    assert "CHECK LABEL - NO BARCODE" in texts
    assert code in "".join(texts)
    assert im.size == (264, 192)
    assert p.barcode == code


def test_long_name_shortens_display_while_preserving_barcode_and_source():
    p = product("1000459-10", name="Very long product name " * 12)
    im, warnings, exception = render_label(p, profile())
    assert not exception
    assert "name shortened" in warnings[0]
    assert p.name == "Very long product name " * 12
    reference = label(product(p.barcode), profile())
    y = profile().dots(2) + 52
    assert (
        im.crop((0, y, im.width, y + 48)).tobytes()
        == reference.crop((0, y, im.width, y + 48)).tobytes()
    )


def test_mixed_job_keeps_all_requested_slots_and_rows():
    g = profile()
    normal, impossible = product("000001"), product("W" * 128, quantity=3)
    q = Queue(products=[normal, impossible], geometry=g)
    from backend.layout import rows

    rr = rows(q.products)
    assert len(rr) == 2 and sum(p is not None for row in rr for p in row) == 4
    for row in rr:
        raster_row(row, g, strict=True)
    commands = tspl(q)
    assert commands.count(b"PRINT 1,1\r\n") == 2


def test_upgrade_activates_auto_once_preserving_media_and_products(
    tmp_path, monkeypatch
):
    from backend import app

    monkeypatch.setattr(app, "STATE", tmp_path)
    q = Queue(products=[product("1000459-10")], geometry=profile())
    q.geometry.barcode_module = 2
    app.put_setting("queue", q.model_dump(mode="json"))
    upgraded = app.load_queue()
    assert upgraded["geometry"]["barcode_module"] == 0
    assert upgraded["products"] == q.model_dump(mode="json")["products"]
    assert upgraded["geometry"]["safe"] == 2
    # A later explicit manual selection remains respected.
    app.save_queue(q)
    assert app.load_queue()["geometry"]["barcode_module"] == 2
