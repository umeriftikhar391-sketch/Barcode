"""Check/reuse TE200 queues; ask Windows Update for exact connected hardware only."""

import os
from pathlib import Path
import re
import tempfile
import time
from scripts import provision_printer as printer


def te200_queues(discover=None):
    if discover is None:
        import win32print

        discover = lambda: win32print.EnumPrinters(2 | 4)
    return [p[2] for p in discover() if re.search(r"\bTE200\b", p[2], re.I)]


def install_updates(folder):
    printer.powershell(
        "& ([scriptblock]::Create([IO.File]::ReadAllText($env:BARCODE_DRIVER_UPDATE_SCRIPT)))",
        {
            "BARCODE_DRIVER_UPDATE_SCRIPT": str(
                Path(__file__).with_name("Install-Printer-Online.ps1")
            )
        },
    )


def configure_standard_page(name, geometry):
    import win32con
    import win32print

    with printer.printer_handle(name) as handle:
        dm = win32print.GetPrinter(handle, 2)["pDevMode"]
        dm.PaperSize = 256  # DMPAPER_USER; lengths are tenths of a millimetre.
        dm.PaperWidth = round(geometry.backing * 10)
        dm.PaperLength = round(geometry.height * 10)
        dm.FormName = ""
        dm.Fields &= ~win32con.DM_FORMNAME
        dm.Orientation = win32con.DMORIENT_PORTRAIT
        dm.Copies = 1
        dm.Scale = 100
        dm.Fields |= (
            win32con.DM_PAPERSIZE
            | win32con.DM_PAPERWIDTH
            | win32con.DM_PAPERLENGTH
            | win32con.DM_ORIENTATION
            | win32con.DM_COPIES
            | win32con.DM_SCALE
        )
        result = win32print.DocumentProperties(
            0, handle, name, dm, dm, win32con.DM_IN_BUFFER | win32con.DM_OUT_BUFFER
        )
        if result != 1:
            raise RuntimeError(
                "The driver could not validate the 107 x 24 mm row settings."
            )
        win32print.SetPrinter(handle, 9, {"pDevMode": dm}, 0)
    printer.check_page(name, geometry)


def ensure():
    if os.name != "nt":
        raise RuntimeError("Printer installation requires Windows")
    printer.initialize()
    queues = te200_queues()
    if not queues:
        print(
            "Checking Windows Update for the connected TE200 driver. Approve the Windows prompt...",
            flush=True,
        )
        try:
            with tempfile.TemporaryDirectory(prefix="BarcodeDriverUpdate-") as temp:
                printer.admin_action("install-online", Path(temp))
            for _ in range(15):
                queues = te200_queues()
                if queues:
                    break
                time.sleep(2)
        except Exception as exc:
            print("PRINTER PENDING: " + str(exc), flush=True)
            return False
    if len(queues) != 1:
        print(
            "PRINTER PENDING: Connect one TE200 and rerun Setup. No USB port or printer was guessed.",
            flush=True,
        )
        return False
    name = queues[0]
    geometry = printer.workspace().geometry
    try:
        try:
            printer.check_page(name, geometry)
        except Exception:
            configure_standard_page(name, geometry)
        printer.initialize(name, geometry)
    except Exception as exc:
        print(
            "PRINTER PENDING: Driver detected for " + name + ". " + str(exc), flush=True
        )
        return False
    print("TSC TE200 driver and row settings are ready: " + name, flush=True)
    return True


if __name__ == "__main__":
    ensure()
