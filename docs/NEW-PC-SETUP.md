# One-file setup for a new Windows PC

Download **Barcode-One-Click-Setup.zip** from this project's GitHub `downloads` folder. Right-click the ZIP, choose **Extract All**, then double-click **Setup-Barcode-Studio.cmd**. Keep the setup window open until it finishes. Run it as your ordinary Windows user, not as Administrator.

The CMD file is the installer. It downloads the application automatically, so you do not need to download/extract the full application ZIP, open Python, type PowerShell commands, install Node.js, or change PowerShell's execution policy. It runs ordinary inline PowerShell commands, not a policy-changing command. Organizational application-control rules still apply; contact your administrator if your organization's rules block it. The file is not code-signed; only run the copy from your own project repository after reviewing its provenance. Do not disable security products to run it.

What it does:

1. Checks for Python 3.12 x64 in known installed locations and the Python launcher.
2. If absent, downloads Python 3.12.10 x64 from the official python.org HTTPS endpoint, checks the Windows Authenticode signature and Python Software Foundation publisher, and installs it for your Windows account. Signature validation remains enabled. Existing Python installations are reused.
3. Downloads the exact application package from an immutable GitHub commit and checks the embedded SHA256 before extraction. Old setup files continue using their original package version. A checksum failure stops setup.
4. Installs a separate version of the application under `%LOCALAPPDATA%\BarcodeStudio\versions\<package-hash>`, creates its private Python environment, installs requirements, checks dependency consistency/imports, and generates a sample label in memory to verify rendering.
5. Creates a **Barcode Studio** desktop shortcut and starts the app. The existing app console remains open while you use it. Windows, USB hardware and browser behavior still require real-machine verification.

You need Windows 10/11 **x64**, Internet during setup, and permission to download/install software for your own Windows account. ARM64 native compatibility is not verified. New installs require access to `raw.githubusercontent.com`, `www.python.org`, `pypi.org`, and `files.pythonhosted.org`, plus Windows certificate-validation endpoints where required. The current GitHub application download was verified publicly accessible. If repository visibility changes to private, unauthenticated setup stops; it never asks for a token or password. Future offline setup and a signed MSI/EXE are separate release work.

After setup, the **Barcode Studio desktop shortcut** opens the application. Manual products, spreadsheet imports, saved queues and preview work without Internet. Odoo naturally requires Internet and separate authorized credentials.

Repeated runs of the same setup verify the existing version and recreate the shortcut; a partially installed known package can resume dependency installation. Unknown existing folders are not overwritten. Different packaged versions use different folders. Queue/history/calibration data stay in `%LOCALAPPDATA%\BarcodeStudio\state.sqlite`, outside version folders. This setup does not move settings or Odoo credentials from a different PC. Calibration must be repeated for that PC/printer configuration. No existing Python is removed, no printer driver is installed, and no Odoo credentials are requested or stored by setup.

If setup stops, leave its window open and read the message. Logs are in `%LOCALAPPDATA%\BarcodeStudio\setup-YYYYMMDD-HHMMSS.log`. Do not send credentials in screenshots or logs. Fix the reported network/permission problem, then rerun the same setup. Do not assume it finished if checks failed. A rare installer exit code requesting a restart may require Windows to restart before a retry.

Physical printer setup remains separate: verify and install the official TSC driver, connect USB, resolve the 113 mm/107 mm geometry contradiction and perform the complete calibration checklist. The setup file deliberately does not run the uploaded unverified printer installer or mark hardware tests as passed.

## Build and verification scope

`python scripts/package_windows.py` builds the full application ZIP including the compiled frontend, plus the small one-file setup ZIP. It excludes dependencies, local state/secrets, Git metadata and nested download archives. ZIP entries are deterministic. For publication, commit the application ZIP first, then run the packager with `--ref <full commit SHA>` and commit the generated setup downloads. The application ZIP does not contain the generated bootstrap, avoiding a circular checksum.

The packaging algorithm, archive contents/checksums and PowerShell syntax can be checked on Linux. Actual CMD execution, Windows Authenticode, per-user Python installation, desktop shortcut creation, and the full fresh-PC setup require Windows. Do not describe those as tested solely from Linux checks.
