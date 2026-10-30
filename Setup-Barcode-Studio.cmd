@echo off
setlocal
set "BARCODE_SETUP_MODE=install"
set "BARCODE_SETUP_FILE=%~f0"
powershell.exe -NoLogo -NoProfile -Command "$text = [IO.File]::ReadAllText($env:BARCODE_SETUP_FILE); $marker = '# BARCODE_POWERSHELL_BEGIN'; $code = $text.Substring($text.LastIndexOf($marker) + $marker.Length); & ([scriptblock]::Create($code))"
set "BARCODE_RESULT=%ERRORLEVEL%"
echo.
if not "%BARCODE_RESULT%"=="0" echo Setup did not finish. Read the error and log location above before retrying.
pause
exit /b %BARCODE_RESULT%
# BARCODE_POWERSHELL_BEGIN
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$packageUrl = 'https://raw.githubusercontent.com/umeriftikhar391-sketch/Barcode/d0bb2229bb0bd41bd8faa50c5c8cea749ea25804/downloads/Barcode-Studio.zip'
$packageHash = '0d1d0b775ee9fc44079cbd3c7fb1808ed031efc48f00291afceb6d03711cb86a'
$offlineManifestHash = ''
$offlineMode = $env:BARCODE_SETUP_MODE -eq 'install-offline'
$offlineRoot = Join-Path ([IO.Path]::GetDirectoryName($env:BARCODE_SETUP_FILE)) 'OfflinePayload'
$base = Join-Path $env:LOCALAPPDATA 'BarcodeStudio'
if ($env:BARCODE_INSTALL_ROOT) { $base = [IO.Path]::GetFullPath($env:BARCODE_INSTALL_ROOT) }
$runtime = Join-Path $base 'Runtime\Python312'
$appDir = Join-Path $base ('versions\' + $packageHash.Substring(0, 16))
$log = Join-Path $base ('setup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.log')
$work = $null
$transcript = $false
$mutex = $null
$locked = $false
$resultCode = 1

function Get-CompatiblePython {
    $candidates = @(
        (Join-Path $runtime 'python.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        (Join-Path $env:ProgramFiles 'Python312\python.exe')
    )
    foreach ($candidate in $candidates) {
        if (Test-Path -LiteralPath $candidate) {
            try {
                $answer = & $candidate -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8; print(sys.executable)" 2>$null
                if ($LASTEXITCODE -eq 0 -and $answer) { return [string]($answer | Select-Object -Last 1) }
            } catch { }
        }
    }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            $answer = & $launcher.Source -3.12 -c "import sys,struct; assert sys.version_info[:2] == (3,12) and struct.calcsize('P') == 8; print(sys.executable)" 2>$null
            if ($LASTEXITCODE -eq 0 -and $answer) { return [string]($answer | Select-Object -Last 1) }
        } catch { }
    }
    return $null
}

function Assert-OfflinePayload {
    if ($offlineManifestHash -notmatch '^[a-f0-9]{64}$') { throw 'Offline manifest checksum is missing. Setup cannot continue.' }
    $manifestPath = Join-Path $offlineRoot 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'OfflinePayload is missing. Extract the entire offline ZIP before running setup. No downloads will be attempted.' }
    if ((Get-Item -LiteralPath $manifestPath).Length -gt 200000) { throw 'Offline manifest is too large.' }
    if ((Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash -ne $offlineManifestHash) { throw 'Offline manifest checksum mismatch.' }
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema -ne 1 -or $manifest.platform -ne 'win_amd64' -or $manifest.python -ne '3.12') { throw 'Unsupported offline payload.' }
    $files = @($manifest.files.PSObject.Properties)
    if ($files.Count -lt 4 -or $files.Count -gt 1000) { throw 'Invalid offline file list.' }
    $expected = @('manifest.json')
    $total = 0L
    foreach ($entry in $files) {
        $name = $entry.Name
        if ($name -notmatch '^(application/Barcode-Studio\.zip|python/python-3\.12\.10-amd64\.exe|requirements-offline\.txt|wheelhouse/[A-Za-z0-9_.+\-]+\.whl)$') { throw ('Invalid offline file path: ' + $name) }
        if ($entry.Value.sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Invalid offline file checksum.' }
        $path = Join-Path $offlineRoot $name
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) { throw ('Missing offline file: ' + $name) }
        $item = Get-Item -LiteralPath $path
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Offline payload must not contain links.' }
        $total += $item.Length
        if ($total -gt 2147483648 -or $item.Length -ne $entry.Value.bytes -or (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash -ne $entry.Value.sha256) { throw ('Offline file integrity check failed: ' + $name) }
        $expected += $name
    }
    foreach ($required in @('application/Barcode-Studio.zip','python/python-3.12.10-amd64.exe','requirements-offline.txt')) {
        if ($required -notin $expected) { throw ('Offline manifest is missing ' + $required) }
    }
    foreach ($item in Get-ChildItem -LiteralPath $offlineRoot -Recurse -Force) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Offline payload must not contain linked folders/files.' }
        if (-not $item.PSIsContainer) {
            $relative = $item.FullName.Substring($offlineRoot.Length + 1).Replace('\','/')
            if ($relative -notin $expected) { throw ('Unlisted offline file: ' + $relative) }
        }
    }
    foreach ($item in @(Get-ChildItem Env: | Where-Object { $_.Name -like 'PIP_*' })) { Remove-Item -LiteralPath ('Env:' + $item.Name) }
    $env:PIP_CONFIG_FILE = 'NUL'
    $env:PIP_NO_INDEX = '1'
    $env:PIP_NO_CACHE_DIR = '1'
    $env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
    Write-Host 'Offline payload checksums verified. Installation will use local files only.'
}

function Download-VerifiedPackage($target) {
    if ($offlineMode) {
        Copy-Item -LiteralPath (Join-Path $offlineRoot 'application/Barcode-Studio.zip') -Destination $target
    } else {
    Write-Host 'Downloading the Barcode Studio application...'
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $packageUrl -OutFile $target
    } catch {
        throw 'Application download failed. Check Internet access and GitHub repository access. A private repository requires an authenticated download; this installer does not collect GitHub passwords or tokens.'
    }
    }
    $actual = (Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash
    if ($actual -ne $packageHash) {
        throw 'Application checksum mismatch. Nothing from this archive will run. Download a fresh setup file from the project GitHub repository.'
    }
}

try {
    if (-not [Environment]::Is64BitOperatingSystem) { throw 'Windows 10/11 x64 is required.' }
    if ($env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') {
        throw 'This setup targets x64 Windows PCs. ARM64 native compatibility is not verified.'
    }
    New-Item -ItemType Directory -Force -Path $base | Out-Null
    $mutex = New-Object Threading.Mutex($false, 'Local\BarcodeStudioSetup')
    try { $locked = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $locked = $true }
    if (-not $locked) { throw 'Another Barcode Studio setup is running. Wait for it to finish.' }
    Start-Transcript -LiteralPath $log | Out-Null
    $transcript = $true
    Write-Host 'BARCODE STUDIO - NEW PC SETUP' -ForegroundColor Cyan
    if ($offlineMode) { Write-Host 'Offline installation: Python, wheels, app and driver are supplied locally.' } else { Write-Host 'Installs the app for your Windows account. Internet is needed to create/download the deployment package.' }
    Write-Host 'No Node.js or typed setup commands are needed. Driver capture/installation requests Windows administrator approval.'
    Write-Host ('Log: ' + $log)
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $work = Join-Path ([IO.Path]::GetTempPath()) ('BarcodeSetup-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $work | Out-Null

    if ($offlineMode) {
        Assert-OfflinePayload
        if (-not (Test-Path -LiteralPath (Join-Path ([IO.Path]::GetDirectoryName($env:BARCODE_SETUP_FILE)) 'PrinterBundle/profile.json'))) { throw 'Offline printer bundle is missing. Extract the entire ZIP.' }
    }
    $python = Get-CompatiblePython
    if (-not $python) {
        if ($offlineMode) {
            $installer = Join-Path $offlineRoot 'python/python-3.12.10-amd64.exe'
            Write-Host 'Using the bundled full Python installer...'
        } else {
            Write-Host 'Downloading Python 3.12.10 x64 from python.org...'
            $installer = Join-Path $work 'python-3.12.10-amd64.exe'
            Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $installer
        }
        $signature = Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(?:^|,\s*)O=Python Software Foundation(?:,|$)') {
            throw 'Python installer signature/publisher could not be verified. Installation stopped; no signature checks have been disabled.'
        }
        Write-Host 'Verified Python Software Foundation signature. Installing for the current account...'
        $arguments = @('/quiet', 'InstallAllUsers=0', 'Include_launcher=0', 'Include_test=0', 'Include_doc=0', 'Include_tcltk=0', 'PrependPath=0', ('TargetDir="{0}"' -f $runtime))
        $process = Start-Process -FilePath $installer -ArgumentList $arguments -Wait -PassThru
        if ($process.ExitCode -notin @(0, 3010)) { throw ('Python installer failed with exit code ' + $process.ExitCode) }
        $python = Get-CompatiblePython
        if (-not $python) { throw 'Python installation did not become available. Restart Windows if the installer requested it, then rerun setup.' }
    } else {
        Write-Host ('Using existing Python: ' + $python)
    }

    $complete = Join-Path $appDir '.setup-complete'
    if (Test-Path -LiteralPath $complete) {
        if ((Get-Content -LiteralPath $complete -Raw).Trim() -ne $packageHash) { throw 'Existing installation marker does not match this package. No files were overwritten.' }
        Write-Host 'This version is already installed. Checking its dependencies...'
        $venv = Join-Path $appDir '.venv\Scripts\python.exe'
        if (-not (Test-Path -LiteralPath $venv)) {
            & $python -m venv (Join-Path $appDir '.venv')
            if ($LASTEXITCODE -ne 0) { throw 'Could not repair the private Python environment.' }
        }
        if ($offlineMode) {
            & $venv -m pip install --no-index --find-links (Join-Path $offlineRoot 'wheelhouse') --require-hashes --only-binary=:all: --no-cache-dir --disable-pip-version-check -r (Join-Path $offlineRoot 'requirements-offline.txt')
        } else {
            & $venv -m pip install --disable-pip-version-check -r (Join-Path $appDir 'requirements.txt')
        }
        if ($LASTEXITCODE -ne 0) { throw 'Could not repair missing application packages.' }
    } else {
        if (-not (Test-Path -LiteralPath $appDir)) {
            $archive = Join-Path $work 'Barcode-Studio.zip'
            Download-VerifiedPackage $archive
            $unpacked = Join-Path $work 'unpacked'
            Expand-Archive -LiteralPath $archive -DestinationPath $unpacked
            $source = Join-Path $unpacked 'Barcode'
            foreach ($required in @('requirements.txt', 'scripts\launch.py', 'frontend\dist\index.html', 'backend\app.py', 'Start-Barcode.cmd')) {
                if (-not (Test-Path -LiteralPath (Join-Path $source $required))) { throw ('Downloaded package is missing ' + $required) }
            }
            New-Item -ItemType Directory -Force -Path (Split-Path $appDir) | Out-Null
            Move-Item -LiteralPath $source -Destination $appDir
            Set-Content -LiteralPath (Join-Path $appDir '.package-sha256') -Value $packageHash -Encoding ASCII
        } elseif (-not (Test-Path -LiteralPath (Join-Path $appDir '.package-sha256')) -or (Get-Content -LiteralPath (Join-Path $appDir '.package-sha256') -Raw).Trim() -ne $packageHash) {
            throw 'The target folder contains unknown files. Setup will not overwrite it. See the log for the install path.'
        }
        Write-Host 'Preparing the private Python environment...'
        & $python -m venv (Join-Path $appDir '.venv')
        if ($LASTEXITCODE -ne 0) { throw 'Python environment creation failed.' }
        $venv = Join-Path $appDir '.venv\Scripts\python.exe'
        Write-Host 'Installing application dependencies. This may take several minutes...'
        if ($offlineMode) {
            & $venv -m pip install --no-index --find-links (Join-Path $offlineRoot 'wheelhouse') --require-hashes --only-binary=:all: --no-cache-dir --disable-pip-version-check -r (Join-Path $offlineRoot 'requirements-offline.txt')
        } else {
            & $venv -m pip install --disable-pip-version-check -r (Join-Path $appDir 'requirements.txt')
        }
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Offline setup never falls back to the Internet. Read the error above, then rerun setup after resolving it.' }
    }

    $venv = Join-Path $appDir '.venv\Scripts\python.exe'
    & $venv -m pip check
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Repairing missing or inconsistent application packages...'
        if ($offlineMode) {
            & $venv -m pip install --no-index --find-links (Join-Path $offlineRoot 'wheelhouse') --require-hashes --only-binary=:all: --no-cache-dir --disable-pip-version-check -r (Join-Path $offlineRoot 'requirements-offline.txt')
        } else {
            & $venv -m pip install --disable-pip-version-check -r (Join-Path $appDir 'requirements.txt')
        }
        if ($LASTEXITCODE -ne 0) { throw 'Dependency repair failed.' }
        & $venv -m pip check
        if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed after repair.' }
    }
    & $venv -c "import fastapi,uvicorn,openpyxl,xlrd,barcode,PIL,fontTools,httpx,keyring,win32print,win32ui"
    if ($LASTEXITCODE -ne 0) { throw 'An application dependency could not load. Setup is not complete. Rerun setup to repair the installation.' }
    Push-Location -LiteralPath $appDir
    try {
        & $venv -c "from backend.models import Product,Geometry; from backend.render import label; p=Product(name='Coaster',barcode='1000111',price='1200',symbol='Rs.',quantity=1); assert label(p,Geometry()).size[0]>0; print('Barcode renderer check passed.')"
        if ($LASTEXITCODE -ne 0) { throw 'Barcode renderer readiness check failed.' }
    } finally { Pop-Location }
    Set-Content -LiteralPath $complete -Value $packageHash -Encoding ASCII

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut((Join-Path $shell.SpecialFolders.Item('Desktop') 'Barcode Studio.lnk'))
    $shortcut.TargetPath = Join-Path $appDir 'Start-Barcode.cmd'
    $pythonw = Join-Path $appDir '.venv\Scripts\pythonw.exe'
    if ((Test-Path -LiteralPath $pythonw) -and (Test-Path -LiteralPath (Join-Path $appDir 'scripts\desktop.pyw'))) {
        $shortcut.TargetPath = $pythonw
        $shortcut.Arguments = '-B "{0}"' -f (Join-Path $appDir 'scripts\desktop.pyw')
    }
    $shortcut.WorkingDirectory = $appDir
    $shortcut.Description = 'Open Barcode Studio local label workspace'
    $appIcon = Join-Path $appDir 'assets\windows\BarcodeStudio.ico'
    if (Test-Path -LiteralPath $appIcon) { $shortcut.IconLocation = $appIcon + ',0' }
    $shortcut.Save()
    $bundle = Join-Path ([IO.Path]::GetDirectoryName($env:BARCODE_SETUP_FILE)) 'PrinterBundle'
    if ($env:BARCODE_SETUP_MODE -in @('prepare','prepare-offline')) {
        $prefix = 'Barcode-Full-PC-Setup-'
        if ($env:BARCODE_SETUP_MODE -eq 'prepare-offline') { $prefix = 'Barcode-OFFLINE-PC-Setup-' }
        $output = Join-Path $shell.SpecialFolders.Item('Desktop') ($prefix + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.zip')
        Write-Host 'Capturing the working TE200 driver and exact printer preferences. Approve the Windows driver-export prompt.'
        Push-Location -LiteralPath $appDir
        try {
            if ($env:BARCODE_SETUP_MODE -eq 'prepare-offline') {
                & $venv -m scripts.offline_bundle --setup $env:BARCODE_SETUP_FILE --output $output
            } else {
                & $venv -m scripts.provision_printer prepare --setup $env:BARCODE_SETUP_FILE --output $output
            }
            if ($LASTEXITCODE -ne 0) { throw 'Could not create the deployment package. Read the download/dependency/printer export error above. Your current printer settings were not changed.' }
        } finally { Pop-Location }
        Write-Host 'FULL NEW-PC SETUP CREATED' -ForegroundColor Green
        Write-Host ('Copy this single ZIP to each new Windows x64 PC: ' + $output)
        Write-Host 'Extract it, connect/power on the TE200, and double-click Setup-Barcode-Studio.cmd. Keep PrinterBundle beside that CMD.'
        Write-Host 'The ZIP contains the signed driver and tested media settings. Inspect physical output on each PC; calibration checklists are optional.'
        if ($env:BARCODE_SETUP_MODE -eq 'prepare-offline') { Write-Host 'OFFLINE BUNDLE: Python installer, all dependency wheels and the application are included. Keep OfflinePayload beside the CMD; no Internet is needed on the destination PC.' -ForegroundColor Green }
        Start-Process explorer.exe -ArgumentList ('/select,"{0}"' -f $output)
    } else {
        Push-Location -LiteralPath $appDir
        try {
            if (Test-Path -LiteralPath $bundle) {
                Write-Host 'Installing the captured signed driver and restoring the tested media settings. Keep the TE200 powered on and connected by USB.'
                & $venv -m scripts.provision_printer restore --folder $bundle
                if ($LASTEXITCODE -ne 0) { throw 'App installed, but printer setup is incomplete. Read the specific error above, resolve it and rerun this setup. Printer setup still needs attention.' }
            } else {
                if ($env:BARCODE_DOWNLOAD_PRINTER -eq '1') {
                    & $venv -m scripts.online_printer
                } else {
                    & $venv -m scripts.provision_printer initialize
                }
                if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the confirmed roll geometry.' }
                if ($env:BARCODE_DOWNLOAD_PRINTER -ne '1') { Write-Host 'This download has no captured PrinterBundle. For automatic driver/profile setup, create the full ZIP on your working PC using Prepare-Full-PC-Setup.cmd.' -ForegroundColor Yellow }
            }
        } finally { Pop-Location }
        Write-Host ''
        Write-Host 'SOFTWARE INSTALLATION COMPLETE' -ForegroundColor Green
        Write-Host 'Use the Barcode Studio desktop shortcut next time. The app runs without a console window.'
        Write-Host 'Confirmed roll: 107 mm, three 33 x 24 mm stickers, 2 mm gaps/margins, 2 mm internal safe margins.'
        Write-Host 'Calibration checklists are optional. Odoo credentials are not transferred.'
        Write-Host ('Application folder: ' + $appDir)
        $listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
        if ($listener) {
            Write-Host 'An app is already using port 8765. Click Close app in the sidebar (or close the old console), then open the new desktop shortcut.' -ForegroundColor Yellow
        } elseif ($env:BARCODE_NO_LAUNCH -ne '1') {
            Start-Process -FilePath (Join-Path $shell.SpecialFolders.Item('Desktop') 'Barcode Studio.lnk')
        }
    }
    $resultCode = 0
} catch {
    Write-Host ''
    Write-Host ('SETUP STOPPED: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host ('Log: ' + $log)
    Write-Host 'Keep this window open and share the error message if you need help.'
} finally {
    if ($transcript) { Stop-Transcript | Out-Null }
    if ($work -and (Test-Path -LiteralPath $work)) { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
    if ($locked) { $mutex.ReleaseMutex() }
    if ($mutex) { $mutex.Dispose() }
}
exit $resultCode
