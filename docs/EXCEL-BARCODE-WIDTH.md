# Longer Excel barcodes on 33 × 24 mm stickers

The confirmed roll is 107 mm wide, with three 33 × 24 mm stickers, 2 mm
horizontal/vertical gaps, 2 mm side margins and 2 mm internal safe margins.
At 203 DPI, the safe content area is 232 dots wide. Standard two-dot Code 128
bars, including ten-module quiet zones at both ends, need 264 dots for
`1000459-1` and 286 dots for `1000459-10`. Importing Excel does not cause this
width limit; short calibration numbers fit while these longer values do not.

## Apply the update to a working PC

1. Obtain `downloads/Barcode-Excel-Print-Update.zip` and extract all files.
   It can be transferred to a disconnected PC by USB.
2. Close the Barcode Studio server console window. Closing its browser tab alone
   does not stop the application.
3. Run `Update-Barcode.cmd`. It finds the Desktop shortcut or asks you to select
   your existing `Start-Barcode.cmd`. Select the working installation, not the
   downloaded update folder.
4. The updater verifies the bundled application archive, backs up the existing
   backend and built frontend under `.update-backups`, replaces those two folders,
   and opens the app. Python, printer driver, saved queue and media dimensions are
   preserved. No Internet, pip, new Python installation or administrator approval
   is needed for this application-only update.

## Test narrow bars

1. Open **Printer settings → Barcode bar width** and select
   **Narrow bars · 1 printer dot · scan test required**.
2. Keep all media dimensions and printer preferences at their successfully tested
   values. Changing bar width requires a separate physical calibration confirmation.
3. Print the approved seven-label calibration sample. In narrow mode it includes
   `1000459-10` in all three columns of the first row, then `1000459-1`,
   `1000704-2`, `0001234567` and `1000112-3` across the following rows.
4. Scan every label with the actual production scanner and compare every character,
   including hyphens and leading zeros. Repeat the sample as an independent job
   and check that it starts at the left of a fresh row. Also test the longest real
   product code if your workbook changes.
5. Only after the physical tests pass, check the applicable checklist items and
   record completed physical calibration. For Windows driver/GDI, leave the
   direct-TSPL command confirmation unchecked. Review the Excel preview, then print.

One-dot bars are about 0.125 mm wide at 203 DPI and may be less reliable with
some scanners or print conditions. Digital decoding of a clean raster is not
proof of physical readability. If the actual scanner cannot read these samples
reliably, retain standard bars and use wider labels or a suitable higher-resolution
printer. Values are never shortened, quiet zones are never cropped, and barcodes
that exceed even the narrow-mode width remain blocked.
