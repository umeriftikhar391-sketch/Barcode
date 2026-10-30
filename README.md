# Barcode Studio

Local Windows-compatible three-column label application for TSC TE200. React/TypeScript frontend, Python/FastAPI local service. Manual products, CSV/XLSX/XLS imports, one persistent queue, exact quantities, Code 128, shared raster preview/print rendering, symbol-only currency changes, read-only Odoo JSON-2, Windows printer discovery and GDI/RAW submission modules.

**This is software-tested development code, not a production-certified printer release.** Your stated media dimensions total **113 mm**, exceeding the **107 mm backing** and **108 mm printable width**. Defaults are preserved. Production remains locked until corrected measured geometry and actual hardware calibration are recorded. A preview is not proof that a barcode will scan.

## No Internet at either stage

Download [Export-Without-Internet.zip](https://github.com/umeriftikhar391-sketch/Barcode/raw/refs/heads/main/downloads/Export-Without-Internet.zip) once (or transfer it by USB). On the working PC, extract both files and run **Export-Without-Internet.cmd**. It uses the already installed Python/dependencies and working TE200 driver, with no downloads or pip operation. Select the working **Start-Barcode.cmd** if prompted and approve driver export.

It creates **Barcode-NO-INTERNET-Setup-<date-time>.zip** on your Desktop. Copy that complete ZIP by USB to a new Windows x64 PC, extract it and run **Install-Barcode-OFFLINE.cmd**. Python and dependencies are included privately, so neither stage needs Internet or a global Python install on the target. Windows driver approval and physical verification remain required. See [zero-Internet setup and verification limits](docs/ZERO-INTERNET-SETUP.md). Native Windows relocation and deployment remain unverified here; the exporter tests its private runtime before producing the final ZIP.

## Offline installer

On your working Windows PC with Internet, download [Prepare-Offline-PC-Setup.zip](https://github.com/umeriftikhar391-sketch/Barcode/raw/refs/heads/main/downloads/Prepare-Offline-PC-Setup.zip), extract and run **Prepare-Offline-PC-Setup.cmd**. It creates **Barcode-OFFLINE-PC-Setup-<date-time>.zip** on your Desktop, including the full Python installer, all dependency wheels with locked hashes, the built app, and your working driver/media profile.

Copy that complete ZIP to a new Windows x64 PC, extract it and run **Setup-Barcode-Studio.cmd**. Destination setup uses bundled files only, with no Internet fallback. Windows driver approval and physical verification still apply. See [offline setup instructions and verification limits](docs/OFFLINE-SETUP.md). The creator requires Internet once; the finished Desktop ZIP is the offline installer. Native new-PC Windows offline installation remains unverified here.

## Final setup including the working TSC driver

On the PC where the TE200 now prints correctly, download [Prepare-Full-PC-Setup.zip](https://github.com/umeriftikhar391-sketch/Barcode/raw/refs/heads/main/downloads/Prepare-Full-PC-Setup.zip), extract it and run **Prepare-Full-PC-Setup.cmd**. It creates **Barcode-Full-PC-Setup-<date-time>.zip** on your Desktop with the installed signed TSC driver and exact tested printer/media preferences.

Copy that single ZIP to a new Windows x64 PC, extract the entire ZIP, connect/power on the TE200, and run **Setup-Barcode-Studio.cmd**. It installs/reuses Python, downloads the verified app/dependencies, installs the captured driver with Windows approval, restores the printer settings, seeds the 107 mm / 33 x 24 mm / 2 mm media profile, and creates the desktop shortcut. No dimensions or setup commands need typing. The physical verification checklist is still required on the new PC; an installer cannot certify sensor calibration or printed alignment. See [matched-PC setup instructions and verification limits](docs/MATCHED-PC-SETUP.md).

The [ordinary app-only setup](https://github.com/umeriftikhar391-sketch/Barcode/raw/refs/heads/main/downloads/Barcode-One-Click-Setup.zip) is also available. Without a captured PrinterBundle, it installs the app/Python and confirmed media profile but does not claim the driver was installed. No unverified driver URL or installer is used. Internet and Windows administrator approval for driver actions are required. Native deployment still needs real Windows verification.

## Install on Windows 10/11 x64

1. Download this project to a normal folder. Install official Python **3.12 x64** (include the Python launcher), and Node.js **22 LTS or newer** from their official publishers. Internet is required for first installation.
2. In the project folder, right-click/open PowerShell and run `powershell -File .\Install-Windows.ps1`. This creates a private Python environment, installs dependencies, and builds the interface. Do not disable organizational execution policies; ask your administrator if blocked.
3. Double-click **Start-Barcode.cmd**. Leave its console open. The local application opens in your browser; close the console to stop the service. The launcher binds only to loopback. It does not need paid hosting or a subscription. Do not expose port 8765 through a router or tunnel.
4. For a source ZIP that already contains `frontend/dist`, Node is optional: the installer reuses the included build. Dependencies still require Python installation unless you build the standalone executable described below.
5. Install the separately verified official TSC driver and complete [printer setup and calibration](docs/PRINTER.md). Never install the uploaded driver just because its filename looks correct.

No Windows installer or executable has been built or signed in this Linux environment. `Build-Windows.ps1` and `barcode-studio.spec` provide a reproducible standalone build recipe for a Windows developer. The resulting artifact must be tested on both Windows versions before distribution.

## Daily operation

1. Open Start-Barcode.cmd. In **Manual entry**, enter the full product name, exact barcode, numeric price, printed symbol, and desired label count. Save to queue. Edit, copy, remove, reorder or adjust quantities in **Print queue**.
2. In **CSV / Excel import**, choose the local file and worksheet. Review the detected header row and every mapping. Choose whether the mapped quantity is truly label quantity, or explicitly apply a label count while ignoring inventory. Review numeric barcode cells for lost leading zeros. Select a decimal convention, validate, inspect errors and append valid products or confirm queue replacement. Fix source errors and re-import; edit accepted products in the queue. No stock count becomes label quantity silently.
3. Symbols are searchable/typeable. Changing a symbol never changes the Decimal amount. Apply to selected queue products or explicitly to all. Confirm that this does not misrepresent the selling price.
4. Save/export unfinished queues to JSON or rely on automatic local persistence. Reopen JSON through the schema-validated queue loader. Keep copies if switching computers. Each product keeps its own identifier and order; identical-looking items are never automatically merged.
5. In **Odoo products**, configure your SaaS HTTPS address, database and API key securely through the backend on Windows. Test/search, review Sales Price and currency, enter an explicit label quantity, and add variants. Connection loss does not prevent offline work. Pricelist pricing is intentionally unavailable until verified for the actual database; see [Odoo guide](docs/ODOO.md).
6. Open **Print preview** to inspect every physical row, eight rows at a time. Content-fit failures are displayed instead of truncating names/barcodes. For longer codes on 33 mm stickers, see the [offline update and narrow-bar scan test](docs/EXCEL-BARCODE-WIDTH.md). Narrow bars require explicit selection and fresh physical verification; wider labels or a suitable higher-resolution printer are needed if scanning is unreliable.
7. Select **Printer settings**, choose TE200, select driver or direct mode, enter corrected physical measurements, and perform the approved seven-label test and every manual calibration check. The test requires valid geometry, explicit approval and, for direct mode, official command verification.
8. Record completed calibration only after the physical tests pass, then submit the exact requested count. Spooler acceptance is not physical success. Inspect paper before any retry. An unchanged job identifier cannot be submitted twice. Use **Prepare new independent job** only when you intentionally want another copy; every generated job starts LEFT and uses complete physical rows.

Queues/settings/history are stored in `.local/state.sqlite` on Linux and `%LOCALAPPDATA%/BarcodeStudio/state.sqlite` on Windows. Odoo keys use Windows Credential Manager, never queue files or browser storage. Delete/remove credentials in Odoo settings when no longer needed.

## Development and validation

Use the existing checkout; a cloud task is already isolated and does not need a new worktree.

```sh
cd /workspace/Barcode
bash scripts/setup-cloud.sh
.venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 8765 --no-access-log
```

The server serves the built React app. Restart it after backend changes. Do not use multiple workers (session capabilities are per process). After frontend changes run `npm run build --prefix frontend`.

```sh
.venv/bin/python -m pytest -q
npm run build --prefix frontend
# Optional real-browser smoke, while the local server is running:
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python scripts/browser_smoke.py
```

Browser smoke uses `/usr/bin/chromium` on Linux, preserves/restores the queue and blocks external requests. It verifies manual entry, three-row preview, reload persistence and the actual supplied workbook. Update the executable path to your installed Chromium when using other systems.

Architecture: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). Attachment evidence: [docs/ATTACHMENTS.md](docs/ATTACHMENTS.md). Verification and remaining acceptance work: [docs/STATUS.md](docs/STATUS.md). Core tests do not require credentials, Windows or hardware. No real Odoo writes or physical printer tests were performed.
