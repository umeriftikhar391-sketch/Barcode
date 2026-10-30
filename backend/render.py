"""Single monochrome raster source for preview, GDI and TSPL bitmap output."""

from pathlib import Path
from functools import lru_cache
import os
from barcode import Code128
from PIL import Image, ImageDraw, ImageFont, ImageChops, features
from fontTools.ttLib import TTFont
from .layout import rows


@lru_cache
def font_path():
    candidates = [
        os.environ.get("LABEL_FONT", ""),
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for p in candidates:
        if p and Path(p).is_file():
            return p
    raise ValueError("Install a Unicode TrueType font and set LABEL_FONT to its path")


@lru_cache
def glyphs():
    with TTFont(font_path()) as f:
        return set(f.getBestCmap())


def text_fit(draw, text, box, min_size=12, max_size=20, lines=1, bold=False):
    if any(ord(c) not in glyphs() for c in text):
        raise ValueError(f"Font lacks glyphs for: {text}")
    if any("\u0600" <= c <= "\u06ff" for c in text) and not features.check_feature(
        "raqm"
    ):
        raise ValueError(
            "Arabic shaping requires Pillow with libraqm; choose a supported symbol"
        )
    x, y, w, h = box
    for size in range(max_size, min_size - 1, -1):
        path = font_path()
        bold_path = path.replace("DejaVuSans.ttf", "DejaVuSans-Bold.ttf").replace(
            "arial.ttf", "arialbd.ttf"
        )
        font = ImageFont.truetype(
            bold_path if bold and Path(bold_path).exists() else path, size
        )
        words = text.split(" ")
        parts = [""]
        for word in words:
            trial = (parts[-1] + " " + word).strip()
            if draw.textlength(trial, font=font) > w and parts[-1]:
                parts.append(word)
            else:
                parts[-1] = trial
        line_h = size + 3
        if (
            len(parts) <= lines
            and len(parts) * line_h <= h
            and all(draw.textlength(t, font=font) <= w for t in parts)
        ):
            for i, t in enumerate(parts):
                draw.text(
                    (x + w / 2, y + i * line_h), t, fill=0, font=font, anchor="mt"
                )
            return
    raise ValueError(f"Text cannot fit without truncation: {text}")


def label(product, g, warnings=None):
    w, h = g.dots(g.width), g.dots(g.height)
    s = g.dots(g.safe)
    im = Image.new("1", (w, h), 1)
    d = ImageDraw.Draw(im)
    try:
        text_fit(d, product.name, (s, s, w - 2 * s, 48), 12, 20, 2, True)
    except ValueError as exc:
        if g.barcode_module != 0 or not str(exc).startswith("Text cannot fit"):
            raise
        # Only the display name may be shortened; barcode and price stay exact.
        trial = ImageDraw.Draw(Image.new("1", (w, h), 1))
        lo, hi, best = 0, len(product.name) - 1, None
        while lo <= hi:
            end = (lo + hi) // 2
            candidate = product.name[:end].rstrip() + "..."
            try:
                text_fit(
                    trial,
                    candidate,
                    (s, s, w - 2 * s, 48),
                    12,
                    20,
                    2,
                    True,
                )
                best, lo = candidate, end + 1
            except ValueError:
                hi = end - 1
        if best is None:
            raise ValueError("No room for a product name")
        text_fit(d, best, (s, s, w - 2 * s, 48), 12, 20, 2, True)
        if warnings is not None:
            warnings.append(
                "Printed product name shortened; full name remains in the queue."
            )
    bits = Code128(product.barcode).build()[0]
    # Automatic fitting selects between standard and narrow bars per value.
    # Draw whole printer dots; never resample bars or crop the ten-module quiet zones.
    module = g.barcode_module
    if module == 0:
        module = 2 if (len(bits) + 20) * 2 <= w - 2 * s else 1
    bw = (len(bits) + 20) * module
    if bw > w - 2 * s:
        raise ValueError(
            f"Barcode {product.barcode} needs {bw} dots including quiet zones; only {w - 2 * s} available. "
            + (
                "For this roll, select Automatic fit or Narrow bars in Printer settings."
                if module == 2
                else "Even narrow bars do not fit; use wider labels or a suitable higher-resolution printer."
            )
        )
    x = (w - bw) // 2 + 10 * module
    y = s + 52
    bh = g.dots(6)
    if y + bh + 51 > h - s:
        raise ValueError("Label too short for readable content")
    for i, b in enumerate(bits):
        if b == "1":
            d.rectangle(
                (x + i * module, y, x + (i + 1) * module - 1, y + bh - 1), fill=0
            )
    text_fit(d, product.barcode, (s, y + bh + 3, w - 2 * s, 22), 12, 16)
    text_fit(
        d,
        f"{product.symbol} {product.price:,.{max(0, -product.price.as_tuple().exponent)}f}",
        (s, h - s - 25, w - 2 * s, 25),
        12,
        20,
        1,
        True,
    )
    bounds = ImageChops.invert(im.convert("L")).getbbox()
    if bounds and (
        bounds[0] < s or bounds[1] < s or bounds[2] > w - s or bounds[3] > h - s
    ):
        raise ValueError(
            "Rendered glyphs exceed label safe margins; select another font or label size"
        )
    return im


def exception_label(product, g):
    """A counted, visibly marked exception, never a fabricated barcode."""
    w, h, s = g.dots(g.width), g.dots(g.height), g.dots(g.safe)
    im = Image.new("1", (w, h), 1)
    d = ImageDraw.Draw(im)
    font = ImageFont.truetype(font_path(), 10)
    # Printable ASCII barcode values are schema-validated and at most 128 chars.
    lines, current = [], ""
    for char in product.barcode:
        if current and d.textlength(current + char, font=font) > w - 2 * s:
            lines.append(current)
            current = ""
        current += char
    lines.append(current)
    needed = 34 + len(lines) * 13
    if needed > h - 2 * s:
        raise ValueError("Label too small even for a readable exception value")
    d.text((s, s), "CHECK LABEL - NO BARCODE", font=font, fill=0)
    for i, line in enumerate(lines):
        d.text((s, s + 17 + i * 13), line, font=font, fill=0)
    price = f"{product.symbol} {product.price:f}"
    text_fit(d, price, (s, h - s - 17, w - 2 * s, 17), 8, 12)
    return im


def render_label(product, g):
    warnings = []
    try:
        return label(product, g, warnings), warnings, False
    except ValueError as exc:
        if g.barcode_module != 0:
            raise
        return (
            exception_label(product, g),
            [f"Exception label: no scannable barcode. {exc}"],
            True,
        )


def raster_row(row, g, strict=False):
    if strict and g.errors():
        raise ValueError("; ".join(g.errors()))
    extent = max(
        g.backing, g.left + 3 * g.width + 2 * g.gap_x + g.right + max(0, g.offset_x)
    )
    # Invalid geometry is shown at its stated extent, never silently compressed.
    im = Image.new("1", (g.dots(extent), g.dots(g.height)), 1)
    for col, p in enumerate(row):
        if p:
            tile = render_label(p, g)[0]
            x = g.dots(g.left + col * (g.width + g.gap_x) + g.offset_x)
            y = g.dots(g.top)
            if y + tile.height > im.height:
                # The white bottom margin may be cropped, never printed content.
                if (
                    tile.crop((0, im.height - y, tile.width, tile.height)).getextrema()[
                        0
                    ]
                    == 0
                ):
                    raise ValueError("Vertical offset clips label content")
            if strict:
                bounds = ImageChops.invert(tile.convert("L")).getbbox()
                if bounds and (
                    x + bounds[0] < g.dots(g.origin)
                    or x + bounds[2] > g.dots(g.origin + g.printable)
                    or y + bounds[3] > im.height
                ):
                    raise ValueError("Raster content exceeds printable dot boundaries")
            im.paste(tile, (x, y))
    return im


def tspl(queue):
    g = queue.geometry
    if g.errors():
        raise ValueError("; ".join(g.errors()))
    output = f"SIZE {g.backing:g} mm,{g.height:g} mm\r\nGAP {g.gap_y:g} mm,0 mm\r\nDIRECTION 1\r\nREFERENCE 0,0\r\nSPEED {g.speed}\r\nDENSITY {g.density}\r\n".encode(
        "ascii"
    )
    for row in rows(queue.products):
        im = raster_row(row, g, True)
        # Convert backing coordinates to printer-origin coordinates, retaining only
        # the validated printable content. Bit 1 is black in TSPL BITMAP.
        cropped = Image.new("1", ((g.dots(g.printable) // 8) * 8, im.height), 1)
        bounds = ImageChops.invert(im.convert("L")).getbbox()
        if bounds and bounds[2] - g.dots(g.origin) > cropped.width:
            raise ValueError(
                "Content exceeds byte-aligned TSPL printable width; increase safe margin"
            )
        cropped.paste(im, (-g.dots(g.origin), 0))
        padded = Image.new("1", (((cropped.width + 7) // 8) * 8, cropped.height), 1)
        padded.paste(cropped, (0, 0))
        data = bytes(b ^ 255 for b in padded.tobytes())
        output += (
            f"CLS\r\nBITMAP 0,0,{padded.width // 8},{padded.height},0,".encode()
            + data
            + b"\r\nPRINT 1,1\r\n"
        )
    return output
