"""Transfer the tested TE200 driver/profile without transferring calibration claims.

Windows operations are intentionally isolated from archive/manifest validation.
No driver installer switches or firmware calibration commands are guessed.
"""

from __future__ import annotations
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import struct
import subprocess
import sys
import tempfile
import time
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.models import Geometry, Queue

MAX_DRIVER_BYTES = 300 * 1024 * 1024
DEFAULT_GEOMETRY = Geometry(width=33, height=24, safe=2)


def digest(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def check_devmode(data):
    if not 220 <= len(data) <= 1024 * 1024:
        raise ValueError("Invalid Windows printer profile size")
    size, extra = struct.unpack_from("<HH", data, 68)
    if size < 220 or size + extra != len(data):
        raise ValueError("Invalid DEVMODE header/private-data size")
    return data


def load_bundle(folder):
    folder = Path(folder).resolve()
    manifest_path = folder / "profile.json"
    if manifest_path.stat().st_size > 100000:
        raise ValueError("Printer manifest is too large")
    m = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    if m.get("schema") != 1 or m.get("environment") != "Windows x64":
        raise ValueError("Unsupported printer bundle format/architecture")
    if (
        not isinstance(m.get("driver_name"), str)
        or "TE200" not in m["driver_name"].upper()
    ):
        raise ValueError("Bundle is not for the TSC TE200")
    if not isinstance(m.get("driver_version"), int):
        raise ValueError("Missing exact Windows driver version")
    geometry = Geometry.model_validate(m["geometry"])
    if geometry.errors():
        raise ValueError("; ".join(geometry.errors()))
    for key in (
        "backing",
        "width",
        "height",
        "columns",
        "gap_x",
        "gap_y",
        "left",
        "right",
        "safe",
        "dpi",
    ):
        if getattr(geometry, key) != getattr(DEFAULT_GEOMETRY, key):
            raise ValueError(
                "Bundle does not match the confirmed 107 mm / 33 x 24 mm roll"
            )
    files = m.get("files")
    if not isinstance(files, dict) or not 2 <= len(files) <= 5000:
        raise ValueError("Invalid printer file manifest")
    total = 0
    for name, expected in files.items():
        if not isinstance(name, str) or "\\" in name or ":" in name:
            raise ValueError("Unsafe bundle path")
        p = folder / name
        if (
            Path(name).is_absolute()
            or ".." in Path(name).parts
            or p.is_symlink()
            or not p.resolve().is_relative_to(folder)
        ):
            raise ValueError("Unsafe bundle path")
        if not isinstance(expected, str) or not re.fullmatch("[a-f0-9]{64}", expected):
            raise ValueError("Invalid file checksum")
        total += p.stat().st_size
        if total > MAX_DRIVER_BYTES or digest(p) != expected:
            raise ValueError("Printer bundle checksum/size validation failed")
    if (
        "devmode.bin" not in files
        or not any(
            n.startswith("driver/") and n.lower().endswith(".inf") for n in files
        )
        or not any(
            n.startswith("driver/") and n.lower().endswith(".cat") for n in files
        )
    ):
        raise ValueError("Driver INF, signed catalog and printer profile are required")
    actual = {
        p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()
    }
    if actual != set(files) | {"profile.json"}:
        raise ValueError("Unexpected files in printer bundle")
    check_devmode((folder / "devmode.bin").read_bytes())
    forms = m.get("forms", [])
    if not isinstance(forms, list) or len(forms) > 1:
        raise ValueError("Only the selected custom paper form can be transferred")
    for form in forms:
        if (
            set(form) != {"Name", "Flags", "Size", "ImageableArea"}
            or not isinstance(form["Name"], str)
            or len(form["Name"]) > 100
        ):
            raise ValueError("Invalid custom paper form")
        if form["Size"] != {"cx": 107000, "cy": 24000}:
            raise ValueError("Custom paper form does not match 107 x 24 mm")
        area = form["ImageableArea"]
        if (
            set(area) != {"left", "top", "right", "bottom"}
            or not all(isinstance(v, int) for v in area.values())
            or not (
                0 <= area["left"] < area["right"] <= 107000
                and 0 <= area["top"] < area["bottom"] <= 24000
            )
        ):
            raise ValueError("Invalid custom paper imageable area")
    return m


def powershell(code, extra_env=None):
    env = dict(os.environ)
    env.update(extra_env or {})
    command = (
        '[Console]::OutputEncoding=[Text.UTF8Encoding]::new(); $ErrorActionPreference="Stop"; '
        + code
    )
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-EncodedCommand",
            base64.b64encode(command.encode("utf-16le")).decode(),
        ],
        env=env,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode:
        raise RuntimeError(
            "Windows printer command failed: " + result.stderr.strip()[-2000:]
        )
    return result.stdout.strip()


def admin_action(operation, folder, printer=""):
    import ctypes

    args = [
        sys.executable,
        "-B",
        "-c",
        "import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_module('scripts.provision_printer',run_name='__main__')",
        str(ROOT),
        operation,
        "--folder",
        str(folder),
    ]
    if printer:
        args += ["--printer", printer]
    result_path = Path(folder).parent / (Path(folder).name + ".result.json")
    if result_path.exists():
        result_path.unlink()
    if ctypes.windll.shell32.IsUserAnAdmin():
        completed = subprocess.run(args, cwd=ROOT)
    else:

        def quote(s):
            return "'" + str(s).replace("'", "''") + "'"

        command = (
            "$ErrorActionPreference='Stop'; $p=Start-Process -Verb RunAs -Wait -PassThru -FilePath "
            + quote(args[0])
            + " -WorkingDirectory "
            + quote(ROOT)
            + " -ArgumentList "
            + quote(subprocess.list2cmdline(args[1:]))
            + "; exit $p.ExitCode"
        )
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", command]
        )
    if not result_path.exists():
        raise RuntimeError(
            "Printer driver action returned no completion report. Approve the Windows administrator prompt or ask your administrator. No security policy was changed."
        )
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result_path.unlink()
    if not result.get("ok"):
        raise RuntimeError(result.get("error", "Driver action failed"))
    if completed.returncode:
        raise RuntimeError("Windows driver action did not exit successfully")
    return result


def matching_printers(driver=None):
    import win32print

    matches = []
    for entry in win32print.EnumPrinters(2 | 4):
        with printer_handle(entry[2]) as h:
            info = win32print.GetPrinter(h, 2)
        if driver:
            match = info["pDriverName"] == driver
        else:
            match = (
                "TSC" in info["pDriverName"].upper()
                and "TE200" in info["pDriverName"].upper()
            )
        if match:
            matches.append(info)
    return matches


class printer_handle:
    def __init__(self, name, admin=False):
        self.name = name
        self.admin = admin

    def __enter__(self):
        import win32print

        self.h = (
            win32print.OpenPrinter(
                self.name,
                {
                    "DesiredAccess": win32print.PRINTER_ACCESS_ADMINISTER
                    | win32print.PRINTER_ACCESS_USE
                },
            )
            if self.admin
            else win32print.OpenPrinter(self.name)
        )
        return self.h

    def __exit__(self, *args):
        import win32print

        win32print.ClosePrinter(self.h)


def driver_info(name):
    import win32print

    found = [
        d
        for d in win32print.EnumPrinterDrivers(None, None, 6)
        if d["Name"] == name and d["Environment"] == "Windows x64"
    ]
    if len(found) != 1:
        raise RuntimeError("Exact TSC x64 printer driver could not be identified")
    return found[0]


def devmode(name, saved=None):
    import ctypes
    from ctypes import wintypes

    api = ctypes.WinDLL("winspool.drv", use_last_error=True)
    doc = api.DocumentPropertiesW
    doc.argtypes = [
        wintypes.HWND,
        wintypes.HANDLE,
        wintypes.LPWSTR,
        ctypes.c_void_p,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    doc.restype = ctypes.c_long

    class PI9(ctypes.Structure):
        _fields_ = [("pDevMode", ctypes.c_void_p)]

    with printer_handle(name) as handle:
        size = doc(None, int(handle), name, None, None, 0)
        if not 220 <= size <= 1024 * 1024:
            raise RuntimeError("Driver did not return a supported DEVMODE size")
        out = ctypes.create_string_buffer(size)
        if saved is None:
            # Prefer the user's actual saved preferences, including vendor-private
            # stock/gap settings, over a driver's factory defaults.
            getter = api.GetPrinterW
            getter.argtypes = [
                wintypes.HANDLE,
                wintypes.DWORD,
                ctypes.c_void_p,
                wintypes.DWORD,
                ctypes.POINTER(wintypes.DWORD),
            ]
            getter.restype = wintypes.BOOL
            needed = wintypes.DWORD()
            getter(int(handle), 9, None, 0, ctypes.byref(needed))
            if 0 < needed.value <= 2 * 1024 * 1024:
                storage = ctypes.create_string_buffer(needed.value)
                if getter(int(handle), 9, storage, needed.value, ctypes.byref(needed)):
                    ptr = PI9.from_buffer(storage).pDevMode
                    if ptr:
                        low = ctypes.addressof(storage)
                        high = low + len(storage)
                        if not low <= ptr <= high - 72:
                            raise RuntimeError("Unsupported printer preference pointer")
                        length, extra = struct.unpack(
                            "<HH", ctypes.string_at(ptr + 68, 4)
                        )
                        if length + extra > high - ptr:
                            raise RuntimeError(
                                "Printer preferences exceed their native buffer"
                            )
                        return check_devmode(ctypes.string_at(ptr, length + extra))
            if doc(None, int(handle), name, out, None, 2) != 1:
                raise RuntimeError("Unable to read the Windows printer preferences")
            data = bytes(out)
            length, extra = struct.unpack_from("<HH", data, 68)
            return check_devmode(data[: length + extra])
        saved = check_devmode(saved)
        if len(saved) != len(devmode(name)):
            raise RuntimeError(
                "Target driver profile size differs; refusing incompatible private settings"
            )
        source = bytearray(saved)
        source[:64] = (
            name.encode("utf-16le")[:62]
            .decode("utf-16le", errors="ignore")
            .encode("utf-16le")
            .ljust(64, b"\0")
        )
        buf = ctypes.create_string_buffer(bytes(source), size)
        if doc(None, int(handle), name, out, buf, 2 | 8) != 1:
            raise RuntimeError("Target driver rejected the exported printer settings")

        info = PI9(ctypes.addressof(out))
        setter = api.SetPrinterW
        setter.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            ctypes.c_void_p,
            wintypes.DWORD,
        ]
        setter.restype = wintypes.BOOL
        if not setter(int(handle), 9, ctypes.byref(info), 0):
            raise ctypes.WinError(ctypes.get_last_error())


def check_page(name, geometry):
    import win32ui, win32con
    from PIL import Image
    from backend.printers import driver_preflight

    dc = win32ui.CreateDC()
    try:
        dc.CreatePrinterDC(name)
        mapping = {
            "dpi_x": win32con.LOGPIXELSX,
            "dpi_y": win32con.LOGPIXELSY,
            "page_width": win32con.HORZRES,
            "page_height": win32con.VERTRES,
            "offset_x": win32con.PHYSICALOFFSETX,
            "offset_y": win32con.PHYSICALOFFSETY,
        }
        caps = {key: dc.GetDeviceCaps(value) for key, value in mapping.items()}
        driver_preflight(
            geometry,
            caps,
            [
                Image.new(
                    "1",
                    (geometry.dots(geometry.backing), geometry.dots(geometry.height)),
                    1,
                )
            ],
        )
        return caps
    finally:
        dc.DeleteDC()


def state_path():
    return Path(os.environ["LOCALAPPDATA"]) / "BarcodeStudio" / "state.sqlite"


def saved_workspace():
    path = state_path()
    if not path.exists():
        return None
    with sqlite3.connect(path) as c:
        if not c.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='settings'"
        ).fetchone():
            return None
        found = c.execute("SELECT value FROM settings WHERE key='queue'").fetchone()
        return Queue.model_validate_json(found[0]) if found else None


def workspace():
    return saved_workspace() or Queue(geometry=DEFAULT_GEOMETRY)


def initialize(printer=None, geometry=DEFAULT_GEOMETRY, replace_profile=False):
    path = state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as c:
        c.execute(
            "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY,value TEXT NOT NULL)"
        )
        old = c.execute("SELECT value FROM settings WHERE key='queue'").fetchone()
        q = Queue.model_validate_json(old[0]) if old else Queue(geometry=geometry)
        if old and replace_profile and q.geometry != geometry:
            raise RuntimeError(
                "Existing workspace has different media settings; it has been preserved. Apply the exported profile in a separate clean Windows account or resolve the existing configuration first."
            )
        if not old:
            c.execute(
                "INSERT INTO settings VALUES (?,?)", ("queue", q.model_dump_json())
            )
        if printer:
            c.execute(
                "INSERT OR REPLACE INTO settings VALUES (?,?)",
                ("printer", json.dumps(printer)),
            )
            # Driver settings were changed on this PC. Never import a hardware claim.
            c.execute("DELETE FROM settings WHERE key='calibration'")
            c.execute(
                "INSERT OR REPLACE INTO settings VALUES (?,?)",
                (
                    "provisioned",
                    json.dumps(
                        {"printer": printer, "physical_verification": "pending"}
                    ),
                ),
            )


def signed_catalogs(folder):
    powershell(
        """$cats=@(Get-ChildItem -LiteralPath $env:BARCODE_DRIVER_FOLDER -Recurse -Filter *.cat); if($cats.Count -eq 0){throw 'No signed driver catalog found'}; foreach($cat in $cats){$sig=Get-AuthenticodeSignature -LiteralPath $cat.FullName; if($sig.Status -ne 'Valid'){throw ('Driver catalog trust validation failed: '+$cat.Name)}}""",
        {"BARCODE_DRIVER_FOLDER": str(folder)},
    )


def export_machine(folder, printer):
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    info = json.loads(
        powershell(
            """$d=Get-Printer -Name $env:BARCODE_PRINTER; $p=Get-PrinterDriver -Name $d.DriverName; $w=@(Get-WindowsDriver -Online | Where-Object {$_.OriginalFileName -eq $p.InfPath}); if($w.Count -ne 1){throw 'Cannot uniquely map the installed driver to its signed OEM INF'}; @{inf=$w[0].Driver; driver_name=$d.DriverName} | ConvertTo-Json -Compress""",
            {"BARCODE_PRINTER": printer},
        )
    )
    if not re.fullmatch(r"oem\d+\.inf", info["inf"], re.I):
        raise RuntimeError(
            "Installed printer is not an exportable third-party OEM driver"
        )
    subprocess.run(
        ["pnputil.exe", "/export-driver", info["inf"], str(folder)], check=True
    )
    signed_catalogs(folder)


def install_machine(folder):
    import win32print

    folder = Path(folder)
    m = load_bundle(folder)
    signed_catalogs(folder / "driver")
    for inf in sorted((folder / "driver").rglob("*.inf")):
        result = subprocess.run(["pnputil.exe", "/add-driver", str(inf), "/install"])
        if result.returncode not in (0, 3010):
            raise RuntimeError(
                "Windows refused driver package installation; signature verification remains enabled"
            )
    powershell(
        """if(-not (Get-PrinterDriver -Name $env:BARCODE_DRIVER -ErrorAction SilentlyContinue)){Add-PrinterDriver -Name $env:BARCODE_DRIVER}; pnputil.exe /scan-devices | Out-Null; if($LASTEXITCODE -ne 0){throw 'Windows device rescan failed'}""",
        {"BARCODE_DRIVER": m["driver_name"]},
    )
    info = driver_info(m["driver_name"])
    if info["DriverVersion"] != m["driver_version"]:
        raise RuntimeError(
            "Installed driver version differs from the captured profile; refusing vendor-private settings"
        )
    # Forms are optional; restore only the source's selected 107 x 24 mm custom form.
    queues = []
    for _ in range(12):
        queues = matching_printers(m["driver_name"])
        if queues:
            break
        time.sleep(3)
    if len(queues) != 1 or not re.fullmatch(r"USB\d+", queues[0]["pPortName"], re.I):
        raise RuntimeError(
            "Driver installed, but Windows has not identified exactly one TE200 USB queue. Connect/power on the TE200 and rerun; no port was guessed."
        )
    for p in queues:
        with printer_handle(p["pPrinterName"], True) as h:
            existing = {f["Name"]: f for f in win32print.EnumForms(h)}
            for form in m.get("forms", []):
                if form["Name"] in existing:
                    if existing[form["Name"]]["Size"] != form["Size"]:
                        raise RuntimeError(
                            "A conflicting paper form exists; it has not been overwritten"
                        )
                else:
                    win32print.AddForm(h, form)


def prepare(setup, output, announce=True):
    import win32print

    q = workspace()
    if q.geometry.errors():
        raise RuntimeError(
            "The working app still has invalid geometry. Save the successfully tested profile before exporting."
        )
    geometry = q.geometry
    for key in (
        "backing",
        "width",
        "height",
        "columns",
        "gap_x",
        "gap_y",
        "left",
        "right",
        "safe",
        "dpi",
    ):
        if getattr(geometry, key) != getattr(DEFAULT_GEOMETRY, key):
            raise RuntimeError(
                "Save the confirmed 107 mm roll / 33 x 24 mm / 2 mm gap-and-margin settings before exporting."
            )
    candidates = matching_printers()
    selected = None
    path = state_path()
    if path.exists():
        with sqlite3.connect(path) as c:
            r = c.execute("SELECT value FROM settings WHERE key='printer'").fetchone()
            if r:
                selected = json.loads(r[0])
    if selected:
        candidates = [p for p in candidates if p["pPrinterName"] == selected]
    if len(candidates) != 1:
        raise RuntimeError(
            "Exactly one selected TSC TE200 is required. Select your working printer in the app and retry."
        )
    printer = candidates[0]
    name = printer["pPrinterName"]
    if not re.fullmatch(r"USB\d+", printer["pPortName"], re.I):
        raise RuntimeError("Select the working USB-connected TE200 before exporting")
    d = driver_info(printer["pDriverName"])
    caps = check_page(name, geometry)
    binary = devmode(name)
    form_name = binary[102:166].decode("utf-16le").split("\0", 1)[0]
    with printer_handle(name) as h:
        forms = [
            f
            for f in win32print.EnumForms(h)
            if f["Name"] == form_name and f["Size"] == {"cx": 107000, "cy": 24000}
        ]
    for form in forms:
        form["Flags"] = 0  # Recreate a selected custom form as FORM_USER.
    with tempfile.TemporaryDirectory(prefix="BarcodePrinterExport-") as temp:
        bundle = Path(temp) / "PrinterBundle"
        bundle.mkdir()
        (bundle / "devmode.bin").write_bytes(binary)
        admin_action("export-machine", bundle / "driver", name)
        files = {
            p.relative_to(bundle).as_posix(): digest(p)
            for p in sorted(bundle.rglob("*"))
            if p.is_file()
        }
        manifest = {
            "schema": 1,
            "environment": d["Environment"],
            "driver_name": d["Name"],
            "driver_version": d["DriverVersion"],
            "geometry": geometry.model_dump(),
            "caps": caps,
            "forms": forms,
            "files": files,
        }
        (bundle / "profile.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        load_bundle(bundle)
        cmd = (
            Path(setup)
            .read_bytes()
            .replace(
                b'set "BARCODE_SETUP_MODE=prepare"',
                b'set "BARCODE_SETUP_MODE=install"',
                1,
            )
        )
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        # Create a new file; never silently overwrite an earlier working export.
        with zipfile.ZipFile(output, "x", zipfile.ZIP_DEFLATED) as z:
            z.writestr("Setup-Barcode-Studio.cmd", cmd)
            for p in sorted(bundle.rglob("*")):
                if p.is_file():
                    z.write(p, Path("PrinterBundle") / p.relative_to(bundle))
        with zipfile.ZipFile(output) as z:
            if z.testzip() is not None:
                raise RuntimeError("Deployment archive failed integrity verification")
    if announce:
        print("FULL NEW-PC SETUP CREATED:", output)
        print(
            "This file contains the installed signed TSC driver and printer settings. Keep it private; do not upload it to GitHub."
        )
    return str(output)


def restore(folder):
    folder = Path(folder)
    m = load_bundle(folder)
    geometry = Geometry.model_validate(m["geometry"])
    # Check existing workspace before installing or changing printer defaults.
    q = saved_workspace()
    if q is not None and q.geometry != geometry:
        raise RuntimeError(
            "Existing workspace has different media settings; nothing has been changed"
        )
    admin_action("install-machine", folder)
    found = []
    for _ in range(12):
        found = matching_printers(m["driver_name"])
        if found:
            break
        time.sleep(3)
    if len(found) != 1:
        raise RuntimeError(
            "Driver installed, but one connected TE200 USB queue could not be identified. Connect/power on the TE200, wait for Windows detection, and rerun setup. No USB001 port or Epson queue was guessed."
        )
    target = found[0]
    if not re.fullmatch(r"USB\d+", target["pPortName"], re.I):
        raise RuntimeError(
            "Detected queue is not a USB printer; automatic USB setup was not applied"
        )
    if driver_info(m["driver_name"])["DriverVersion"] != m["driver_version"]:
        raise RuntimeError("Target driver version changed; profile was not applied")
    devmode(target["pPrinterName"], (folder / "devmode.bin").read_bytes())
    check_page(target["pPrinterName"], geometry)
    initialize(target["pPrinterName"], geometry, replace_profile=True)
    print(
        "Driver, exact user printing preferences and app geometry configured. Physical verification is pending on this PC."
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "operation",
        choices=[
            "initialize",
            "prepare",
            "restore",
            "export-machine",
            "install-machine",
            "install-online",
        ],
    )
    parser.add_argument("--folder", type=Path)
    parser.add_argument("--printer", default="")
    parser.add_argument("--setup", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if os.name != "nt":
        raise RuntimeError("Printer provisioning requires Windows x64")
    elevated = args.operation in ("export-machine", "install-machine", "install-online")
    try:
        if args.operation == "initialize":
            initialize()
        elif args.operation == "prepare":
            prepare(args.setup, args.output)
        elif args.operation == "restore":
            restore(args.folder)
        elif args.operation == "export-machine":
            export_machine(args.folder, args.printer)
        elif args.operation == "install-machine":
            install_machine(args.folder)
        elif args.operation == "install-online":
            from scripts.online_printer import install_updates
            install_updates(args.folder)
        if elevated:
            report = args.folder.parent / (args.folder.name + ".result.json")
            report.write_text(json.dumps({"ok": True}), encoding="utf-8")
    except Exception as exc:
        if elevated:
            report = args.folder.parent / (args.folder.name + ".result.json")
            report.write_text(
                json.dumps({"ok": False, "error": str(exc)}), encoding="utf-8"
            )
        raise


if __name__ == "__main__":
    main()
