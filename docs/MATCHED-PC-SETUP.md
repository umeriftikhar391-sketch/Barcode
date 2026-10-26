# Final reusable setup with the working TE200 driver and settings

## Create the final file once, on the PC where printing works

1. Leave the working TSC TE200 connected by USB and powered on. Save the tested app settings: 107 mm backing; three 33 x 24 mm stickers; 2 mm horizontal/vertical gaps; 2 mm side and internal safe margins. Select the working printer in the application. Existing printer settings and calibration are not changed by capture.
2. Download `downloads/Prepare-Full-PC-Setup.zip` from this repository, extract it, and double-click **Prepare-Full-PC-Setup.cmd** as your normal Windows user. It installs/reuses the app's Python environment automatically; no typed commands or Node.js are needed.
3. Approve the Windows administrator prompt for the signed driver export. The source must be the working USB-connected TSC TE200. Multiple/ambiguous printer queues, a non-USB printer, unsupported geometry or non-exportable driver stops the operation with an error instead of guessing.
4. When it finishes, it selects **Barcode-Full-PC-Setup-<date-time>.zip** on your Desktop. **That is the final reusable file for your new PCs.** Keep the complete ZIP. The source-driver catalog must validate through Windows; no unverified uploaded installer is run.

## Use that single ZIP on a new PC

1. Use Windows 10/11 x64. Connect/power on the TE200 by USB, extract the whole ZIP, and double-click **Setup-Barcode-Studio.cmd**. Keep the accompanying `PrinterBundle` folder beside the CMD file.
2. Approve Windows administrator access for driver installation. Setup automatically finds or installs verified Python 3.12 x64, downloads/verifies the pinned application, installs dependencies, imports the captured signed driver using Windows PnPUtil, waits for Windows to identify the TE200 USB queue, restores that driver's exact per-user printing preferences and any selected custom 107 x 24 mm paper form, saves the app's measured media profile, creates a desktop shortcut and opens the application.
3. No media dimensions need retyping. It does not assume `USB001`, set the system default printer, change an Epson queue, install an unsigned driver, disable security policy or copy Odoo keys/queues. If Windows has not identified exactly one matching USB queue, it stops with instructions to connect the printer and retry. Unknown/incompatible driver versions and conflicting existing workspace geometry are preserved and reported.
4. Complete the physical verification in the app on the new PC. The profile transfers software preferences, **not proof that this PC/driver/loaded roll feeds and prints correctly**. Run the approved calibration sample, inspect margins/prices, scan barcodes, and verify fresh-row behavior on a second independent job. Then record the verified checklist. Calibration confirmation is intentionally not imported or manufactured.

## What is included, downloaded, and retained

* The final local ZIP contains the installed TSC driver INF/catalog/files, its vendor DEVMODE preferences, selected custom form (if any), app geometry and the verified-download setup CMD. It can contain proprietary vendor files and device settings; use within your authorized deployment and **keep it private**. The source-specific driver/profile bundle is never uploaded to GitHub by this project.
* Python is downloaded from python.org only if a compatible x64 3.12 installation is absent. Windows Authenticode and publisher are checked before installation. The application comes from its pinned GitHub commit and is verified with an embedded SHA256. Python packages come from the normal verified package sources. First installation requires Internet.
* The driver is bundled from your successful installation. Manufacturer/driver-publisher sites returned network-policy HTTP 403 during development, so there is **no fabricated universal driver URL or guessed silent installer command**. Driver extraction uses `pnputil /export-driver`, and destination installation uses `pnputil /add-driver /install` with Windows signature enforcement. Windows administrator approval remains necessary.
* Per-PC queues and settings remain in `%LOCALAPPDATA%\BarcodeStudio\state.sqlite`. Installation files use separate version directories. Capture does not include that database, print history, credentials or physical calibration claims. Existing queue products are not discarded. Destination driver-profile application invalidates any earlier local calibration because it changes driver settings.
* Device-side gap sensor calibration, mechanical guide positioning and scanner/physical output verification cannot be guaranteed by a PC installer. No undocumented sensor commands or blind feed/print operations are sent. If your printer itself needs sensor calibration, follow the official TSC procedure.

## Verification limits

Automated tests cover bundle checksums/path/size protection, matching confirmed geometry, profile-header validation, credential/state exclusions, preserved existing queues, calibration invalidation, exact target selection and refusal to guess a USB port. Mocked transfer tests are not a real Windows driver transfer. Embedded PowerShell syntax is parsed separately.

Windows driver export/import, UAC, USB PnP discovery, vendor-private DEVMODE transfer/custom forms, catalog trust validation and full fresh-PC installation require real Windows verification. The existing application's GDI print workflow has been reported successful by the user; the new deployment feature has not yet been exercised on the user's Windows PC. Do not describe the final package as physically calibrated or universally unattended until those tests have been performed.

Failures remain visible in the setup window and `%LOCALAPPDATA%\BarcodeStudio\setup-*.log`. A source export failing to map its published OEM INF is a concrete driver compatibility issue to diagnose. Do not bypass signature checks or silently substitute another printer to complete setup.
