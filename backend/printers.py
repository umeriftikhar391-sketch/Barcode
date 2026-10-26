import os
from .render import raster_row, tspl
from .layout import rows


def discover():
    if os.name != "nt":
        return []
    import win32print

    return [{"name": p[2], "description": p[1]} for p in win32print.EnumPrinters(2 | 4)]


def submit(queue, printer, mode):
    if os.name != "nt":
        raise ValueError(
            "Physical printing requires Windows and the installed TSC driver"
        )
    if printer not in [p["name"] for p in discover()]:
        raise ValueError("Selected printer is unavailable")
    if not ("TSC" in printer.upper() or "TE200" in printer.upper()):
        raise ValueError(
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
        raise ValueError("Choose driver or raw printing")
    import win32ui, win32con
    from PIL import ImageWin

    dc = win32ui.CreateDC()
    dc.CreatePrinterDC(printer)
    g = queue.geometry
    # Refuse driver scaling or printable areas that cannot preserve native dots.
    if (
        dc.GetDeviceCaps(win32con.LOGPIXELSX),
        dc.GetDeviceCaps(win32con.LOGPIXELSY),
    ) != (g.dpi, g.dpi):
        dc.DeleteDC()
        raise ValueError(
            "Driver DPI must match 203 DPI; automatic scaling is forbidden"
        )
    page_w = dc.GetDeviceCaps(win32con.HORZRES)
    page_h = dc.GetDeviceCaps(win32con.VERTRES)
    physical_x = dc.GetDeviceCaps(win32con.PHYSICALOFFSETX)
    physical_y = dc.GetDeviceCaps(win32con.PHYSICALOFFSETY)
    images = [raster_row(r, g, True) for r in rows(queue.products)]
    if any(im.width > page_w or im.height > page_h for im in images):
        dc.DeleteDC()
        raise ValueError(
            "Driver page is too small; configure one physical row, no scaling"
        )
    if physical_x or physical_y:
        dc.DeleteDC()
        raise ValueError(
            "Driver introduces hardware margins; configure zero-offset media before driver printing"
        )
    try:
        job = dc.StartDoc("Barcode Studio")
        for im in images:
            dc.StartPage()
            ImageWin.Dib(im.convert("RGB")).draw(
                dc.GetHandleOutput(), (0, 0, im.width, im.height)
            )
            dc.EndPage()
        dc.EndDoc()
        return job
    except Exception:
        dc.AbortDoc()
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
