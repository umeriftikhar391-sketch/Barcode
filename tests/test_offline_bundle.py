import hashlib
import json
from pathlib import Path
import zipfile

from packaging.tags import Tag
import pytest
from scripts import offline_bundle as o
from test_provisioning import make_bundle


def wheel(
    folder, name="demo-1.0-py3-none-any.whl", metadata="Name: demo\nVersion: 1.0\n"
):
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("demo-1.0.dist-info/METADATA", metadata)
    return path


def setup_bytes():
    root = Path(__file__).resolve().parents[1]
    text = (root / "scripts/Setup-New-PC.template.cmd").read_text()
    text = text.replace(
        "__PACKAGE_URL__",
        "https://raw.githubusercontent.com/umeriftikhar391-sketch/Barcode/"
        + "a" * 40
        + "/downloads/Barcode-Studio.zip",
    )
    return (
        text.replace("__PACKAGE_SHA256__", "b" * 64)
        .replace("__SETUP_MODE__", "prepare-offline")
        .encode()
    )


def payload(folder):
    folder.mkdir()
    for rel, body in [
        (o.APP_FILE, b"app archive fixture"),
        (o.PYTHON_FILE, b"Python signature fixture, not executed"),
    ]:
        p = folder / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(body)
    wheel(folder / "wheelhouse")
    (folder / o.LOCK_FILE).write_text(
        o.lock_wheels(folder / "wheelhouse", {Tag("py3", "none", "any")})
    )
    (folder / "manifest.json").write_text(json.dumps(o.make_manifest(folder)))
    return folder


def test_complete_payload_integrity_and_locked_dependencies(tmp_path):
    p = payload(tmp_path / "payload")
    checksum = o.printer.digest(p / "manifest.json")
    assert o.verify_payload(p, checksum)["platform"] == "win_amd64"
    w = p / "wheelhouse/demo-1.0-py3-none-any.whl"
    lock = (p / o.LOCK_FILE).read_text()
    assert (
        lock
        == "demo==1.0 --hash=sha256:"
        + hashlib.sha256(w.read_bytes()).hexdigest()
        + "\n"
    )
    w.write_bytes(b"changed")
    with pytest.raises(ValueError, match="checksum"):
        o.verify_payload(p, checksum)


@pytest.mark.parametrize("mutation", ["extra", "manifest", "missing"])
def test_offline_payload_never_accepts_unverified_files(tmp_path, mutation):
    p = payload(tmp_path / "payload")
    checksum = o.printer.digest(p / "manifest.json")
    if mutation == "extra":
        (p / "unlisted.exe").write_bytes(b"bad")
    if mutation == "manifest":
        (p / "manifest.json").write_text("{}")
    if mutation == "missing":
        (p / o.PYTHON_FILE).unlink()
    with pytest.raises((ValueError, FileNotFoundError)):
        o.verify_payload(p, checksum)


def test_no_source_distributions_duplicate_or_incompatible_wheels(tmp_path):
    folder = tmp_path / "wheels"
    wheel(folder)
    (folder / "source.tar.gz").write_bytes(b"no builds on offline PCs")
    with pytest.raises(ValueError, match="only binary"):
        o.lock_wheels(folder, {Tag("py3", "none", "any")})
    (folder / "source.tar.gz").unlink()
    wheel(folder, "demo-1.0-cp312-cp312-win_amd64.whl")
    with pytest.raises(ValueError, match="incompatible"):
        o.lock_wheels(folder, {Tag("py3", "none", "any")})
    with pytest.raises(ValueError, match="Duplicate"):
        o.lock_wheels(
            folder, {Tag("py3", "none", "any"), Tag("cp312", "cp312", "win_amd64")}
        )


def test_wheel_identity_must_match_metadata(tmp_path):
    folder = tmp_path / "wheels"
    wheel(folder, metadata="Name: different\nVersion: 1.0\n")
    with pytest.raises(ValueError, match="identity"):
        o.lock_wheels(folder, {Tag("py3", "none", "any")})


def test_only_pinned_application_can_be_bundled():
    assert o.bootstrap_settings(setup_bytes())[1] == "b" * 64
    with pytest.raises(ValueError, match="immutable"):
        o.bootstrap_settings(setup_bytes().replace(b"a" * 40, b"main"))


def test_offline_bootstrap_has_no_download_fallback(tmp_path):
    p = payload(tmp_path / "payload")
    expected = o.printer.digest(p / "manifest.json")
    cmd = o.offline_setup(setup_bytes(), expected)
    assert b"BARCODE_SETUP_MODE=install-offline" in cmd
    assert ("$offlineManifestHash = '" + expected + "'").encode() in cmd
    args = o.offline_pip_args("python", p / "wheelhouse", p / o.LOCK_FILE)
    assert (
        "--no-index" in args and "--require-hashes" in args and "--no-cache-dir" in args
    )
    assert "--only-binary=:all:" in args
    with pytest.raises(ValueError):
        o.offline_setup(b"old unsupported setup", expected)


def test_offline_zip_contains_all_prerequisites_and_preserves_existing_output(tmp_path):
    p = payload(tmp_path / "payload")
    bundle = tmp_path / "printer"
    make_bundle(bundle)
    out = tmp_path / "offline.zip"
    o.assemble(out, setup_bytes(), p, bundle)
    before = out.read_bytes()
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        names = z.namelist()
        assert "OfflinePayload/" + o.APP_FILE in names
        assert "OfflinePayload/" + o.PYTHON_FILE in names
        assert "OfflinePayload/" + o.LOCK_FILE in names
        assert "PrinterBundle/driver/tsc.cat" in names
        assert "PrinterBundle/devmode.bin" in names
        assert "Setup-Barcode-Studio.cmd" in names
        extracted = tmp_path / "extracted"
        z.extractall(extracted)
    cmd = (extracted / "Setup-Barcode-Studio.cmd").read_text()
    import re

    checksum = re.search(r"\$offlineManifestHash = '([a-f0-9]+)'", cmd)[1]
    o.verify_payload(extracted / "OfflinePayload", checksum)
    o.printer.load_bundle(extracted / "PrinterBundle")
    with pytest.raises(FileExistsError):
        o.assemble(out, setup_bytes(), p, bundle)
    assert out.read_bytes() == before


def test_direct_dependency_urls_are_not_accepted(tmp_path):
    folder = tmp_path / "wheels"
    wheel(
        folder,
        metadata="Name: demo\nVersion: 1.0\nRequires-Dist: other @ https://example.invalid/other.whl\n",
    )
    with pytest.raises(ValueError, match="Direct-URL"):
        o.lock_wheels(folder, {Tag("py3", "none", "any")})


def test_external_pip_configuration_is_not_inherited(monkeypatch):
    monkeypatch.setenv("PIP_FIND_LINKS", "https://example.invalid/wheels")
    monkeypatch.setenv("PIP_REQUIREMENT", "https://example.invalid/requirements.txt")
    monkeypatch.setenv("PIP_INDEX_URL", "https://example.invalid/simple")
    env = o.offline_environment()
    assert "PIP_FIND_LINKS" not in env
    assert "PIP_REQUIREMENT" not in env and "PIP_INDEX_URL" not in env
    assert env["PIP_NO_INDEX"] == "1"
    assert env["PIP_CONFIG_FILE"] == o.os.devnull
