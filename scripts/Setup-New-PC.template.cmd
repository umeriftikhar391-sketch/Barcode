@echo off
setlocal
set "BARCODE_SETUP_MODE=__SETUP_MODE__"
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
$packageUrl = '__PACKAGE_URL__'
$packageHash = '__PACKAGE_SHA256__'
$base = Join-Path $env:LOCALAPPDATA 'BarcodeStudio'
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

function Download-VerifiedPackage($target) {
    Write-Host 'Downloading the Barcode Studio application...'
    try {
        Invoke-WebRequest -UseBasicParsing -Uri $packageUrl -OutFile $target
    } catch {
        throw 'Application download failed. Check Internet access and GitHub repository access. A private repository requires an authenticated download; this installer does not collect GitHub passwords or tokens.'
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
    Write-Host 'Installs the app for your Windows account. Internet is needed once.'
    Write-Host 'No Node.js or typed setup commands are needed. Driver capture/installation requests Windows administrator approval.'
    Write-Host ('Log: ' + $log)
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
    $work = Join-Path ([IO.Path]::GetTempPath()) ('BarcodeSetup-' + [guid]::NewGuid().ToString('N'))
    New-Item -ItemType Directory -Path $work | Out-Null

    $python = Get-CompatiblePython
    if (-not $python) {
        Write-Host 'Downloading Python 3.12.10 x64 from python.org...'
        $installer = Join-Path $work 'python-3.12.10-amd64.exe'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.exe' -OutFile $installer
        $signature = Get-AuthenticodeSignature -LiteralPath $installer
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '(?:^|,\s*)O=Python Software Foundation(?:,|$)') {
            throw 'Python installer signature/publisher could not be verified. Installation stopped; no signature checks have been disabled.'
        }
        Write-Host 'Verified Python Software Foundation signature. Installing for the current account...'
        $arguments = @('/quiet', 'InstallAllUsers=0', 'Include_launcher=0', 'Include_test=0', 'PrependPath=0', ('TargetDir="{0}"' -f $runtime))
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
        & $venv -m pip install --disable-pip-version-check -r (Join-Path $appDir 'requirements.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed. Check Internet/proxy access, then rerun this setup to resume.' }
    }

    $venv = Join-Path $appDir '.venv\Scripts\python.exe'
    & $venv -m pip check
    if ($LASTEXITCODE -ne 0) { throw 'Dependency consistency check failed.' }
    & $venv -c "import fastapi,uvicorn,openpyxl,xlrd,barcode,PIL,fontTools,httpx,keyring,win32print,win32ui"
    if ($LASTEXITCODE -ne 0) { throw 'An application dependency could not load. Setup is not complete.' }
    Push-Location -LiteralPath $appDir
    try {
        & $venv -c "from backend.models import Product,Geometry; from backend.render import label; p=Product(name='Coaster',barcode='1000111',price='1200',symbol='Rs.',quantity=1); assert label(p,Geometry()).size[0]>0; print('Barcode renderer check passed.')"
        if ($LASTEXITCODE -ne 0) { throw 'Barcode renderer readiness check failed.' }
    } finally { Pop-Location }
    Set-Content -LiteralPath $complete -Value $packageHash -Encoding ASCII

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut((Join-Path $shell.SpecialFolders.Item('Desktop') 'Barcode Studio.lnk'))
    $shortcut.TargetPath = Join-Path $appDir 'Start-Barcode.cmd'
    $shortcut.WorkingDirectory = $appDir
    $shortcut.Description = 'Open Barcode Studio local label workspace'
    $shortcut.Save()
    $bundle = Join-Path ([IO.Path]::GetDirectoryName($env:BARCODE_SETUP_FILE)) 'PrinterBundle'
    if ($env:BARCODE_SETUP_MODE -eq 'prepare') {
        $output = Join-Path $shell.SpecialFolders.Item('Desktop') ('Barcode-Full-PC-Setup-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.zip')
        Write-Host 'Capturing the working TE200 driver and exact printer preferences. Approve the Windows driver-export prompt.'
        Push-Location -LiteralPath $appDir
        try {
            & $venv -m scripts.provision_printer prepare --setup $env:BARCODE_SETUP_FILE --output $output
            if ($LASTEXITCODE -ne 0) { throw 'Could not create the matched-PC setup. Read the printer export error above. Your current printer settings were not changed.' }
        } finally { Pop-Location }
        Write-Host 'FULL NEW-PC SETUP CREATED' -ForegroundColor Green
        Write-Host ('Copy this single ZIP to each new Windows x64 PC: ' + $output)
        Write-Host 'Extract it, connect/power on the TE200, and double-click Setup-Barcode-Studio.cmd. Keep PrinterBundle beside that CMD.'
        Write-Host 'The ZIP contains the signed driver and tested media settings. Physical calibration confirmation must be completed on each PC.'
        Start-Process explorer.exe -ArgumentList ('/select,"{0}"' -f $output)
    } else {
        Push-Location -LiteralPath $appDir
        try {
            if (Test-Path -LiteralPath $bundle) {
                Write-Host 'Installing the captured signed driver and restoring the tested media settings. Keep the TE200 powered on and connected by USB.'
                & $venv -m scripts.provision_printer restore --folder $bundle
                if ($LASTEXITCODE -ne 0) { throw 'App installed, but printer setup is incomplete. Read the specific error above, resolve it and rerun this setup. Production remains locked.' }
            } else {
                & $venv -m scripts.provision_printer initialize
                if ($LASTEXITCODE -ne 0) { throw 'Could not initialize the confirmed roll geometry.' }
                Write-Host 'This download has no captured PrinterBundle. For automatic driver/profile setup, create the full ZIP on your working PC using Prepare-Full-PC-Setup.cmd.' -ForegroundColor Yellow
            }
        } finally { Pop-Location }
        Write-Host ''
        Write-Host 'SOFTWARE INSTALLATION COMPLETE' -ForegroundColor Green
        Write-Host 'Use the Barcode Studio desktop shortcut next time. Keep its console window open while using it.'
        Write-Host 'Confirmed roll: 107 mm, three 33 x 24 mm stickers, 2 mm gaps/margins, 2 mm internal safe margins.'
        Write-Host 'A short physical verification is required on this PC before production printing unlocks. Odoo credentials are not transferred.'
        Write-Host ('Application folder: ' + $appDir)
        $listener = Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue
        if ($listener) {
            Write-Host 'An app is already using port 8765. Close the old Barcode Studio console, then open the new desktop shortcut.' -ForegroundColor Yellow
        } else {
            Start-Process -FilePath (Join-Path $appDir 'Start-Barcode.cmd') -WorkingDirectory $appDir
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
