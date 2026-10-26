from hashlib import sha256
from pathlib import Path
import zipfile

import pytest
from scripts.package_windows import build


@pytest.fixture
def project(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts/Setup-New-PC.template.cmd").write_bytes(
        (
            Path(__file__).resolve().parents[1] / "scripts/Setup-New-PC.template.cmd"
        ).read_bytes()
    )
    (tmp_path / "frontend/dist/assets").mkdir(parents=True)
    (tmp_path / "frontend/dist/index.html").write_text(
        '<script src="/assets/app.js"></script>'
    )
    (tmp_path / "frontend/dist/assets/app.js").write_text('console.log("ready")')
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv/secret.txt").write_text("not-for-distribution")
    (tmp_path / ".local").mkdir()
    (tmp_path / ".local/state.sqlite").write_text("private queue")
    (tmp_path / ".env").write_text("SECRET=not-for-distribution")
    (tmp_path / ".env.production").write_text("SECRET=not-for-distribution")
    (tmp_path / ".env.example").write_text("ODOO_API_KEY=")
    return tmp_path


def test_packages_pin_verified_app_and_exclude_local_state(project):
    ref = "a" * 40
    digest = build(project, ref)
    app = (project / "downloads/Barcode-Studio.zip").read_bytes()
    assert sha256(app).hexdigest() == digest
    with zipfile.ZipFile(project / "downloads/Barcode-Studio.zip") as archive:
        assert archive.testzip() is None
        names = archive.namelist()
        assert "Barcode/frontend/dist/index.html" in names
        assert "Barcode/frontend/dist/assets/app.js" in names
        assert "Barcode/.env.example" in names
        assert not any(
            "/.local/" in n
            or "/.venv/" in n
            or n.endswith("/.env")
            or ".env.production" in n
            for n in names
        )
        assert not any(
            "/downloads/" in n or n.endswith("/Setup-Barcode-Studio.cmd") for n in names
        )
    with zipfile.ZipFile(project / "downloads/Barcode-One-Click-Setup.zip") as setup:
        assert setup.namelist() == ["Setup-Barcode-Studio.cmd"]
        contents = setup.read("Setup-Barcode-Studio.cmd")
        assert contents == (project / "Setup-Barcode-Studio.cmd").read_bytes()
        assert digest.encode() in contents
        assert f"/{ref}/downloads/Barcode-Studio.zip".encode() in contents
        assert b"__PACKAGE_" not in contents
        assert contents.startswith(b"@echo off\r\n")


def test_rebuild_is_deterministic_and_ref_change_does_not_mutate_app(project):
    first = build(project, "a" * 40)
    original = (project / "downloads/Barcode-Studio.zip").read_bytes()
    assert build(project, "b" * 40) == first
    assert (project / "downloads/Barcode-Studio.zip").read_bytes() == original
    (project / "frontend/dist/assets/app.js").write_text('console.log("updated")')
    assert build(project, "b" * 40) != first


def test_requires_built_ui_and_explicit_valid_ref(project):
    with pytest.raises(ValueError):
        build(project, "../../other")
    (project / "frontend/dist/index.html").unlink()
    with pytest.raises(ValueError, match="Build the frontend"):
        build(project)
