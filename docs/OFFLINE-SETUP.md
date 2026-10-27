# Offline installer

## Create it once on the working PC, with Internet

Download `downloads/Prepare-Offline-PC-Setup.zip`, extract it, and double-click **Prepare-Offline-PC-Setup.cmd** on the Windows x64 PC where the TE200 prints correctly. Keep the printer connected/powered on, and select the tested profile in Barcode Studio. Approve Windows administrator access when driver export requests it.

The creator downloads the pinned app archive, the **full** Python 3.12.10 x64 installer and all native Windows Python dependency wheels. It verifies the Python publisher signature, creates an exact SHA256-locked wheel requirements file, tests a fresh virtual environment installation using only those local wheels, and captures the working signed TE200 driver/preferences. It then creates **Barcode-OFFLINE-PC-Setup-<date-time>.zip** on your Desktop.

**That Desktop ZIP is the offline installer.** The small creator download itself needs Internet and is not the finished offline bundle. Build time and output size depend on downloads and the installed driver package. Keep your finished ZIP private; it contains the selected driver's files and settings, not your product queues, Odoo credentials or print history.

## Install on a new PC, without Internet

1. Copy the complete Desktop ZIP to the new Windows 10/11 x64 PC (a USB stick is suitable).
2. Extract the entire ZIP. Keep **OfflinePayload** and **PrinterBundle** beside **Setup-Barcode-Studio.cmd**.
3. Connect/power on the TSC TE200 by USB, then double-click **Setup-Barcode-Studio.cmd** and approve the Windows driver prompt.
4. Setup checks the pinned manifest and every bundled file, installs/reuses Python, extracts the local application, installs dependencies from local wheels only, restores the signed driver and media profile, checks software readiness and creates the desktop shortcut. No Node.js, typed commands, PyPI access or GitHub download is needed on the destination.
5. Print/scan the short physical verification sample and record the completed checks on that PC. A transferred software profile does not prove sensor calibration, feeding, scanner performance or physical alignment on another PC. Odoo features still need their configured network service and credentials; manual entry, local imports, queue and preview work offline.

The copied media profile is the confirmed 107 mm backing, three 33 x 24 mm stickers, 2 mm gaps and side/internal safe margins. Existing different workspace geometry is preserved and reported, not silently overwritten. Installation/driver faults remain visible and prevent a false completion claim.

## Integrity and offline guarantees

* The CMD embeds the manifest SHA256; the manifest binds the full Python installer, app ZIP, every wheel and requirements lock by size/hash. Application SHA256 is also verified against its pinned release independently. Driver files are checked by the printer manifest, signed catalogs and Windows PnPUtil signature enforcement.
* Python dependencies use `--no-index --find-links <local wheelhouse> --require-hashes --only-binary=:all: --no-cache-dir`. Existing pip configuration/environment is removed in the installer process before known offline settings are applied. Direct-URL wheel dependencies are rejected while building; missing/incompatible wheels stop creation rather than creating an incomplete package.
* There is no Internet fallback in destination offline mode. Missing/tampered files stop installation. The whole archive must be copied/extracted, not the CMD alone. Existing setup outputs are never overwritten blindly.
* Windows Authenticode/catalog trust checks remain enabled at both creation and installation. An offline Windows image must already have the certificate trust and operating-system components needed to validate/install the supplied signed packages. Setup does not disable signature/revocation checks or alter organizational policies to compensate for missing trust. An administrator must resolve such a Windows prerequisite if reported. Windows itself may try its normal certificate/device-update mechanisms; setup supplies all app/driver artifacts locally.
* The creator uses the native Windows CPython 3.12 x64 resolver, so its wheelhouse is for that target. ARM64-native, other Python minor versions and old unsupported Windows builds are not supported by this bundle.

## What was tested

Automated tests cover locked compatible wheels, refusal of source distributions/direct URLs, manifest integrity/path/file validation, local installer mode, complete archive assembly and preservation of existing files. Actual fresh dependency installation from a local wheelhouse (with index access disabled), dependency consistency and barcode rendering were executed successfully on **Linux**. PowerShell manifest verification was exercised on Linux and rejected a tampered payload. Those are software checks, not a Windows offline installation or a printer test.

Windows Python installation, offline certificate validation, UAC, driver transfer, vendor profile restoration and a complete new-PC offline run remain Windows-dependent and unverified in this environment. The creator itself performs the local-wheel clean-install/import/render check on the working Windows PC before producing the final ZIP; that still does not replace new-PC/hardware acceptance.
