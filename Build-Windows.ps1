$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
npm ci --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed' }
npm run build --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed' }
& powershell -File .\Install-Windows.ps1
if ($LASTEXITCODE -ne 0) { throw 'Installation failed' }
& .\.venv\Scripts\python.exe -m pip install pyinstaller==6.16.0
if ($LASTEXITCODE -ne 0) { throw 'Build tool installation failed' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm barcode-studio.spec
if ($LASTEXITCODE -ne 0) { throw 'Packaging failed' }
Write-Host 'Build output: dist\BarcodeStudio\BarcodeStudio.exe. Windows and hardware acceptance still required.'
