import json
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import zipfile

import pytest
from backend.models import Geometry, Product, Queue
from scripts import provision_printer as p


def profile_bytes():
    data = bytearray(224)
    struct.pack_into("<HH", data, 68, 220, 4)
    return bytes(data)


def make_bundle(folder):
    folder.mkdir()
    (folder / "driver").mkdir()
    (folder / "driver/tsc.inf").write_bytes(b"fixture inf")
    (folder / "driver/tsc.cat").write_bytes(b"fixture catalog, not a real signature")
    (folder / "devmode.bin").write_bytes(profile_bytes())
    files = {
        f.relative_to(folder).as_posix(): p.digest(f)
        for f in folder.rglob("*")
        if f.is_file()
    }
    m = dict(
        schema=1,
        environment="Windows x64",
        driver_name="TSC TE200",
        driver_version=123,
        geometry=p.DEFAULT_GEOMETRY.model_dump(),
        forms=[],
        files=files,
    )
    (folder / "profile.json").write_text(json.dumps(m))
    return m


def test_profile_requires_integrity_and_exact_confirmed_roll(tmp_path):
    folder = tmp_path / "bundle"
    make_bundle(folder)
    assert p.load_bundle(folder)["geometry"]["height"] == 24
    (folder / "driver/tsc.inf").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="checksum"):
        p.load_bundle(folder)


@pytest.mark.parametrize("mutation", ["escape", "extra", "geometry", "devmode"])
def test_rejects_unsafe_or_incompatible_bundle(tmp_path, mutation):
    folder = tmp_path / "bundle"
    m = make_bundle(folder)
    if mutation == "escape":
        m["files"]["../outside"] = "a" * 64
    if mutation == "extra":
        (folder / "unlisted.exe").write_bytes(b"x")
    if mutation == "geometry":
        m["geometry"]["width"] = 35
    if mutation == "devmode":
        f = folder / "devmode.bin"
        f.write_bytes(b"x" * 224)
        m["files"]["devmode.bin"] = p.digest(f)
    (folder / "profile.json").write_text(json.dumps(m))
    with pytest.raises(ValueError):
        p.load_bundle(folder)


def test_default_seed_preserves_existing_workspace_and_never_copies_calibration(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    p.initialize()
    q = p.workspace()
    assert (
        q.geometry.backing,
        q.geometry.width,
        q.geometry.height,
        q.geometry.safe,
    ) == (107, 33, 24, 2)
    assert q.geometry.errors() == []
    import sqlite3

    q.products = [
        Product(
            name="Keep me", barcode="000001", price="1200", symbol="Rs.", quantity=2
        )
    ]
    with sqlite3.connect(p.state_path()) as c:
        c.execute(
            "UPDATE settings SET value=? WHERE key='queue'", (q.model_dump_json(),)
        )
        c.execute(
            "INSERT INTO settings VALUES (?,?)",
            ("calibration", json.dumps("original-local-check")),
        )
    p.initialize()
    with sqlite3.connect(p.state_path()) as c:
        assert c.execute(
            "SELECT value FROM settings WHERE key='calibration'"
        ).fetchone()
    p.initialize("TSC TE200", replace_profile=True)
    assert p.workspace().products[0].name == "Keep me"
    with sqlite3.connect(p.state_path()) as c:
        assert (
            c.execute("SELECT value FROM settings WHERE key='calibration'").fetchone()
            is None
        )
        assert (
            "pending"
            in c.execute(
                "SELECT value FROM settings WHERE key='provisioned'"
            ).fetchone()[0]
        )


def test_existing_different_profile_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    p.initialize(geometry=Geometry(width=33, height=25))
    original = p.state_path().read_bytes()
    with pytest.raises(RuntimeError, match="preserved"):
        p.initialize("TSC TE200", replace_profile=True)
    assert p.state_path().read_bytes() == original


def test_capture_zip_contains_only_driver_profile_and_bootstrap(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    p.initialize()
    printer = {
        "pPrinterName": "TSC TE200",
        "pDriverName": "TSC TE200",
        "pPortName": "USB003",
    }
    monkeypatch.setattr(p, "matching_printers", lambda *args: [printer])
    monkeypatch.setattr(
        p,
        "driver_info",
        lambda name: dict(Name=name, Environment="Windows x64", DriverVersion=123),
    )
    monkeypatch.setattr(
        p, "check_page", lambda *args: dict(page_width=855, page_height=192)
    )
    monkeypatch.setattr(p, "devmode", lambda *args: profile_bytes())

    class Handle:
        def __init__(self, *args):
            pass

        def __enter__(self):
            return 1

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(p, "printer_handle", Handle)
    monkeypatch.setitem(
        sys.modules, "win32print", SimpleNamespace(EnumForms=lambda h: [])
    )

    def export(operation, folder, printer):
        assert operation == "export-machine"
        folder.mkdir()
        (folder / "tsc.inf").write_bytes(b"fixture")
        (folder / "tsc.cat").write_bytes(b"fixture")

    monkeypatch.setattr(p, "admin_action", export)
    setup = tmp_path / "prepare.cmd"
    setup.write_bytes(b'@echo off\r\nset "BARCODE_SETUP_MODE=prepare"\r\n')
    output = tmp_path / "new-pc.zip"
    p.prepare(setup, output)
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert b"BARCODE_SETUP_MODE=install" in z.read("Setup-Barcode-Studio.cmd")
        assert not any(
            n.endswith(".sqlite") or "credential" in n.lower() or "queue" in n.lower()
            for n in z.namelist()
        )
        manifest = json.loads(z.read("PrinterBundle/profile.json"))
        assert set(manifest) == {
            "schema",
            "environment",
            "driver_name",
            "driver_version",
            "geometry",
            "caps",
            "forms",
            "files",
        }
        extracted = tmp_path / "check"
        z.extractall(extracted)
    p.load_bundle(extracted / "PrinterBundle")
    with pytest.raises(FileExistsError):
        p.prepare(setup, output)


def test_restore_does_not_guess_usb_port_or_use_epson(tmp_path, monkeypatch):
    folder = tmp_path / "bundle"
    make_bundle(folder)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    monkeypatch.setattr(p, "admin_action", lambda *args: None)
    monkeypatch.setattr(p.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(p, "matching_printers", lambda driver: [])
    with pytest.raises(RuntimeError, match="No USB001 port or Epson queue was guessed"):
        p.restore(folder)
    assert not p.state_path().exists()


def test_restore_applies_profile_without_production_confirmation(tmp_path, monkeypatch):
    folder = tmp_path / "bundle"
    m = make_bundle(folder)
    m["geometry"]["density"] = 9
    (folder / "profile.json").write_text(json.dumps(m))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "user"))
    monkeypatch.setattr(p, "admin_action", lambda *args: None)
    monkeypatch.setattr(
        p,
        "matching_printers",
        lambda driver: [{"pPrinterName": "TSC TE200 new", "pPortName": "USB005"}],
    )
    monkeypatch.setattr(p, "driver_info", lambda name: dict(DriverVersion=123))
    applied = []
    monkeypatch.setattr(p, "devmode", lambda name, data: applied.append((name, data)))
    monkeypatch.setattr(p, "check_page", lambda *args: None)
    p.restore(folder)
    assert applied == [("TSC TE200 new", profile_bytes())]
    assert p.workspace().geometry == Geometry.model_validate(m["geometry"])
    import sqlite3

    with sqlite3.connect(p.state_path()) as c:
        assert (
            c.execute("SELECT value FROM settings WHERE key='calibration'").fetchone()
            is None
        )
        assert (
            json.loads(
                c.execute("SELECT value FROM settings WHERE key='printer'").fetchone()[
                    0
                ]
            )
            == "TSC TE200 new"
        )
