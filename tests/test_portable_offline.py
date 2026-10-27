import base64
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import zipfile

import pytest
from scripts import portable_offline as p


class Dist:
    def __init__(self, name, version, requires=None):
        self.version = version
        self.requires = requires or []


def test_installed_dependency_graph_includes_extras_and_windows_markers(tmp_path):
    requirements = tmp_path / "requirements.txt"
    requirements.write_text("root[print]==1.0\n")
    records = {
        "root": Dist(
            "root",
            "1.0",
            [
                'dep>=2; extra == "print"',
                'win==3; sys_platform == "win32"',
                'linux; sys_platform == "linux"',
            ],
        ),
        "dep": Dist("dep", "2.0"),
        "win": Dist("win", "3"),
    }
    result = p.installed_closure(
        requirements, records.__getitem__, {"sys_platform": "win32"}
    )
    assert set(result) == {"root", "dep", "win"}
    records["dep"].version = "1.5"
    with pytest.raises(ValueError, match="does not satisfy"):
        p.installed_closure(
            requirements, records.__getitem__, {"sys_platform": "win32"}
        )


def test_direct_urls_are_not_copied(tmp_path):
    r = tmp_path / "r.txt"
    r.write_text("package @ https://example.invalid/private.whl\n")
    with pytest.raises(ValueError, match="Direct-URL"):
        p.installed_closure(r)


class Record(str):
    def __new__(cls, path, body, hashed=True):
        obj = super().__new__(cls, path)
        obj.hash = (
            SimpleNamespace(
                mode="sha256",
                value=base64.urlsafe_b64encode(hashlib.sha256(body).digest())
                .rstrip(b"=")
                .decode(),
            )
            if hashed
            else None
        )
        return obj


class Installed:
    def __init__(self, base, records):
        self.base = base
        self.files = records

    def locate_file(self, record):
        return self.base / str(record)


def test_only_verified_installed_library_files_are_copied(tmp_path):
    source = tmp_path / "site"
    source.mkdir()
    records = []
    for path, body in [
        ("package/__init__.py", b"version=1"),
        ("package-1.dist-info/METADATA", b"Name: package\nVersion: 1\n"),
        ("package-1.dist-info/direct_url.json", b"private source URL"),
        ("package/__pycache__/file.pyc", b"cache"),
    ]:
        f = source / path
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(body)
        records.append(Record(path, body))
    (tmp_path / "secret.txt").write_bytes(b"private source file")
    records.append(Record("../secret.txt", b"private source file"))
    target = tmp_path / "copied"
    assert (
        p.copy_dependency_files({"package": Installed(source, records)}, source, target)
        == 2
    )
    assert (target / "package/__init__.py").read_bytes() == b"version=1"
    assert not (target / "package-1.dist-info/direct_url.json").exists()
    assert not (target / "package/__pycache__").exists()
    assert not (target / "secret.txt").exists()
    (source / "package/__init__.py").write_bytes(b"modified")
    with pytest.raises(ValueError, match="checksum"):
        p.copy_dependency_files(
            {"package": Installed(source, records)}, source, tmp_path / "bad"
        )


def test_unhashed_code_is_not_exported(tmp_path):
    f = tmp_path / "package.py"
    f.write_bytes(b"code")
    dist = Installed(tmp_path, [Record("package.py", b"code", False)])
    with pytest.raises(ValueError, match="no verifiable"):
        p.copy_dependency_files({"package": dist}, tmp_path, tmp_path / "target")


def minimal_payload(folder):
    required = [
        "Payload/App/Runtime/python.exe",
        "Payload/App/Runtime/python312.dll",
        "Payload/App/Runtime/python312._pth",
        "Payload/App/frontend/dist/index.html",
        "Payload/App/Start-Barcode.cmd",
        "PrinterBundle/profile.json",
    ]
    for name in required:
        f = folder / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_bytes(b"fixture only")


def test_full_portable_archive_is_local_complete_and_never_overwrites(tmp_path):
    folder = tmp_path / "staging"
    minimal_payload(folder)
    output = tmp_path / "offline.zip"
    checksum = p.assemble(folder, output, {"package": "1.0"})
    original = output.read_bytes()
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        manifest = json.loads(z.read("manifest.json"))
        assert hashlib.sha256(z.read("manifest.json")).hexdigest() == checksum
        assert checksum.encode() in z.read("Install-Barcode-OFFLINE.cmd")
        assert "Payload/App/Runtime/python.exe" in manifest["files"]
        assert "PrinterBundle/profile.json" in manifest["files"]
        for name, info in manifest["files"].items():
            assert hashlib.sha256(z.read(name)).hexdigest() == info["sha256"]
    with pytest.raises(FileExistsError):
        p.assemble(folder, output, {"package": "1.0"})
    assert output.read_bytes() == original


def test_private_or_missing_files_block_packaging(tmp_path):
    folder = tmp_path / "staging"
    minimal_payload(folder)
    (folder / "credentials.txt").write_text("not for export")
    with pytest.raises(ValueError, match="Unexpected"):
        p.make_manifest(folder, {})
    (folder / "credentials.txt").unlink()
    (folder / "Payload/App/Runtime/python.exe").unlink()
    with pytest.raises(ValueError, match="incomplete"):
        p.make_manifest(folder, {})
