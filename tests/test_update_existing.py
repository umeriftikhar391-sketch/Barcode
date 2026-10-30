from hashlib import sha256
from pathlib import Path
import socket
import zipfile
import pytest
from scripts.update_existing import update


@pytest.fixture
def installation(tmp_path, monkeypatch):
    def offline(*args, **kwargs):
        raise ConnectionRefusedError()

    monkeypatch.setattr(socket, "create_connection", offline)
    target = tmp_path / "Existing app"
    for name in (
        "backend/app.py",
        "frontend/dist/index.html",
        "Runtime/python.exe",
        ".venv/saved",
        "Start-Barcode.cmd",
        ".local/state.sqlite",
    ):
        path = target / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("original")
    archive = tmp_path / "Application.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        for name in (
            "backend/app.py",
            "backend/render.py",
            "backend/models.py",
            "frontend/dist/index.html",
            "frontend/dist/assets/new.js",
        ):
            bundle.writestr("Barcode/" + name, "updated")
        bundle.writestr("Barcode/Start-Barcode.cmd", "must not overwrite")
    return target, archive, sha256(archive.read_bytes()).hexdigest()


def test_update_preserves_runtime_state_launcher_and_backup(installation):
    target, archive, digest = installation
    update(target, archive, digest)
    assert (target / "backend/render.py").read_text() == "updated"
    assert (target / "frontend/dist/assets/new.js").read_text() == "updated"
    for name in (
        "Runtime/python.exe",
        ".venv/saved",
        ".local/state.sqlite",
        "Start-Barcode.cmd",
    ):
        assert (target / name).read_text() == "original"
    backups = list((target / ".update-backups").iterdir())
    assert (backups[0] / "backend/app.py").read_text() == "original"


def test_wrong_hash_and_running_server_prevent_update(installation, monkeypatch):
    target, archive, digest = installation
    with pytest.raises(ValueError, match="checksum"):
        update(target, archive, "0" * 64)

    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    monkeypatch.setattr(
        socket, "create_connection", lambda *args, **kwargs: Connection()
    )
    with pytest.raises(ValueError, match="running"):
        update(target, archive, digest)
    assert (target / "backend/app.py").read_text() == "original"


def test_failed_update_rolls_back_all_replaced_folders(installation, monkeypatch):
    import os

    target, archive, digest = installation
    original = os.replace

    def fail(source, dest):
        if ".barcode-update-" in str(source) and Path(source).parts[-2:] == (
            "frontend",
            "dist",
        ):
            raise OSError("test failed copy")
        return original(source, dest)

    monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError):
        update(target, archive, digest)
    assert (target / "backend/app.py").read_text() == "original"
    assert (target / "frontend/dist/index.html").read_text() == "original"
