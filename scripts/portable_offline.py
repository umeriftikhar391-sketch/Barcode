"""Create a zero-download deployment from the working PC's installed runtime.

No pip install/download, web requests or registry-based Python installation.
The private runtime is relocated and tested before the final ZIP is written.
"""

from __future__ import annotations
import argparse
import base64
import hashlib
import importlib.metadata as metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

from packaging.markers import default_environment
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from scripts import provision_printer as printer

ROOT = Path(__file__).resolve().parents[1]
MAX_FILES = 20000
MAX_BYTES = 2 * 1024 * 1024 * 1024
PTH = b".\r\nDLLs\r\nLib\r\nLib/site-packages\r\n..\r\nimport site\r\n"
LAUNCHER = b'@echo off\r\ncd /d "%~dp0"\r\n"Runtime\\python.exe" -B scripts\\launch.py\r\npause\r\n'


def installed_closure(requirements, lookup=metadata.distribution, environment=None):
    env = default_environment() if environment is None else environment
    pending = []
    for line in Path(requirements).read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            pending.append((Requirement(line), {""}))
    selected = {}
    expanded = {}
    while pending:
        req, parent_extras = pending.pop()
        if req.url:
            raise ValueError(
                "Direct-URL dependencies cannot be cloned into this deployment"
            )
        if req.marker and not any(
            req.marker.evaluate(dict(env, extra=e)) for e in parent_extras
        ):
            continue
        name = canonicalize_name(req.name)
        dist = selected.get(name) or lookup(name)
        if req.specifier and not req.specifier.contains(dist.version, prereleases=True):
            raise ValueError(
                f"Installed {name} {dist.version} does not satisfy {req.specifier}; the working environment has not been changed"
            )
        selected[name] = dist
        extras = set(req.extras) | {""}
        todo = extras - expanded.get(name, set())
        if not todo:
            continue
        expanded.setdefault(name, set()).update(todo)
        for dependency in dist.requires or []:
            pending.append((Requirement(dependency), todo))
    return selected


def copy_dependency_files(distributions, source_site, target_site):
    source_site = Path(source_site).resolve()
    target_site = Path(target_site)
    copied = 0
    for name, dist in sorted(distributions.items()):
        if not dist.files:
            raise ValueError(
                f"{name} has no installed file records; editable/legacy installs are unsupported"
            )
        for record in dist.files:
            rel = Path(str(record))
            if (
                "__pycache__" in rel.parts
                or rel.suffix == ".pyc"
                or rel.name == "direct_url.json"
            ):
                continue
            source = Path(dist.locate_file(record))
            # Console wrappers outside site-packages are unnecessary. Never copy
            # unrelated source files or anything referenced outside this library.
            resolved = source.resolve()
            if not resolved.is_relative_to(source_site):
                continue
            relative = resolved.relative_to(source_site)
            if source.is_symlink() or not source.is_file():
                raise ValueError(
                    f"Invalid installed dependency file: {name}/{relative}"
                )
            if record.hash:
                if record.hash.mode not in {"sha256", "sha384", "sha512"}:
                    raise ValueError(
                        "Unsupported installed file verification algorithm"
                    )
                h = hashlib.new(record.hash.mode)
                with source.open("rb") as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b""):
                        h.update(chunk)
                actual = base64.urlsafe_b64encode(h.digest()).rstrip(b"=").decode()
                if actual != record.hash.value:
                    raise ValueError(
                        f"Installed file differs from its recorded checksum: {name}/{relative}"
                    )
            elif not (
                relative.parent.name.endswith(".dist-info")
                and relative.name in {"RECORD", "INSTALLER", "REQUESTED"}
            ):
                raise ValueError(
                    f"Installed file has no verifiable record: {name}/{relative}"
                )
            target = target_site / relative
            if target.exists():
                if printer.digest(target) != printer.digest(source):
                    raise ValueError("Conflicting installed dependency files")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied += 1
    if not copied:
        raise ValueError("No installed dependency files were collected")
    return copied


def copy_runtime(base, target):
    base = Path(base)
    target = Path(target)
    for required in ["python.exe", "python312.dll", "Lib/os.py", "LICENSE.txt"]:
        if not (base / required).is_file():
            raise ValueError("The working CPython installation is missing " + required)
    printer.powershell(
        "foreach($f in @('python.exe','python312.dll')){$s=Get-AuthenticodeSignature -LiteralPath (Join-Path $env:BARCODE_SOURCE_RUNTIME $f);if($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch '(?:^|,\\s*)O=Python Software Foundation(?:,|$)'){throw ('Installed Python signature/publisher could not be verified: '+$f)}}",
        {"BARCODE_SOURCE_RUNTIME": str(base)},
    )
    target.mkdir(parents=True)
    wanted = [
        "python.exe",
        "pythonw.exe",
        "python312.dll",
        "python3.dll",
        "LICENSE.txt",
    ] + [p.name for p in base.glob("vcruntime*.dll")]
    for name in wanted:
        path = base / name
        if path.exists():
            shutil.copy2(path, target / name)
    for name in ["Lib", "DLLs"]:
        if (base / name).is_dir():
            shutil.copytree(
                base / name,
                target / name,
                ignore=shutil.ignore_patterns(
                    "site-packages",
                    "__pycache__",
                    "*.pyc",
                    "test",
                    "tests",
                    "idlelib",
                    "tkinter",
                    "turtledemo",
                    "sitecustomize.py",
                    "usercustomize.py",
                ),
            )
    (target / "Lib/site-packages").mkdir(parents=True, exist_ok=True)
    (target / "python312._pth").write_bytes(PTH)


def copy_app(source, target):
    target = Path(target)
    target.mkdir(parents=True)
    # Only curated code/resources, never source queues, logs or credentials.
    for name in ["backend", "scripts", "samples", "docs", "frontend/dist"]:
        src = Path(source) / name
        if not src.is_dir():
            raise ValueError("Application resource missing: " + name)
        shutil.copytree(
            src,
            target / name,
            ignore=shutil.ignore_patterns(
                "__pycache__",
                "*.pyc",
                "Runtime",
                "PrinterBundle",
                "OfflinePayload",
                "downloads",
            ),
        )
    for name in ["README.md", "requirements.txt"]:
        shutil.copy2(Path(source) / name, target / name)
    (target / "Start-Barcode.cmd").write_bytes(LAUNCHER)


def verify_relocated(app):
    runtime = Path(app) / "Runtime"
    modules = [
        "fastapi",
        "uvicorn",
        "openpyxl",
        "xlrd",
        "barcode",
        "PIL",
        "fontTools",
        "httpx",
        "keyring",
        "win32print",
        "win32ui",
        "pywintypes",
        "pythoncom",
    ]
    code = "import sys, pathlib, importlib; r=pathlib.Path(sys.executable).resolve().parent; assert pathlib.Path(sys.prefix).resolve()==r; "
    code += f"mods=[importlib.import_module(n) for n in {modules!r}]; assert all(pathlib.Path(m.__file__).resolve().is_relative_to(r) for m in mods); "
    code += "from backend.models import Product,Geometry; from backend.render import label; p=Product(name='Coaster',barcode='1000111',price='1200',symbol='Rs.',quantity=1); assert label(p,Geometry(width=33,height=24,safe=2)).size[0]>0; print('Relocated private runtime, native imports and renderer passed.')"
    subprocess.run(
        [str(runtime / "python.exe"), "-I", "-B", "-c", code], cwd=app, check=True
    )


def make_manifest(folder, versions):
    folder = Path(folder)
    files = {}
    total = 0
    for path in sorted(folder.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(folder).as_posix()
        if (
            not (name.startswith("Payload/App/") or name.startswith("PrinterBundle/"))
            or path.is_symlink()
        ):
            raise ValueError("Unexpected portable deployment file")
        total += path.stat().st_size
        if len(files) >= MAX_FILES or total > MAX_BYTES:
            raise ValueError("Portable package exceeds size/file limit")
        files[name] = {"bytes": path.stat().st_size, "sha256": printer.digest(path)}
    required = {
        "Payload/App/Runtime/python.exe",
        "Payload/App/Runtime/python312.dll",
        "Payload/App/Runtime/python312._pth",
        "Payload/App/frontend/dist/index.html",
        "Payload/App/Start-Barcode.cmd",
        "PrinterBundle/profile.json",
    }
    if not required.issubset(files):
        raise ValueError("Portable deployment is incomplete")
    return {
        "schema": 1,
        "kind": "portable-windows-x64",
        "python": "3.12",
        "packages": versions,
        "files": files,
    }


def installer(manifest_hash):
    import re

    if not re.fullmatch("[a-f0-9]{64}", manifest_hash):
        raise ValueError("Invalid portable manifest hash")
    template = (ROOT / "scripts/Install-Portable.template.cmd").read_text()
    return (
        template.replace("__MANIFEST_SHA256__", manifest_hash)
        .replace("\r\n", "\n")
        .replace("\n", "\r\n")
        .encode()
    )


def assemble(folder, output, versions):
    folder = Path(folder)
    output = Path(output)
    m = make_manifest(folder, versions)
    data = json.dumps(m, indent=2, sort_keys=True).encode()
    checksum = hashlib.sha256(data).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as z:
            z.writestr("Install-Barcode-OFFLINE.cmd", installer(checksum))
            z.writestr("manifest.json", data)
            for name in m["files"]:
                z.write(folder / name, name)
        with zipfile.ZipFile(output) as z:
            if z.testzip() is not None:
                raise ValueError("Portable archive integrity check failed")
    except FileExistsError:
        raise
    except Exception:
        output.unlink(missing_ok=True)
        raise
    return checksum


def create(output):
    if os.name != "nt" or sys.version_info[:2] != (3, 12) or sys.maxsize <= 2**32:
        raise RuntimeError(
            "Run this exporter with the working app's Windows CPython 3.12 x64 environment"
        )
    output = Path(output)
    if output.exists():
        raise FileExistsError("The earlier export has not been overwritten")
    source_site = Path(sys.prefix) / "Lib/site-packages"
    distributions = installed_closure(ROOT / "requirements.txt")
    versions = {name: d.version for name, d in distributions.items()}
    with tempfile.TemporaryDirectory(prefix="BarcodeNoNetwork-") as temp:
        temp = Path(temp)
        staging = temp / "bundle"
        app = staging / "Payload/App"
        print(
            "Copying application resources and the installed signed Python runtime..."
        )
        copy_app(ROOT, app)
        copy_runtime(sys.base_prefix, app / "Runtime")
        print(
            "Checking and copying installed application dependencies (no downloads)..."
        )
        copy_dependency_files(
            distributions, source_site, app / "Runtime/Lib/site-packages"
        )
        verify_relocated(app)
        print(
            "Exporting the working signed TE200 driver. Approve the Windows prompt..."
        )
        capture_cmd = temp / "capture.cmd"
        capture_cmd.write_bytes(b"@echo off\r\n")
        matched = temp / "printer.zip"
        printer.prepare(capture_cmd, matched, announce=False)
        with zipfile.ZipFile(matched) as z:
            for name in z.namelist():
                if name.startswith("PrinterBundle/"):
                    z.extract(name, staging)
        printer.load_bundle(staging / "PrinterBundle")
        assemble(staging, output, versions)
    print("ZERO-DOWNLOAD OFFLINE INSTALLER CREATED:", output)
    print(
        "Copy the complete ZIP by USB, extract it, and run Install-Barcode-OFFLINE.cmd on the new Windows x64 PC. No Internet is used to create or install this package."
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    create(args.output)
