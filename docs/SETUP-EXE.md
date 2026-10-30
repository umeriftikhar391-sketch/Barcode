# Windows Setup.exe

[Download Setup.exe](https://github.com/umeriftikhar391-sketch/Barcode/raw/refs/heads/main/downloads/Setup.exe)

This is the online installer for Windows 10/11 x64. Connect and switch on the
TSC TE200, run Setup.exe, choose a writable installation folder, and click
Install. The final Open app button launches the new desktop shortcut.

The native Windows executable opens a setup window without requiring Python,
Node.js, Inno Setup or another third-party runtime. Windows PowerShell and .NET
Framework/Windows Forms, normally supplied by supported Windows versions, host
the interface. Downloads begin only after Install is clicked.

## Installation behavior

- Detects compatible Python 3.12 x64 at known locations or through the Python
  launcher. If absent, downloads the full official Python installer from
  python.org, verifies the Python Software Foundation Authenticode signature,
  and installs it for the current account under the chosen folder.
- Downloads an immutable application archive, verifies its embedded SHA256,
  and installs pinned dependencies into a private virtual environment. Existing
  compatible Python is reused, and missing packages are installed on rerun.
- Reuses an existing working TE200 queue and its media preferences. If none is
  present, requests Windows administrator approval and searches Windows Update
  for a driver whose hardware ID exactly matches the connected TE200. Windows
  validates the driver package; signature checks are not bypassed. Driver
  licenses requiring acceptance are shown to the operator.
- Attempts standard driver page dimensions for the saved geometry (initially
  a 107 × 24 mm row at 203 DPI) and checks actual GDI page size and offsets.
  Vendor-private preferences are never guessed. An unavailable catalog driver,
  ambiguous queue, missing device or unsupported page setting is reported as
  **PRINTER PENDING**. The app remains installed; this is not reported as a
  ready printer. An official manufacturer installation or the existing captured
  driver deployment may then be necessary.
- Creates a desktop shortcut with the supplied teal barcode icon. The shortcut
  opens the app without a console and reuses an already running local service.
  **Close app** in the sidebar saves pending queue changes and gracefully stops
  the service. Use it before applying an app update.
- Product queues and credentials are not imported from another PC. Existing
  data for the current Windows account is preserved. Calibration checklist
  confirmation is optional.

Choosing a protected installation folder can require running setup with suitable
Windows rights. The default folder is writable by the current account. Driver
installation has its own Windows elevation prompt.

## Daily use

Open the desktop shortcut, choose an Excel file, click **Import and preview
labels**, then **Print** directly from the preview. A single detected TE200 is
selected automatically; a previously saved available printer is preferred.
Multiple possible printers require choosing the intended one.

## Verification and limits

The executable is compiled from `scripts/windows/setup_stub.c` with MinGW-w64.
It loads only Windows system DLLs. Setup GUI, pinned engine and ICO bytes occupy
bounded PE resource slots; `scripts/windows_sfx.py` fills them and recomputes
the PE checksum. The application archive is committed before the online setup
is regenerated against that immutable commit.

Tests cover resource integrity, architecture/checksum, package binding, existing
driver reuse, driver-pending status, desktop service reuse and authenticated
shutdown. Real-browser checks cover the supplied Excel, automatic TE200 choice,
direct preview printing with a simulated spooler and real service shutdown.
PowerShell scripts pass syntax parsing. Full execution of Setup.exe, Python
installation, Windows Update driver availability, driver preferences and actual
printing still require Windows/hardware verification. This executable is not
Authenticode-signed; no signing certificate was provided.

To rebuild the native host on a Linux build machine with MinGW-w64 and Pillow:
`python scripts/windows/build_stub.py`. An extracted Debian toolchain can be
specified with `MINGW_ROOT`. Ordinary release packaging uses the compiled stub
and needs no C compiler: build the frontend, then run
`python -m scripts.package_windows --ref <application-commit-sha>`.
