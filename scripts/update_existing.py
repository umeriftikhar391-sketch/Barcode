"""Apply a verified application-only update using an existing Python runtime."""

import argparse
from datetime import datetime
from hashlib import sha256
from io import BytesIO
from pathlib import Path, PurePosixPath
import os
import shutil
import socket
import tempfile
import zipfile


def update(target, archive, expected):
    target = Path(target).resolve()
    if (
        not (target / "Start-Barcode.cmd").is_file()
        or not (target / "backend/app.py").is_file()
    ):
        raise ValueError("Choose the folder containing your working Start-Barcode.cmd.")
    try:
        with socket.create_connection(("127.0.0.1", 8765), timeout=1):
            raise ValueError(
                "Barcode Studio is running. Click Close app in its sidebar (or close its server console), then run the update again."
            )
    except OSError:
        pass
    data = Path(archive).read_bytes()
    if sha256(data).hexdigest() != expected:
        raise ValueError(
            "Application checksum mismatch. Extract the whole update ZIP again."
        )
    folders = ("backend", "frontend/dist")
    with tempfile.TemporaryDirectory(
        prefix=".barcode-update-", dir=target
    ) as temporary:
        stage = Path(temporary)
        with zipfile.ZipFile(BytesIO(data)) as bundle:
            total = 0
            for item in bundle.infolist():
                name = PurePosixPath(item.filename)
                if (
                    name.is_absolute()
                    or ".." in name.parts
                    or "\\" in item.filename
                    or ":" in item.filename
                ):
                    raise ValueError("Unsafe update archive path.")
                if (
                    not item.filename.startswith(
                        ("Barcode/backend/", "Barcode/frontend/dist/")
                    )
                    or item.is_dir()
                ):
                    continue
                total += item.file_size
                if total > 100_000_000:
                    raise ValueError("Application update exceeds size limit.")
                dest = stage.joinpath(*name.parts[1:])
                dest.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    raise ValueError("Duplicate update archive path.")
                dest.write_bytes(bundle.read(item))
        for required in (
            "backend/app.py",
            "backend/models.py",
            "backend/render.py",
            "frontend/dist/index.html",
        ):
            if not (stage / required).is_file():
                raise ValueError("Application update is incomplete.")
        for relative in folders:
            dest = target / relative
            if any(p.is_symlink() for p in (dest, dest.parent)):
                raise ValueError("Linked application folders are not supported.")
        backup = (
            target / ".update-backups" / datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        )
        backup.mkdir(parents=True)
        replaced = []
        try:
            for relative in folders:
                dest, saved = target / relative, backup / relative
                dest.parent.mkdir(parents=True, exist_ok=True)
                saved.parent.mkdir(parents=True, exist_ok=True)
                if dest.exists():
                    os.replace(dest, saved)
                replaced.append((dest, saved))
                os.replace(stage / relative, dest)
        except Exception:
            for dest, saved in reversed(replaced):
                if dest.exists():
                    shutil.rmtree(dest)
                if saved.exists():
                    os.replace(saved, dest)
            raise
    print(
        "Update installed. Python, driver, products and saved dimensions were preserved."
    )
    print("Previous application files: " + str(backup))
    print(
        "Automatic fit is enabled on first launch. Calibration checklists are optional. Review preview warnings before printing."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--archive", required=True, type=Path)
    parser.add_argument("--sha256", required=True)
    args = parser.parse_args()
    update(args.target, args.archive, args.sha256)
