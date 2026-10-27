# No Internet for creation or installation

This is different from the earlier online package creators. It copies the Python runtime and application dependencies already installed on the PC where printing works. It does not use pip, download a Python installer, resolve packages online or contact GitHub while exporting or installing. It creates a private, app-local runtime; no global Python installation is required on the destination.

## On the working Windows PC

1. Obtain **Export-Without-Internet.zip** once (you can transfer it to the disconnected PC by USB from another device). Extract **both** `Export-Without-Internet.cmd` and `Application.zip` together.
2. Keep the working TSC TE200 powered on and connected. Your existing Barcode Studio installation must work with Windows CPython 3.12 x64 and its installed dependencies.
3. Double-click **Export-Without-Internet.cmd**. It checks the bundled application's checksum. If a Barcode Studio desktop shortcut identifies the existing environment, it uses it. Otherwise a file picker asks you to select **Start-Barcode.cmd** from your working app folder. No commands or measurements need typing.
4. Approve Windows administrator access for driver export. The exporter copies a curated application, the installed signed Python runtime/standard library and only the dependency graph required by this application. Installed library files are checked against their package records; caches, unrelated packages, product queues and credentials are excluded. Licenses and distribution metadata are retained. No bare virtual environment is copied.
5. The private runtime uses `python312._pth` to define only its own libraries and packaged application path, ignoring registry/user-site/environment Python search paths. The exporter tests the relocated interpreter, native imports and label renderer before creating **Barcode-NO-INTERNET-Setup-<date-time>.zip** on your Desktop. A mismatch/missing dependency stops export; it never tries downloading a replacement.

Your current printer preferences and verified calibration record are not changed by capture. The ZIP includes the signed TE200 driver and tested media settings. Keep that private source-specific ZIP for your own deployment; it is not uploaded to GitHub.

## On the new Windows x64 PC

Copy the finished Desktop ZIP by USB, extract the entire ZIP and run **Install-Barcode-OFFLINE.cmd**. Keep `Payload`, `PrinterBundle`, and `manifest.json` beside that CMD. Connect/power on the TE200 and approve the driver prompt.

The installer validates the embedded manifest hash and every payload file before executing the private runtime, checks Python signatures, copies the app/runtime to a version-specific folder under `%LOCALAPPDATA%\BarcodeStudio\portable`, imports the signed driver, restores the exact media preferences and creates a desktop shortcut. Existing unknown folders/files are preserved. It does not require or install pip, Node, an online package index or a system-wide Python. Driver installation uses Windows PnPUtil and does not guess an Epson queue or USB port.

After software installation, print/scan the short physical sample and record the checks in the app. Calibration evidence from another PC is never copied or invented. The profile is the confirmed 107 mm backing, three 33 x 24 mm labels, and 2 mm gaps/side/internal safe margins. Sensor/mechanical adjustment cannot be certified by a PC installer. Odoo access still requires its external service/network; local manual entry, files, queues and preview remain offline.

## Prerequisites and verification limits

* The source must already have a complete working, unmodified, supported CPython 3.12 x64 installation and required packages. It must have enough free disk space for a second copy and archive. Missing/incompatible files are reported rather than fetched from the Internet. Editable/source-only package installations and unverifiable modified code are rejected.
* Both PCs require supported Windows x64 system components. Windows Authenticode and driver-catalog trust remain enabled. An image missing the trust certificates or OS components needed to verify/load these signed binaries requires administrator remediation; this tool does not disable verification or change security policy. Windows itself can attempt its normal certificate checks, but this exporter/installer has no download fallback or package-install operation.
* No Internet is required to run either stage. Receiving the initial exporter file can be done through another device/USB. Windows administrator approval remains necessary for driver actions. Existing workspaces, Odoo credentials and product data are not cloned; the destination's physical calibration remains pending until checked there.
* Tests check dependency/extra/Windows-marker resolution, installed-file hashes, private-file exclusions, complete archive inventory and no overwriting. Actual installed dependency files were copied and successfully imported in an isolated **Linux** process without the original site-packages. Both embedded PowerShell scripts parse successfully. These do not verify Windows CPython relocation, native DLL loading, driver migration, offline certificate validation or a complete new-PC deployment. The exporter explicitly tests relocation on the working Windows PC before creating the final ZIP; new-PC acceptance remains separate.

Logs are under `%LOCALAPPDATA%\BarcodeStudio\offline-export-*.log` and `portable-setup-*.log`. If export stops, keep the window open and share the reported error. Do not disable signature checks, download undocumented replacements or mark an unperformed physical test passed.
