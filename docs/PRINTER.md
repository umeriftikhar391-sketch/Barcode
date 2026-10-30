# TSC TE200 setup and physical acceptance

The checklist below is optional in the current app and does not lock printing.
See [automatic fitting and exception labels](EXCEL-BARCODE-WIDTH.md). The confirmed
stock is 33 × 24 mm, three columns on 107 mm backing with 2 mm gaps/margins.
The 113/107 contradiction in historical instructions below has been resolved.

**Production is not verified.** Never use the Epson receipt/preparation printer. Linux cannot detect the user's USB Windows printer. No driver installer is bundled or automatically executed.

1. On Windows 10/11 x64 obtain the TE200-compatible driver and user/programming manual from TSC's official support site. Verify package provenance, hash where officially published, publisher signature and compatibility. For the attached installer, first extract without running and inspect `Get-AuthenticodeSignature .\TSC_12.4.0.exe`. Do not accept unsigned/untrusted results or disable verification to install it.
2. Install per TSC instructions, attach USB, load media with correct guides and direct thermal or ribbon mode. Use Windows printer properties to identify TE200 separately from Epson.
3. Measure the die cuts and backing with a ruler/caliper. Resolve the 113/107 mm contradiction. Record actual label width/height, gaps and margins in Advanced media geometry; changing them invalidates the calibration fingerprint. A valid mathematical profile is not yet production ready. Do not use the 33 mm width used in automated tests as a measurement of your stock.
4. Configure gap media, one complete three-label row per driver page and correct 203 DPI. Disable fit-to-page, scaling and driver copies. Set speed/density conservatively. Gap-sensor calibration must follow the TE200 manual or official utility; this application does not send an unverified sensor calibration command. Do not experiment with undocumented button sequences.
5. Check the TSPL-EZD model manual for SIZE, GAP, DIRECTION, REFERENCE, SPEED, DENSITY, CLS, BITMAP and PRINT command semantics, bitmap polarity, feed pitch and origin. Direct mode remains experimental until checked on your firmware. Its emitted row-level jobs use one PRINT 1,1 for each complete physical row, never one copy count per product.
6. Perform the explicitly approved calibration sample from Printer settings only after geometry is valid and official command semantics have been checked for direct mode. It sends seven sample labels over three rows, leaving two positions blank on the last row. Keep people clear of moving media. Submission does not prove physical success.
7. Inspect all three columns: horizontal alignment, left/right quiet zones, text, prices and safe margins. Measure first and later rows for vertical drift. Scan each barcode and compare exact digits/case/leading zeros. Adjust horizontal/top offsets only in small measured increments. Repeat calibration after every setting change.
8. Count physical output for 1, 2, 3, 4, 5, 7 and mixed-product jobs. Scan the last partially used row. Then submit a NEW independent one-label job and verify LEFT starts on a fresh row, never in the unused positions. Confirm gap feeding and no extra marks/duplicates. Run the same checks independently for driver and raw methods.
9. Confirm measured geometry, alignment, barcode scanning, consecutive rows, independent-job boundaries and physical counts in the checklist. Record calibration only when these tests actually pass. A record represents the operator's evidence; the software cannot inspect paper.
10. Test USB disconnection, media-out, cancellation, and reconnect. Inspect spooler and physical labels before any retry. Windows acceptance is reported as **Physical Confirmation Pending**, not Printed. Cancellation cannot recall output. Automatic retries are disabled.

Troubleshooting: wandering columns suggest guide tension or incorrect die-cut pitch; progressive vertical drift suggests sensor/media-gap settings; pale/dense bars suggest media/ribbon or density/speed; clipped text indicates unsafe geometry or driver margins; wrong row origin indicates driver page pitch or feed calibration. Stop production, resolve the cause, and repeat physical acceptance. Do not compensate by shrinking barcode modules below the minimum.

Windows 10/11, GDI driver behavior, TSPL polarity/feeding, actual USB communication, scanner readability and printer faults are hardware-dependent and remain untested here.

## Confirmed revised roll and GDI stock settings

The user's latest dimension drawing supersedes earlier values: backing 107 mm, three labels each 33 x 24 mm, 2 mm horizontal/vertical gaps, 2 mm left/right margins. Retain the separately requested 2 mm internal safe inset. Horizontal total is 107 mm; row pitch is 26 mm. Start app print offsets/origin at zero, then calibrate physically.

For this application's full-row GDI raster, create one driver stock page of **107 mm wide x 24 mm high**, Die-Cut, Portrait. Enter exact measurements, not an approximation of 0.94 inches for height: that is only 23.876 mm and may result in a driver page one dot shorter than the renderer requires. If the fields accept explicit units, type `107 mm` and `24 mm`; otherwise use 4.2126 in and 0.9449 in. A rounded display alone does not prove the internally stored value was rounded.

Set the driver's **Exposed Liner Widths Left/Right to zero** for the full-row raster. The application's two side margins remain 2 mm; adding driver liner offsets double-applies placement and may introduce hardware margins that the strict GDI preflight refuses. Save/select the stock and Apply/OK all preferences before the app creates a new print context. Set the vertical gap/sensor options separately according to the driver controls and TSC manual. Inspect the Windows queue and any physical output before sending another approved calibration sample.

Known preflight failures now display the actual driver DPI, printable dot dimensions and offsets, with corrective instructions. These are distinguished from an uncertain failure after submission may have begun. Driver behavior remains Windows/hardware-dependent; a screenshot alone cannot establish the exact reported device capabilities or whether the stock dimensions were stored precisely.
