import pytest
from fastapi.testclient import TestClient
from backend import app as module
from backend import odoo
from backend.models import Queue
from test_core import product, valid


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(module, "STATE", tmp_path)
    with TestClient(module.app, base_url="http://127.0.0.1:8765") as c:
        token = c.get("/api/session").json()["token"]
        c.headers["X-Session-Token"] = token
        yield c


def test_security(client):
    assert client.get("/api/queue").status_code == 200
    assert (
        client.get("/api/queue", headers={"X-Session-Token": "wrong"}).status_code
        == 401
    )
    assert (
        client.get("/api/session", headers={"Origin": "https://evil.test"}).status_code
        == 403
    )
    assert client.get("/api/session", headers={"Host": "evil.test"}).status_code == 403
    assert (
        client.get("/api/session", headers={"Sec-Fetch-Site": "cross-site"}).status_code
        == 403
    )


def test_queue_preview_and_lock(client):
    q = Queue(products=[product()], geometry=valid()).model_dump(mode="json")
    assert client.put("/api/queue", json=q).status_code == 200
    assert client.get("/api/queue").json() == q
    assert client.post("/api/validate", json=q).json()["labels"] == 1
    r = client.post("/api/preview/0", json=q)
    assert r.status_code == 200
    assert r.content.startswith(b"\x89PNG")
    assert (
        client.post(
            "/api/print", json={"id": "test-lock", "queue": q, "printer": "TSC"}
        ).status_code
        == 400
    )
    q["products"][0]["quantity"] = 0
    assert client.put("/api/queue", json=q).status_code == 422


def test_duplicate_and_uncertain_print(client, monkeypatch):
    q = Queue(products=[product()], geometry=valid())
    module.put_setting("calibration", module.fingerprint(q.geometry, "TSC", "driver"))
    monkeypatch.setattr(module.printers, "submit", lambda *args: 42)
    payload = {
        "id": "unique-job-id",
        "queue": q.model_dump(mode="json"),
        "printer": "TSC",
    }
    assert (
        "Physical Confirmation Pending"
        in client.post("/api/print", json=payload).json()["status"]
    )
    assert client.post("/api/print", json=payload).status_code == 409

    def fail(*args):
        raise RuntimeError("sensitive details")

    monkeypatch.setattr(module.printers, "submit", fail)
    payload["id"] = "failed-job-id"
    r = client.post("/api/print", json=payload)
    assert "uncertain" in r.json()["status"]
    assert "sensitive" not in r.text
    assert client.post("/api/print", json=payload).status_code == 409


def test_odoo_guard_and_missing(monkeypatch):
    monkeypatch.setattr(odoo, "credentials", lambda: (None, None, None))
    with pytest.raises(ValueError, match="credentials"):
        odoo.products("")
    with pytest.raises(ValueError, match="read-only"):
        odoo.call("product.product", "write", {})
    with pytest.raises(ValueError, match="blocked"):
        odoo.pricelist_price()


def test_odoo_wire(monkeypatch):
    import httpx

    monkeypatch.setattr(
        odoo, "credentials", lambda: ("https://test.odoo.com", "test", "secret")
    )
    seen = []

    class Client:
        def __init__(self, **kw):
            assert not kw["follow_redirects"]

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, url, headers, json):
            seen.append((url, headers, json))
            return httpx.Response(
                200, json=[{"id": 1, "barcode": "000123", "lst_price": 1200}]
            )

    monkeypatch.setattr(odoo.httpx, "Client", Client)
    assert odoo.products("coaster")[0]["barcode"] == "000123"
    assert seen[0][0].endswith("/json/2/product.product/search_read")
    assert seen[0][1]["Authorization"] == "bearer secret"
    assert seen[0][2]["limit"] == 100


def test_calibration_requires_approval(client):
    p = {
        "id": "sample-test",
        "geometry": valid().model_dump(),
        "printer": "TSC",
        "mode": "driver",
    }
    assert client.post("/api/calibration-test", json=p).status_code == 400
    p["approved"] = True
    p["mode"] = "raw"
    assert client.post("/api/calibration-test", json=p).status_code == 400
    p["command_reference_verified"] = True
    p["geometry"]["width"] = 35
    assert client.post("/api/calibration-test", json=p).status_code == 400


@pytest.mark.parametrize("status", [401, 403, 500])
def test_odoo_remote_errors_are_redacted(monkeypatch, status):
    import httpx

    monkeypatch.setattr(
        odoo, "credentials", lambda: ("https://test.odoo.com", "test", "secret")
    )

    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def post(self, *args, **kwargs):
            return httpx.Response(status, json={"debug": "sensitive traceback"})

    monkeypatch.setattr(odoo.httpx, "Client", Client)
    with pytest.raises(ValueError, match=str(status)) as exc:
        odoo.products("")
    assert "sensitive" not in str(exc.value)
