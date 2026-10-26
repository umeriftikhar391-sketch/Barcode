import csv, io, re, zipfile
from decimal import Decimal, InvalidOperation
from openpyxl import load_workbook
import xlrd
from .models import Product

ALIASES = {
    "barcode": [
        "barcode",
        "barcodenumber",
        "barcodevalue",
        "productcode",
        "sku",
        "itemcode",
    ],
    "name": ["product", "productname", "itemname", "description", "title"],
    "quantity": ["qty", "quantity", "copies", "labels", "printqty", "printquantity"],
    "price": ["price", "salesprice", "sellingprice", "rate", "retailprice"],
    "symbol": ["currency", "currencysymbol", "symbol", "curr"],
}


def norm(v):
    return re.sub(r"[^a-z0-9]", "", str(v).lower())


def inspect_file(data, filename):
    if len(data) > 8 * 1024 * 1024:
        raise ValueError("File limit is 8 MiB")
    ext = filename.lower().rsplit(".", 1)[-1]
    sheets = {}
    warnings = []
    if ext == "csv":
        text = data.decode("utf-8-sig")
        dialect = None
        lines = text.splitlines()
        for skip in range(min(20, len(lines))):
            try:
                dialect = csv.Sniffer().sniff(
                    "\n".join(lines[skip:])[:8192], delimiters=",;\t"
                )
                break
            except csv.Error:
                pass
        sheets["CSV"] = list(csv.reader(io.StringIO(text), dialect or csv.excel))
    elif ext == "xlsx":
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            if sum(f.file_size for f in z.infolist()) > 40 * 1024 * 1024:
                raise ValueError("Expanded workbook exceeds 40 MiB")
        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=False)
        for s in wb:
            if s.max_row > 10001 or s.max_column > 100:
                raise ValueError("Worksheet limit: 10,000 data rows, 100 columns")
            table = []
            for row in s:
                values = []
                for c in row:
                    value = c.value
                    if c.data_type == "f":
                        value = None
                        warnings.append(
                            f"{s.title}!{c.coordinate}: formula rejected; replace with a literal value"
                        )
                    if isinstance(value, (int, float)) and not isinstance(value, bool):
                        warnings.append(
                            f"{s.title}!{c.coordinate}: numeric cell; barcode leading zeros cannot be inferred"
                        )
                    values.append(value)
                table.append(values)
            sheets[s.title] = table
        wb.close()
    elif ext == "xls":
        wb = xlrd.open_workbook(file_contents=data, on_demand=True)
        for s in wb.sheets():
            if s.nrows > 10001 or s.ncols > 100:
                raise ValueError("Worksheet size limit exceeded")
            sheets[s.name] = [s.row_values(i) for i in range(s.nrows)]
            warnings.append(
                f"{s.name}: legacy XLS numeric cells and formula caches require review; use literal text barcodes"
            )
        wb.release_resources()
    else:
        raise ValueError("Choose CSV, XLSX or XLS")
    for table in sheets.values():
        if len(table) > 10001 or any(len(r) > 100 for r in table):
            raise ValueError("Worksheet size limit exceeded")
    return {"sheets": sheets, "warnings": warnings[:100]}


def propose(table):
    candidates = []
    for i, row in enumerate(table[:20]):
        mapping = {
            field: next((j for j, c in enumerate(row) if norm(c) in names), None)
            for field, names in ALIASES.items()
        }
        candidates.append((sum(v is not None for v in mapping.values()), -i, mapping))
    if not candidates:
        raise ValueError("Empty worksheet")
    _, negative, mapping = max(candidates, key=lambda c: (c[0], c[1]))
    return {
        "header": -negative,
        "mapping": mapping,
        "confirmation_required": True,
        "notice": "Confirm all mappings. Quantity may be inventory; SKU may not be a barcode. Numeric barcodes may have lost zeros.",
    }


SYMBOLS = [
    "Rs.",
    "PKR",
    "USD",
    "EUR",
    "GBP",
    "AED",
    "SAR",
    "$",
    "€",
    "£",
    "₨",
    "د.إ",
    "﷼",
]


def parse_price(value, decimal_separator="."):
    if value is None or str(value).strip() == "":
        raise ValueError("Price is required (zero is allowed)")
    s = str(value).strip()
    symbol = ""
    for item in SYMBOLS:
        if s.startswith(item):
            symbol = item
            s = s[len(item) :].strip()
            break
    if decimal_separator not in [".", ","]:
        raise ValueError("Select decimal separator")
    group = "," if decimal_separator == "." else "."
    pattern = rf"(?:\d+|\d{{1,3}}(?:{re.escape(group)}\d{{3}})+)(?:{re.escape(decimal_separator)}\d{{1,4}})?"
    if not re.fullmatch(pattern, s):
        raise ValueError(
            "Invalid or ambiguous price; correct it or change decimal convention"
        )
    return Decimal(s.replace(group, "").replace(decimal_separator, ".")), symbol


def convert(
    table,
    header,
    mapping,
    quantity_mode,
    default_quantity,
    confirmed,
    numeric_confirmed,
    decimal_separator,
):
    if not confirmed:
        raise ValueError("Confirm column mapping and quantity interpretation")
    if quantity_mode not in ["column", "fixed"]:
        raise ValueError("Choose column quantities or an explicit fixed quantity")
    products = []
    errors = []

    def cell(row, field):
        index = mapping.get(field)
        return row[index] if isinstance(index, int) and 0 <= index < len(row) else None

    for number, row in enumerate(table[header + 1 :], header + 2):
        if all(v is None or v == "" for v in row):
            continue
        try:
            barcode = cell(row, "barcode")
            if isinstance(barcode, bool):
                raise ValueError("Boolean cells cannot be barcodes")
            if isinstance(barcode, (int, float)):
                if not numeric_confirmed:
                    raise ValueError(
                        "Numeric barcode: confirm review of possible lost leading zeros"
                    )
                if barcode != int(barcode) or abs(barcode) > 999999999999999:
                    raise ValueError("Unsafe numeric barcode; supply exact text")
                barcode = str(int(barcode))
            price, embedded = parse_price(cell(row, "price"), decimal_separator)
            quantity = (
                cell(row, "quantity") if quantity_mode == "column" else default_quantity
            )
            if quantity is None:
                raise ValueError("Print quantity is required")
            q = Decimal(str(quantity))
            if not q.is_finite() or q != q.to_integral_value():
                raise ValueError("Quantity must be a positive whole number")
            currency = cell(row, "symbol")
            if currency and embedded and str(currency) != embedded:
                raise ValueError("Embedded and separate currencies conflict")
            p = Product(
                name=cell(row, "name"),
                barcode=barcode,
                price=price,
                symbol=str(currency or embedded or ""),
                quantity=int(q),
                source="spreadsheet",
                reference=f"row {number}",
            )
            products.append(p)
        except (ValueError, TypeError, InvalidOperation) as e:
            errors.append({"row": number, "error": str(e)})
    return {"products": products, "errors": errors}
