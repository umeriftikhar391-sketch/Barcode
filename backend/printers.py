import os
from .render import raster_row, tspl
from .layout import rows


class PrinterPreflightError(ValueError):
    """A known configuration problem detected before submitting any document."""


def driver_preflight(g, caps, images):
    issues = []
    if (caps["dpi_x"], caps["dpi_y"]) != (g.dpi, g.dpi):
        issues.append(
            f"Driver resolution is {caps['dpi_x']} x {caps['dpi_y']} DPI; select 203 DPI. Automatic scaling is disabled."
        )
    if any(
        im.width > caps["page_width"] or im.height > caps["page_height"]
        for im in images
    ):
        needed_w = max(im.width for im in images)
        needed_h = max(im.height for im in images)
        issues.append(
            f"Driver printable page is {caps['page_width']} x {caps['page_height']} dots; this row requires {needed_w} x {needed_h}. Enter exact stock width {g.backing:g} mm and label height {g.height:g} mm (avoid rounded inch values), select that stock and Apply settings."
        )
    if caps["offset_x"] or caps["offset_y"]:
        issues.append(
            f"Driver adds offsets of {caps['offset_x']} horizontal and {caps['offset_y']} vertical dots. Set driver Exposed Liner Widths Left/Right to 0 and driver print offsets to 0. Keep the physical side margins in the app; its raster already includes them."
        )
    if issues:
        raise PrinterPreflightError(" ".join(issues))


def discover():
    if os.name != "nt":
        return []
    import win32print

    return [{"name": p[2], "description": p[1]} for p in win32print.EnumPrinters(2 | 4)]


def submit(queue, printer, mode):
    if os.name != "nt":
        raise PrinterPreflightError(
            "Physical printing requires Windows and the installed TSC driver"
        )
    if printer not in [p["name"] for p in discover()]:
        raise PrinterPreflightError("Selected printer is unavailable")
    if not ("TSC" in printer.upper() or "TE200" in printer.upper()):
        raise PrinterPreflightError(
            "Select a TSC label printer; Epson receipt printers are not supported"
        )
    import win32print

    if mode == "raw":
        payload = tspl(queue)
        handle = win32print.OpenPrinter(printer)
        try:
            job = win32print.StartDocPrinter(handle, 1, ("Barcode Studio", None, "RAW"))
            try:
                win32print.StartPagePrinter(handle)
                written = win32print.WritePrinter(handle, payload)
                if written != len(payload):
                    raise ValueError(
                        "Partial spooler write: inspect output before any retry"
                    )
                win32print.EndPagePrinter(handle)
            finally:
                win32print.EndDocPrinter(handle)
            return job
        finally:
            win32print.ClosePrinter(handle)
    if mode != "driver":
        raise PrinterPreflightError("Choose driver or raw printing")
    import win32ui, win32con
    from PIL import ImageWin

    dc = win32ui.CreateDC()
    started = False
    try:
        dc.CreatePrinterDC(printer)
        g = queue.geometry
        caps = {
            "dpi_x": dc.GetDeviceCaps(win32con.LOGPIXELSX),
            "dpi_y": dc.GetDeviceCaps(win32con.LOGPIXELSY),
            "page_width": dc.GetDeviceCaps(win32con.HORZRES),
            "page_height": dc.GetDeviceCaps(win32con.VERTRES),
            "offset_x": dc.GetDeviceCaps(win32con.PHYSICALOFFSETX),
            "offset_y": dc.GetDeviceCaps(win32con.PHYSICALOFFSETY),
        }
        images = [raster_row(r, g, True) for r in rows(queue.products)]
        driver_preflight(g, caps, images)
        job = dc.StartDoc("Barcode Studio")
        started = True
        for im in images:
            dc.StartPage()
            ImageWin.Dib(im.convert("RGB")).draw(
                dc.GetHandleOutput(), (0, 0, im.width, im.height)
            )
            dc.EndPage()
        dc.EndDoc()
        started = False
        return job
    except Exception:
        if started:
            try:
                dc.AbortDoc()
            except Exception:
                pass  # Preserve the original failure; physical outcome is uncertain.
        raise
    finally:
        dc.DeleteDC()


def cancel(printer, job):
    if os.name != "nt":
        raise ValueError("Windows spooler unavailable")
    import win32print

    h = win32print.OpenPrinter(printer)
    try:
        win32print.SetJob(h, job, 0, None, win32print.JOB_CONTROL_CANCEL)
    finally:
        win32print.ClosePrinter(h)
