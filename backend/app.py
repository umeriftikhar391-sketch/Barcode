from pathlib import Path
from io import BytesIO
import hashlib, json, os, secrets, sqlite3, threading
from uuid import uuid4
from typing import Any
from fastapi import FastAPI, UploadFile, HTTPException, Request
from fastapi.responses import Response, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import Field
from PIL import ImageDraw
from .models import Queue, Geometry, Strict, Product
from .layout import rows
from .render import raster_row, label, tspl
from .importer import inspect_file, propose, convert
from . import odoo, printers

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STATE = (
    Path(os.environ.get("LOCALAPPDATA", str(ROOT))) / "BarcodeStudio"
    if os.name == "nt"
    else ROOT / ".local"
)
STATE = Path(os.environ.get("BARCODE_STATE", str(DEFAULT_STATE)))
STATE.mkdir(parents=True, exist_ok=True)
TOKEN = secrets.token_urlsafe(32)
LOCK = threading.Lock()


def db():
    c = sqlite3.connect(STATE / "state.sqlite")
    c.row_factory = sqlite3.Row
    c.execute(
        "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY,status TEXT NOT NULL,printer TEXT,spool_id INTEGER,detail TEXT)"
    )
    return c


def get_setting(key, default=None):
    with db() as c:
        r = c.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        return json.loads(r[0]) if r else default


def put_setting(key, value):
    with db() as c:
        c.execute(
            "INSERT OR REPLACE INTO settings VALUES (?,?)", (key, json.dumps(value))
        )


def fingerprint(g, printer, mode):
    return hashlib.sha256((g.model_dump_json() + printer + mode).encode()).hexdigest()


app = FastAPI(title="Barcode Studio", docs_url=None, redoc_url=None, openapi_url=None)


@app.middleware("http")
async def local_security(req: Request, call_next):
    # No wildcard CORS; reject foreign origins and DNS rebinding.
    host = req.headers.get("host", "")
    if host not in ["127.0.0.1:8765", "localhost:8765"]:
        return Response("Invalid host", status_code=403)
    origin = req.headers.get("origin")
    if origin and origin not in ["http://127.0.0.1:8765", "http://localhost:8765"]:
        return Response("Unexpected origin", status_code=403)
    if req.headers.get("sec-fetch-site") in ["cross-site", "same-site"]:
        return Response("Cross-site requests forbidden", status_code=403)
    if req.url.path.startswith("/api/") and req.url.path != "/api/session":
        if not secrets.compare_digest(req.headers.get("x-session-token", ""), TOKEN):
            return Response("Authorization required", status_code=401)
    response = await call_next(req)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cache-Control"] = "no-store"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' blob: data:; style-src 'self' 'unsafe-inline'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'"
    )
    return response


@app.exception_handler(ValueError)
async def value_error(req, exc):
    return Response(
        json.dumps({"detail": str(exc)}), status_code=400, media_type="application/json"
    )


@app.get("/api/session")
def session():
    return {"token": TOKEN, "platform": os.name}


@app.get("/api/queue")
def load_queue():
    return get_setting("queue", Queue().model_dump(mode="json"))


@app.put("/api/queue")
def save_queue(q: Queue):
    put_setting("queue", q.model_dump(mode="json"))
    return {"saved": True}


@app.post("/api/validate")
def validate(q: Queue):
    errors = q.geometry.errors()
    content = []
    for p in q.products:
        try:
            label(p, q.geometry)
        except ValueError as e:
            content.append({"id": p.id, "error": str(e)})
    return {
        "geometry_errors": errors,
        "content_errors": content,
        "labels": sum(p.quantity for p in q.products),
        "rows": len(rows(q.products)),
        "state": "Invalid geometry — preview only"
        if errors
        else "Geometry Valid — Hardware Calibration Pending",
    }


@app.post("/api/preview/{index}")
def preview(index: int, q: Queue):
    rr = rows(q.products)
    if index < 0 or index >= len(rr):
        raise ValueError("Row does not exist")
    im = raster_row(rr[index], q.geometry)
    out = BytesIO()
    im.save(out, format="PNG")
    return Response(out.getvalue(), media_type="image/png")


@app.post("/api/import/inspect")
async def inspect(file: UploadFile):
    data = await file.read(8 * 1024 * 1024 + 1)
    try:
        result = inspect_file(data, file.filename or "")
        result["proposals"] = {s: propose(t) for s, t in result["sheets"].items()}
        return result
    except ValueError:
        raise
    except Exception:
        raise ValueError(
            "File could not be parsed. Supply an unencrypted CSV, XLSX or XLS file."
        ) from None


class Mapping(Strict):
    table: list[list[Any]] = Field(max_length=10001)
    header: int = Field(ge=0, le=19)
    mapping: dict[str, int | None]
    quantity_mode: str
    default_quantity: int | None = None
    confirmed: bool = False
    numeric_confirmed: bool = False
    decimal_separator: str = "."


@app.post("/api/import/convert")
def import_convert(m: Mapping):
    return convert(**m.model_dump())


@app.get("/api/printers")
def list_printers():
    return {
        "printers": printers.discover(),
        "selected": get_setting("printer", ""),
        "windows": os.name == "nt",
    }


class Calibration(Strict):
    geometry: Geometry
    printer: str = Field(max_length=200)
    mode: str = "driver"
    measured: bool = False
    alignment: bool = False
    scanned: bool = False
    multirow: bool = False
    boundary: bool = False
    counts: bool = False
    command_reference_verified: bool = False


class Readiness(Strict):
    geometry: Geometry
    printer: str = Field(max_length=200)
    mode: str = "driver"


@app.post("/api/readiness")
def readiness(r: Readiness):
    ready = not r.geometry.errors() and get_setting("calibration") == fingerprint(
        r.geometry, r.printer, r.mode
    )
    return {
        "production_ready": ready,
        "basis": "Operator-confirmed physical calibration"
        if ready
        else "Physical calibration not recorded for this profile",
    }


@app.post("/api/calibration")
def calibrate(c: Calibration):
    if c.geometry.errors():
        raise ValueError("; ".join(c.geometry.errors()))
    if os.name != "nt" or c.printer not in [p["name"] for p in printers.discover()]:
        raise ValueError("Connect the Windows TSC printer before recording calibration")
    if not all([c.measured, c.alignment, c.scanned, c.multirow, c.boundary, c.counts]):
        raise ValueError(
            "Complete every physical test before confirming production readiness"
        )
    if c.mode == "raw" and not c.command_reference_verified:
        raise ValueError(
            "Verify TSPL commands against the official model manual before using direct printing"
        )
    if c.mode not in ["driver", "raw"]:
        raise ValueError("Invalid print method")
    put_setting("calibration", fingerprint(c.geometry, c.printer, c.mode))
    put_setting("printer", c.printer)
    return {
        "state": "Production Ready (operator physical confirmation recorded for this configuration)"
    }


class PrintRequest(Strict):
    id: str = Field(default_factory=lambda: str(uuid4()), min_length=8, max_length=100)
    queue: Queue
    printer: str = Field(max_length=200)
    mode: str = "driver"


@app.post("/api/print")
def print_job(p: PrintRequest):
    errors = p.queue.geometry.errors()
    if errors:
        raise ValueError("; ".join(errors))
    if not p.queue.products:
        raise ValueError("Empty queue cannot be printed")
    if p.mode not in ["driver", "raw"]:
        raise ValueError("Invalid print method")
    if get_setting("calibration") != fingerprint(p.queue.geometry, p.printer, p.mode):
        raise ValueError(
            "Production printing locked: complete physical calibration for this geometry, printer and method"
        )
    for row in rows(p.queue.products):
        raster_row(row, p.queue.geometry, True)
    return dispatch(p)


def dispatch(p):
    with LOCK:
        with db() as c:
            if c.execute("SELECT 1 FROM jobs WHERE id=?", (p.id,)).fetchone():
                raise HTTPException(
                    409,
                    "Job identifier already used. Inspect physical output before creating another job.",
                )
            c.execute(
                "INSERT INTO jobs VALUES (?,?,?,?,?)",
                (p.id, "Prepared", p.printer, None, ""),
            )
        try:
            job = printers.submit(p.queue, p.printer, p.mode)
            status = "Accepted by Spooler — Physical Confirmation Pending"
            detail = ""
        except Exception:
            job = None
            status = "Failed or uncertain — inspect printer before retry"
            detail = "Submission did not complete; automatic retry disabled"
        with db() as c:
            c.execute(
                "UPDATE jobs SET status=?,spool_id=?,detail=? WHERE id=?",
                (status, job, detail, p.id),
            )
    put_setting("printer", p.printer)
    return {"id": p.id, "status": status, "spool_id": job, "detail": detail}


class CalibrationSample(Strict):
    geometry: Geometry
    printer: str = Field(max_length=200)
    mode: str = "driver"
    id: str = Field(min_length=8, max_length=100)
    approved: bool = False
    command_reference_verified: bool = False


@app.post("/api/calibration-test")
def calibration_sample(s: CalibrationSample):
    if not s.approved:
        raise ValueError("Explicit approval of physical calibration output is required")
    if s.geometry.errors():
        raise ValueError("; ".join(s.geometry.errors()))
    if s.mode not in ["driver", "raw"]:
        raise ValueError("Invalid print method")
    if s.mode == "raw" and not s.command_reference_verified:
        raise ValueError(
            "First verify TSPL command semantics against the official manual"
        )
    q = Queue(
        geometry=s.geometry,
        products=[
            Product(
                name=f"{['Left', 'Middle', 'Right'][i % 3]} {i + 1}",
                barcode=f"00000{i + 1}",
                price="0",
                symbol="Rs.",
                quantity=1,
            )
            for i in range(7)
        ],
    )
    for r in rows(q.products):
        raster_row(r, q.geometry, True)
    return dispatch(PrintRequest(id=s.id, queue=q, printer=s.printer, mode=s.mode))


@app.get("/api/jobs")
def jobs():
    with db() as c:
        return [
            dict(r)
            for r in c.execute("SELECT * FROM jobs ORDER BY rowid DESC LIMIT 100")
        ]


@app.post("/api/jobs/{job_id}/cancel")
def cancel(job_id: str):
    with db() as c:
        r = c.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not r or not r["spool_id"]:
            raise ValueError("No cancellable spooler job")
        printers.cancel(r["printer"], r["spool_id"])
        c.execute(
            "UPDATE jobs SET status=? WHERE id=?",
            ("Cancellation requested — physical output uncertain", job_id),
        )
    return {
        "status": "Cancellation requested; already printed labels cannot be recalled"
    }


class OdooConfig(Strict):
    url: str
    database: str
    key: str = Field(min_length=1, max_length=512)


@app.post("/api/odoo/config")
def odoo_config(c: OdooConfig):
    odoo.configure(c.url, c.database, c.key)
    return {"saved": True}


@app.delete("/api/odoo/config")
def odoo_disconnect():
    odoo.disconnect()
    return {
        "removed": os.name == "nt",
        "notice": "Development environment variables must be removed from the backend environment separately.",
    }


@app.get("/api/odoo/products")
def odoo_products(search: str = "", offset: int = 0):
    if len(search) > 200 or offset < 0:
        raise ValueError("Invalid search")
    return odoo.products(search, offset)


@app.get("/api/odoo/currencies")
def odoo_currencies():
    return odoo.call(
        "res.currency",
        "search_read",
        {
            "domain": [["active", "=", True]],
            "fields": ["id", "name", "symbol"],
            "limit": 200,
        },
    )


@app.get("/api/odoo/pricelists")
def odoo_pricelists():
    return odoo.call(
        "product.pricelist",
        "search_read",
        {"domain": [], "fields": ["id", "name", "currency_id"], "limit": 100},
    )


@app.get("/api/odoo/pricelist-price")
def price():
    return odoo.pricelist_price()


@app.get("/api/templates/{kind}")
def template(kind: str):
    if kind not in ["csv", "xlsx"]:
        raise ValueError("Unknown template")
    return FileResponse(
        ROOT / "samples" / f"products.{kind}", filename=f"products.{kind}"
    )


if (ROOT / "frontend/dist").exists():
    app.mount(
        "/", StaticFiles(directory=ROOT / "frontend/dist", html=True), name="frontend"
    )
