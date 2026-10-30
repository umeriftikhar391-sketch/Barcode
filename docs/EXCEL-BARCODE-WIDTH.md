# Automatic barcode fitting and offline update

The confirmed roll is 107 mm wide, with three 33 × 24 mm stickers, 2 mm
horizontal/vertical gaps, 2 mm side margins and 2 mm internal safe margins.

## Update the working PC

1. Download `downloads/Barcode-Auto-Fit-Update.zip`, or transfer it by USB.
2. Close Barcode Studio's server console window, not just the browser tab.
3. Extract the entire ZIP and run **Update-Barcode.cmd**. If prompted, choose
   **Start-Barcode.cmd** from your working app folder.
4. The app opens with **Automatic fit** enabled. Select your TE200 and print.
   No checklist boxes or calibration record are required.

The updater uses the existing Python installation and printer driver. It requires
no Internet, pip or new dependencies, and preserves products and physical media
dimensions. Previous backend and frontend files are saved under `.update-backups`.
The updater and physical printer still need verification on Windows.

## What is automatic

- Each Code 128 value uses two printer dots per module when it fits, or one dot
  when necessary. Both quiet zones are preserved. There is no fractional-dot
  scaling, clipping, substituted code or change to the underlying value.
- Long product names are fitted across two lines. If necessary, the printed
  display name ends in `...`; its full original remains in the queue and the
  preview warnings explain the adjustment.
- If even one-dot bars cannot fit, a **CHECK LABEL - NO BARCODE** exception label
  prints with the full original barcode value as wrapped text and its price.
  That label contains no scannable barcode. Other products keep printing.
  The requested quantities and positions include exception labels; nothing is
  silently skipped. Preview warnings and print submission details identify them.
- Optional manual standard/narrow modes retain strict fit errors. Automatic fit
  is enabled once on upgrade; a later explicit manual selection is respected.
- The calibration checklist remains available in a collapsed optional section.
  Recording calibration is not a prerequisite for printing.

One-dot bars at 203 DPI are about 0.125 mm wide and can be less reliable on real
scanners. Software cannot guarantee a scannable barcode of arbitrary length on
a fixed-size sticker. Inspect the printed output. If narrow bars are unreliable,
wider labels or a suitable higher-resolution printer are needed.

Actual hardware failures, an unavailable printer, invalid media dimensions and
possibly partial submissions still produce truthful errors. Duplicate-job and
uncertain-print handling remains in place to avoid unintended duplicate labels.
