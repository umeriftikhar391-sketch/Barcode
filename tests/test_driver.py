import pytest
from PIL import Image
from backend.models import Geometry
from backend.printers import driver_preflight, PrinterPreflightError


def profile():
    g = Geometry(width=33, height=24, safe=2)
    im = Image.new("1", (g.dots(107), g.dots(24)), 1)
    caps = dict(
        dpi_x=203,
        dpi_y=203,
        page_width=im.width,
        page_height=im.height,
        offset_x=0,
        offset_y=0,
    )
    driver_preflight(g, caps, [im])
    return g, im, caps


def test_exact_row_profile():
    profile()


def test_rounded_inches_and_double_margins_report_both():
    g, im, caps = profile()
    caps.update(page_height=191, offset_x=16)
    with pytest.raises(PrinterPreflightError) as caught:
        driver_preflight(g, caps, [im])
    text = str(caught.value)
    assert "855 x 191" in text
    assert "855 x 192" in text
    assert "height 24 mm" in text
    assert "Exposed Liner Widths Left/Right to 0" in text


def test_dpi_is_not_silently_scaled():
    g, im, caps = profile()
    caps.update(dpi_x=200, dpi_y=200)
    with pytest.raises(PrinterPreflightError, match="200 x 200 DPI"):
        driver_preflight(g, caps, [im])
