# Implementation and verification report

Date: 26 October 2026. Status: **offline preparation implemented and software-tested; hardware acceptance pending; not production ready**.

## Implemented and tested

* React/TypeScript application with manual entry, field validation, editing, duplication, removal, reordering, selected/all currency-symbol changes, quantity controls, unified queue and JSON save/reopen. Symbols change presentation only, never Decimal amounts.
* Local CSV, XLSX and XLS parsing, worksheets, header detection, editable proposed column mappings, explicit quantity meaning and numeric-barcode confirmation, decimal convention, row validation, valid-row preview, append/confirmed replace, and CSV/XLSX templates. Actual supplied workbook retained as an integration fixture. No formula or macro execution.
* Barcode type/character validation and python-barcode Code 128 encoding/checksum/subset handling, quiet zones, minimum two-dot modules, complete name/barcode/price rendering, glyph checks and shaping check. Long content rejects unsafe fit instead of shrinking/truncating silently.
* Pure three-column layout; tested quantities 1,2,3,4,5,6,7,8,10,25,50,100, empty queues, and mixed-product transitions. Blank final positions remain white; each job starts LEFT. Same monochrome raster source feeds paginated preview and print modules.
* Original geometry retained; contradiction detected, absolute half-up dot rounding, printable/media/safe-margin and generated raster checks. Invalid and uncalibrated production printing locked in both frontend and backend.
* Loopback-only service, Host/Origin/fetch-site validation, session capability, validated queue boundaries, SQLite persistence, persistent job IDs, no automatic retry after failures, cancellation request API and truthful spooler states.
* Approved seven-label calibration sample generation with explicit confirmation and valid geometry; operator checklist tied to exact geometry, printer and method. This is software functionality, not evidence of physical calibration.

## Implemented boundaries, not hardware/live verified

* Windows printer enumeration, TSC selection, native GDI driver output, raw TSPL BITMAP submission, spooler cancellation and Windows Credential Manager storage. These code paths are not executed by Linux tests. Native GDI uses app printer selection and strict driver-page checks; a Windows system print-dialog UI is not implemented.
* Read-only Odoo JSON-2 client, bounded product search/pagination, variant Sales Price/barcode loading, currency retrieval and accessible pricelist listing; validated SaaS HTTPS addresses, TLS, bearer header, redirect refusal and sanitized errors. Wire format and errors are tested with mocks, not the user's database. Actual model fields/permissions need database `/doc` verification.
* Selected-pricelist calculation deliberately raises a clear blocker until a public authorized pricing operation and context can be verified. It never silently returns standard Sales Price as a pricelist price.
* Windows install/launch scripts and PyInstaller onedir specification/build recipe are supplied. No Windows executable, installer signature, Windows 10/11 run or standalone distribution was verified here. First-time source setup needs Python and, if no built UI is included, Node.

## Commands actually executed

| Check | Result |
|---|---|
| `bash scripts/setup-cloud.sh` | Passed, including repeat installation, frozen npm install, frontend build and backend suite |
| `.venv/bin/python -m pytest -q` | 50 passed; one upstream Starlette/httpx TestClient deprecation warning |
| `npm run build --prefix frontend` | TypeScript check and Vite production build passed |
| `.venv/bin/python scripts/browser_smoke.py` | Real Chromium passed with external requests blocked: manual entry, seven labels/three rows, queue persistence across reload, supplied workbook mapping and numeric-barcode review; no page errors |
| `.venv/bin/ruff check backend tests scripts --select E9,F63,F7,F82` | Passed (fatal/syntax checks only; not a claim of exhaustive linting) |
| `.venv/bin/python -m compileall -q backend scripts` | Passed |
| `.venv/bin/python -m pip check` | Passed |
| Running Uvicorn + functional preview request | Passed through browser and API tests; PNG output generated |
| Actual Windows printing / USB / driver / scanner / Odoo | Not executed; requires external equipment/access |
| Uploaded driver archive integrity/signature | Not executed; file exceeds download tool's 32 MiB transfer limit |

Initial failures were corrected: CSV sniffing with pre-header notes, frontend syntax, test assumptions about Pillow 1-bit pixel values, and a real queue save/reload timing issue. Queue updates now serialize immediately and expose a save status, with an unload warning while unsaved. Browser test selector errors were fixed in the smoke script. Current required software checks pass; historical failures are not outstanding failures.

## Remaining requirements and next steps

1. Resolve the physical geometry contradiction using actual measurements. Test-only 33 mm geometry is a software fixture, not a correction to the user's supplied roll.
2. Verify current official TSC specifications/command semantics and the installer publisher/signature on Windows. The TSC page returned 403 here. Do not run the uploaded installer without verification.
3. Run Windows 10/11 builds, native GDI/RAW and USB acceptance. Follow docs/PRINTER.md for alignment, row drift, safe margins, scanner readability, exact counts, independent-job boundaries and disconnection tests. The seven-label sample covers column positions/multiple rows; separate outline-grid and sensor-control utilities are not implemented. Use TSC's official calibration utility for sensor calibration.
4. Configure a dedicated read-only Odoo account securely. Verify database `/doc`, fields and live Sales Price semantics. Implement the pricelist adapter only after confirming a suitable public method and quantity/date/partner/company context. Do not modify live data.
5. Native Windows system print-dialog UI, code signing and an installer wizard remain release work. The application currently selects the printer in its own UI and uses native GDI for driver output.
6. Legacy XLS formula provenance cannot be reconstructed from xlrd's exposed cached values. Review its warnings and supply literal values, preferably through the XLSX template. Currency dropdown includes seven common symbol choices plus arbitrary typed symbols, rather than a complete ISO currency catalog. Large-job preview is paginated; no performance benchmark or load certification is claimed.

## Reusable environment configuration

Saved `install_script` and `start_skill` to the environment draft. These reproduce dependencies/build/tests and describe loopback startup/readiness checks and all safety limits. Saving does not publish a snapshot or validate restoration in a new task. Review/save in environment settings and publish when desired. No secrets or network-policy changes were saved.

## Project files

`backend/`: models, pure layout, rendering, importer, Odoo client, printer adapters and local API/persistence/security. `frontend/src/`: real React workflow and API client. `tests/`: 50 tests and actual XLSX/generated XLS fixtures. `samples/`: CSV and Excel templates. `scripts/`: cloud setup, Windows-compatible launcher and browser smoke. Root PowerShell/CMD/spec files: Windows installation and packaging. `docs/`: architecture, attachment evidence, Odoo guide, printer procedures and this report.

## New-PC installer addendum

Added a single hybrid CMD/PowerShell setup download: automatic compatible-Python discovery, official signed Python installation when needed, immutable GitHub package download with embedded SHA256 verification, per-version app environment, dependency/import/render checks, resumable known installs, log file, desktop shortcut and app launch. It neither changes execution policy nor installs unverified printer drivers. See docs/NEW-PC-SETUP.md.

Validation: three packaging tests passed (deterministic archive generation, credential/state exclusions, embedded built frontend, immutable download ref and matching package checksum, invalid/missing build rejection). The embedded PowerShell parsed successfully with the official PowerShell 7.5.4 Linux runtime after verifying its published release checksum; mutex construction also executed successfully. These checks do not establish Windows PowerShell 5.1/CMD compatibility or fresh-Windows installation success. Python installer signature verification, native installation, desktop shortcut and full fresh-PC flow remain Windows-dependent and unverified here.
