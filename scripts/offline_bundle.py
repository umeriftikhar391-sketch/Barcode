"""Build an Internet-free destination installer on the working Windows x64 PC."""

from __future__ import annotations
import argparse
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

from packaging.requirements import Requirement
from packaging.tags import sys_tags
from packaging.utils import canonicalize_name, parse_wheel_filename
from packaging.version import Version
from scripts import provision_printer as printer

ROOT = Path(__file__).resolve().parents[1]
PYTHON_URL = "https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe"
PYTHON_FILE = "python/python-3.12.10-amd64.exe"
APP_FILE = "application/Barcode-Studio.zip"
LOCK_FILE = "requirements-offline.txt"
MAX_PAYLOAD = 2 * 1024 * 1024 * 1024
ALLOWED = re.compile(
    r"(?:application/Barcode-Studio\.zip|python/python-3\.12\.10-amd64\.exe|requirements-offline\.txt|wheelhouse/[A-Za-z0-9_.+\-]+\.whl)"
)


def download(url, target, expected=None):
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=120) as response, target.open("xb") as out:
        if not response.url.startswith("https://"):
            raise ValueError("A secure download redirected to an insecure endpoint")
        total = 0
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > MAX_PAYLOAD:
                raise ValueError("Download exceeds package size limit")
            out.write(chunk)
    if expected and printer.digest(target) != expected:
        raise ValueError(
            "Application checksum mismatch; offline package was not created"
        )


def bootstrap_settings(data):
    text = data.decode("utf-8-sig")
    url = re.search(r"^\$packageUrl = '(https://[^']+)'\s*$", text, re.M)
    checksum = re.search(r"^\$packageHash = '([a-f0-9]{64})'\s*$", text, re.M)
    if not url or not checksum:
        raise ValueError(
            "Missing pinned application download/checksum in setup creator"
        )
    if not re.fullmatch(
        r"https://raw\.githubusercontent\.com/umeriftikhar391-sketch/Barcode/[a-f0-9]{40}/downloads/Barcode-Studio\.zip",
        url[1],
    ):
        raise ValueError(
            "Offline creator requires an immutable published application commit"
        )
    return url[1], checksum[1]


def lock_wheels(folder, compatible_tags=None):
    tags = set(sys_tags()) if compatible_tags is None else set(compatible_tags)
    records = {}
    for path in sorted(Path(folder).iterdir()):
        if not path.is_file() or path.suffix.lower() != ".whl":
            raise ValueError("Wheelhouse must contain only binary wheels")
        name, version, _, wheel_tags = parse_wheel_filename(path.name)
        if not tags.intersection(wheel_tags):
            raise ValueError(
                "Wheel is incompatible with the builder Python/platform: " + path.name
            )
        with zipfile.ZipFile(path) as z:
            members = [
                i for i in z.infolist() if i.filename.endswith(".dist-info/METADATA")
            ]
            if len(members) != 1 or members[0].file_size > 1024 * 1024:
                raise ValueError("Invalid wheel metadata: " + path.name)
            metadata = BytesParser().parsebytes(z.read(members[0]))
        if (
            canonicalize_name(metadata["Name"] or "") != name
            or Version(metadata["Version"] or "") != version
        ):
            raise ValueError("Wheel filename/metadata identity mismatch")
        for dependency in metadata.get_all("Requires-Dist", []):
            if Requirement(dependency).url:
                raise ValueError(
                    "Direct-URL wheel dependencies are not allowed in offline bundles"
                )
        if name in records:
            raise ValueError("Duplicate distribution wheels: " + name)
        records[name] = f"{name}=={version} --hash=sha256:{printer.digest(path)}"
    if not records:
        raise ValueError("Wheelhouse is empty")
    return "\n".join(records[n] for n in sorted(records)) + "\n"


def make_manifest(payload):
    payload = Path(payload)
    files = {}
    total = 0
    for path in sorted(payload.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(payload).as_posix()
        if not ALLOWED.fullmatch(name) or path.is_symlink():
            raise ValueError("Unexpected offline payload file: " + name)
        total += path.stat().st_size
        if total > MAX_PAYLOAD:
            raise ValueError("Offline payload is too large")
        files[name] = {"sha256": printer.digest(path), "bytes": path.stat().st_size}
    if not {APP_FILE, PYTHON_FILE, LOCK_FILE}.issubset(files) or not any(
        n.startswith("wheelhouse/") for n in files
    ):
        raise ValueError("Offline payload is incomplete")
    return {"schema": 1, "platform": "win_amd64", "python": "3.12", "files": files}


def verify_payload(payload, expected_manifest_hash):
    payload = Path(payload).resolve()
    manifest = payload / "manifest.json"
    if printer.digest(manifest) != expected_manifest_hash:
        raise ValueError("Offline manifest checksum mismatch")
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if (
        data.get("schema") != 1
        or data.get("platform") != "win_amd64"
        or data.get("python") != "3.12"
    ):
        raise ValueError("Unsupported offline payload")
    files = data.get("files", {})
    if not isinstance(files, dict) or not 4 <= len(files) <= 1000:
        raise ValueError("Invalid offline manifest")
    total = 0
    for name, info in files.items():
        if not ALLOWED.fullmatch(name):
            raise ValueError("Unsafe offline payload path")
        p = payload / name
        if p.is_symlink() or not p.resolve().is_relative_to(payload):
            raise ValueError("Unsafe payload symlink")
        total += p.stat().st_size
        if (
            total > MAX_PAYLOAD
            or p.stat().st_size != info["bytes"]
            or printer.digest(p) != info["sha256"]
        ):
            raise ValueError("Offline file checksum/size mismatch")
    actual = {
        p.relative_to(payload).as_posix() for p in payload.rglob("*") if p.is_file()
    }
    if actual != set(files) | {"manifest.json"}:
        raise ValueError("Unlisted offline payload file")
    if not {APP_FILE, PYTHON_FILE, LOCK_FILE}.issubset(files):
        raise ValueError("Missing offline prerequisite")
    return data


def offline_setup(data, manifest_hash):
    if not re.fullmatch("[a-f0-9]{64}", manifest_hash):
        raise ValueError("Invalid manifest checksum")
    text = data.decode("utf-8-sig")
    text, count = re.subn(
        r'^set "BARCODE_SETUP_MODE=(?:install|prepare|prepare-offline)"\r?$',
        'set "BARCODE_SETUP_MODE=install-offline"',
        text,
        count=1,
        flags=re.M,
    )
    if count != 1 or text.count("$offlineManifestHash = ''") != 1:
        raise ValueError("Setup creator does not support the offline package format")
    text = text.replace(
        "$offlineManifestHash = ''", f"$offlineManifestHash = '{manifest_hash}'", 1
    )
    return text.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8")


def offline_pip_args(python, wheelhouse, lock):
    return [
        str(python),
        "-m",
        "pip",
        "install",
        "--no-index",
        "--find-links",
        str(wheelhouse),
        "--require-hashes",
        "--only-binary=:all:",
        "--no-cache-dir",
        "--disable-pip-version-check",
        "-r",
        str(lock),
    ]


def offline_environment():
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith("PIP_")}
    env.update(
        PIP_CONFIG_FILE=os.devnull,
        PIP_NO_INDEX="1",
        PIP_NO_CACHE_DIR="1",
        PIP_DISABLE_PIP_VERSION_CHECK="1",
    )
    return env


def verify_clean_install(payload, directory):
    """Resolve/install every wheel from local files in a fresh private environment."""
    directory = Path(directory)
    subprocess.run([sys.executable, "-m", "venv", str(directory)], check=True)
    python = directory / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    env = offline_environment()
    subprocess.run(
        offline_pip_args(
            python, Path(payload) / "wheelhouse", Path(payload) / LOCK_FILE
        ),
        check=True,
        env=env,
    )
    subprocess.run([str(python), "-m", "pip", "check"], check=True, env=env)
    imports = "import fastapi,uvicorn,openpyxl,xlrd,barcode,PIL,fontTools,httpx,keyring"
    if os.name == "nt":
        imports += ",win32print,win32ui"
    subprocess.run(
        [
            str(python),
            "-c",
            imports
            + "; from backend.models import Product,Geometry; from backend.render import label; g=Geometry(width=33,height=24,safe=2); p=Product(name='Coaster',barcode='1000111',price='1200',symbol='Rs.',quantity=1); assert label(p,g).size[0]>0; print('Fresh local-wheel dependency and rendering check passed.')",
        ],
        check=True,
        env=env,
        cwd=ROOT,
    )


def assemble(destination, setup, payload, printer_bundle):
    destination = Path(destination)
    manifest_hash = printer.digest(Path(payload) / "manifest.json")
    verify_payload(payload, manifest_hash)
    printer.load_bundle(printer_bundle)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(destination, "x", zipfile.ZIP_DEFLATED) as z:
            z.writestr("Setup-Barcode-Studio.cmd", offline_setup(setup, manifest_hash))
            for prefix, folder in [
                ("OfflinePayload", payload),
                ("PrinterBundle", printer_bundle),
            ]:
                for p in sorted(Path(folder).rglob("*")):
                    if p.is_file():
                        z.write(p, Path(prefix) / p.relative_to(folder))
        with zipfile.ZipFile(destination) as z:
            if z.testzip() is not None:
                raise ValueError("Offline archive integrity check failed")
    except FileExistsError:
        raise
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return destination


def create(setup, output):
    if os.name != "nt" or sys.version_info[:2] != (3, 12):
        raise RuntimeError(
            "Create this bundle on the working Windows x64 PC using Python 3.12"
        )
    if sys.maxsize <= 2**32:
        raise RuntimeError("A 64-bit Python interpreter is required")
    setup = Path(setup).read_bytes()
    url, app_hash = bootstrap_settings(setup)
    output = Path(output)
    if output.exists():
        raise FileExistsError(
            "An earlier offline installer already exists; it has not been overwritten"
        )
    with tempfile.TemporaryDirectory(prefix="BarcodeOfflineBuild-") as temp:
        temp = Path(temp)
        payload = temp / "OfflinePayload"
        payload.mkdir()
        print("Downloading the pinned application archive for offline use...")
        download(url, payload / APP_FILE, app_hash)
        print("Downloading the full Python x64 installer for offline use...")
        download(PYTHON_URL, payload / PYTHON_FILE)
        printer.powershell(
            "$s=Get-AuthenticodeSignature -LiteralPath $env:BARCODE_PYTHON_INSTALLER; if($s.Status -ne 'Valid' -or $s.SignerCertificate.Subject -notmatch '(?:^|,\\s*)O=Python Software Foundation(?:,|$)'){throw 'Python installer signature/publisher could not be verified'}",
            {"BARCODE_PYTHON_INSTALLER": str(payload / PYTHON_FILE)},
        )
        wheels = payload / "wheelhouse"
        wheels.mkdir()
        print("Downloading all Windows Python dependency wheels...")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "pip",
                "download",
                "--only-binary=:all:",
                "--disable-pip-version-check",
                "--dest",
                str(wheels),
                "-r",
                str(ROOT / "requirements.txt"),
            ],
            check=True,
        )
        (payload / LOCK_FILE).write_text(lock_wheels(wheels), encoding="utf-8")
        print("Testing a clean dependency installation using local wheels only...")
        verify_clean_install(payload, temp / "verify-venv")
        print("Capturing the working signed printer driver and tested settings...")
        # Capture uses a temporary ordinary deployment ZIP. Never publish source-specific drivers.
        source_cmd = temp / "creator.cmd"
        source_cmd.write_bytes(setup)
        matched = temp / "matched.zip"
        printer.prepare(source_cmd, matched)
        captured = temp / "captured"
        with zipfile.ZipFile(matched) as z:
            z.extractall(captured)
        (payload / "manifest.json").write_text(
            json.dumps(make_manifest(payload), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        assemble(output, setup, payload, captured / "PrinterBundle")
    print("OFFLINE INSTALLER CREATED:", output)
    print(
        "Copy this entire ZIP to the new Windows x64 PC. Extract it and run Setup-Barcode-Studio.cmd without Internet. Windows driver approval and physical verification are still required."
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--setup", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    create(args.setup, args.output)
