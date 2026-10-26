"""Build deterministic Windows source and single-file setup downloads.

Run after frontend build; commit the application package first, then regenerate
setup with --ref <that commit SHA> so old setup files keep immutable downloads.
"""

from pathlib import Path
from hashlib import sha256
import argparse
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = {
    ".git",
    ".venv",
    ".local",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "__pycache__",
    "build",
    "downloads",
}


def package_files(root):
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if not path.is_file() or EXCLUDED.intersection(rel.parts):
            continue
        if rel.as_posix() == "Setup-Barcode-Studio.cmd" or path.name.endswith(
            ".tsbuildinfo"
        ):
            continue
        if (
            path.name == ".env"
            or path.name.startswith(".env.")
            and path.name != ".env.example"
        ):
            continue
        yield path, rel


def add_bytes(archive, name, contents):
    entry = zipfile.ZipInfo(
        str(name).replace("\\", "/"), date_time=(2026, 1, 1, 0, 0, 0)
    )
    entry.compress_type = zipfile.ZIP_DEFLATED
    entry.external_attr = 0o100644 << 16
    archive.writestr(entry, contents)


def build(root=ROOT, ref="main"):
    if not (ref == "main" or re.fullmatch(r"[a-f0-9]{40}", ref)):
        raise ValueError(
            "Use main for preparation, or a full immutable application-package commit SHA"
        )
    if not (root / "frontend/dist/index.html").is_file():
        raise ValueError("Build the frontend before packaging")
    downloads = root / "downloads"
    downloads.mkdir(exist_ok=True)
    target = downloads / "Barcode-Studio.zip"
    with zipfile.ZipFile(target, "w") as archive:
        for path, rel in package_files(root):
            add_bytes(archive, Path("Barcode") / rel, path.read_bytes())
    digest = sha256(target.read_bytes()).hexdigest()
    template = (root / "scripts/Setup-New-PC.template.cmd").read_text(encoding="utf-8")
    url = f"https://raw.githubusercontent.com/umeriftikhar391-sketch/Barcode/{ref}/downloads/Barcode-Studio.zip"
    rendered = template.replace("__PACKAGE_URL__", url).replace(
        "__PACKAGE_SHA256__", digest
    )
    contents = rendered.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")
    (root / "Setup-Barcode-Studio.cmd").write_bytes(contents)
    with zipfile.ZipFile(downloads / "Barcode-One-Click-Setup.zip", "w") as archive:
        add_bytes(archive, "Setup-Barcode-Studio.cmd", contents)
    return digest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ref", default="main")
    args = parser.parse_args()
    print("Application SHA256:", build(ref=args.ref))
