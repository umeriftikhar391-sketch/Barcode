$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
py -3.12 -m venv .venv
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 x64 with the Python launcher first.' }
& .\.venv\Scripts\python.exe -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
if (-not (Test-Path 'frontend/dist/index.html')) {
npm ci --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'Install Node.js 22 LTS or newer. npm installation failed.' }
npm run build --prefix frontend
if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
}
Write-Host 'Installation complete. Double-click Start-Barcode.cmd.'
