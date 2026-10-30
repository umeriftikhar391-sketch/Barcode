import hashlib
import pytest
from barcode import Code128
from pydantic import ValidationError
from backend.models import Geometry, Product, Queue
from backend.render import label, raster_row
from backend.app import fingerprint, calibration_sample, CalibrationSample


def profile(**kwargs):
    return Geometry(
        **({"width": 33, "height": 24, "safe": 2, "barcode_module": 2} | kwargs)
    )


def product(code):
    return Product(name="Stole", barcode=code, price="22", symbol="$", quantity=1)


@pytest.mark.parametrize("value", [-1, 3, 1.5, True, "1"])
def test_whole_supported_dot_widths_only(value):
    with pytest.raises(ValidationError):
        profile(barcode_module=value)


@pytest.mark.parametrize("code", ["1000459-1", "1000704-2", "1000459-10", "0001234567"])
def test_narrow_bars_are_exact_code128_with_quiet_zones(code):
    g = profile(barcode_module=1)
    tile = label(product(code), g)
    bits = Code128(code).build()[0]
    start = (tile.width - len(bits) - 20) // 2 + 10
    y = g.dots(g.safe) + 52
    actual = "".join(
        "1" if tile.getpixel((x, y)) == 0 else "0" for x in range(tile.width)
    )
    assert actual == "0" * start + bits + "0" * (tile.width - start - len(bits))
    assert start - g.dots(g.safe) >= 10
    assert tile.width - g.dots(g.safe) - start - len(bits) >= 10
    q = Queue(products=[product(code).model_copy(update={"quantity": 3})], geometry=g)
    raster_row(q.products, g, strict=True)


def test_no_implicit_narrowing_or_changed_value():
    p = product("1000459-10")
    with pytest.raises(ValueError, match="select Automatic fit"):
        label(p, profile())
    with pytest.raises(ValueError, match="Even narrow bars do not fit"):
        label(
            product("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"), profile(barcode_module=1)
        )
    assert p.barcode == "1000459-10"


def test_narrow_profile_needs_its_own_calibration():
    g = profile()
    legacy = hashlib.sha256(
        (g.model_dump_json(exclude={"barcode_module"}) + "TSC" + "driver").encode()
    ).hexdigest()
    assert fingerprint(g, "TSC", "driver") == legacy
    assert fingerprint(profile(barcode_module=1), "TSC", "driver") != legacy


@pytest.mark.parametrize("module", [0, 1, 2])
def test_calibration_uses_long_barcodes_for_narrow_mode(monkeypatch, module):
    captured = []
    monkeypatch.setattr(
        "backend.app.dispatch", lambda request: captured.append(request)
    )
    calibration_sample(
        CalibrationSample(
            geometry=profile(barcode_module=module),
            printer="TSC",
            id="narrow-sample",
            approved=True,
        )
    )
    products = captured[0].queue.products
    assert len(products) == 7
    assert [p.barcode for p in products[:3]] == (
        ["1000459-10"] * 3 if module != 2 else ["000001", "000002", "000003"]
    )
