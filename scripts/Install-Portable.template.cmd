@echo off
setlocal
set "BARCODE_PORTABLE_SETUP=%~f0"
powershell.exe -NoLogo -NoProfile -Command "$text=[IO.File]::ReadAllText($env:BARCODE_PORTABLE_SETUP);$marker='# BARCODE_PORTABLE_POWERSHELL'; & ([scriptblock]::Create($text.Substring($text.LastIndexOf($marker)+$marker.Length)))"
set "BARCODE_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %BARCODE_RESULT%
# BARCODE_PORTABLE_POWERSHELL
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$expected='__MANIFEST_SHA256__'
$root=[IO.Path]::GetDirectoryName($env:BARCODE_PORTABLE_SETUP)
$stage=$null
$transcript=$false
try {
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64') { throw 'Windows x64 is required.' }
    $base=Join-Path $env:LOCALAPPDATA 'BarcodeStudio'
    New-Item -ItemType Directory -Force -Path $base | Out-Null
    $log=Join-Path $base ('portable-setup-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.log')
    Start-Transcript -LiteralPath $log | Out-Null
    $transcript=$true
    Write-Host 'BARCODE STUDIO - NO-INTERNET INSTALLATION' -ForegroundColor Cyan
    $manifestPath=Join-Path $root 'manifest.json'
    if ((Get-Item -LiteralPath $manifestPath).Length -gt 10000000 -or (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash -ne $expected) { throw 'Installer manifest checksum/size check failed.' }
    $manifest=Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema -ne 1 -or $manifest.kind -ne 'portable-windows-x64' -or $manifest.python -ne '3.12') { throw 'Unsupported portable installer.' }
    $entries=@($manifest.files.PSObject.Properties)
    if ($entries.Count -lt 6 -or $entries.Count -gt 20000) { throw 'Invalid portable file inventory.' }
    $total=0L
    foreach ($entry in $entries) {
        $name=$entry.Name
        if ($name -notmatch '^(Payload/App/|PrinterBundle/)' -or $name -match '(^|/)\.\.?(/|$)|[:\\]' -or $entry.Value.sha256 -notmatch '^[a-f0-9]{64}$') { throw 'Unsafe installer file path/checksum.' }
        $file=Join-Path $root $name
        $item=Get-Item -LiteralPath $file
        if ($item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unsupported installer file/link.' }
        $total+=$item.Length
        if ($total -gt 2147483648 -or $item.Length -ne $entry.Value.bytes -or (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $entry.Value.sha256) { throw ('Installer file integrity check failed: '+$name) }
    }
    foreach ($required in @('Payload/App/Runtime/python.exe','Payload/App/Runtime/python312.dll','Payload/App/Runtime/python312._pth','Payload/App/frontend/dist/index.html','Payload/App/Start-Barcode.cmd','PrinterBundle/profile.json')) {
        if ($required -notin $entries.Name) { throw ('Missing required file: '+$required) }
    }
    foreach ($folder in @('Payload','PrinterBundle')) {
        foreach ($item in Get-ChildItem -LiteralPath (Join-Path $root $folder) -Recurse -Force) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked installer files/folders are not supported.' }
            if (-not $item.PSIsContainer) {
                $relative=$item.FullName.Substring($root.Length+1).Replace('\','/')
                if ($relative -notin $entries.Name) { throw ('Unlisted installer file: '+$relative) }
            }
        }
    }
    foreach ($name in @('python.exe','python312.dll')) {
        $sig=Get-AuthenticodeSignature -LiteralPath (Join-Path $root ('Payload/App/Runtime/'+$name))
        if ($sig.Status -ne 'Valid' -or $sig.SignerCertificate.Subject -notmatch '(?:^|,\s*)O=Python Software Foundation(?:,|$)') { throw ('Python runtime signature/publisher could not be verified: '+$name) }
    }
    $parent=Join-Path $base 'portable'
    New-Item -ItemType Directory -Force -Path $parent | Out-Null
    $target=Join-Path $parent $expected.Substring(0,16)
    if (Test-Path -LiteralPath $target) {
        $marker=Join-Path $target '.portable-package-sha256'
        if (-not (Test-Path -LiteralPath $marker) -or (Get-Content -LiteralPath $marker -Raw).Trim() -ne $expected) { throw 'An unknown installation folder already exists. It was not overwritten.' }
    } else {
        $stage=Join-Path $parent ([guid]::NewGuid().ToString('N'))
        Copy-Item -LiteralPath (Join-Path $root 'Payload/App') -Destination $stage -Recurse
        Set-Content -LiteralPath (Join-Path $stage '.portable-package-sha256') -Value $expected -Encoding ASCII
        Move-Item -LiteralPath $stage -Destination $target
        $stage=$null
    }
    foreach ($entry in $entries) {
        if ($entry.Name.StartsWith('Payload/App/')) {
            $file=Join-Path $target $entry.Name.Substring(12)
            if ((Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $entry.Value.sha256) { throw 'Installed application files differ from this package; no files were overwritten.' }
        }
    }
    $python=Join-Path $target 'Runtime/python.exe'
    Push-Location -LiteralPath $target
    try {
        & $python -I -B -c "import fastapi,uvicorn,openpyxl,xlrd,barcode,PIL,fontTools,httpx,keyring,win32print,win32ui; from backend.models import Product,Geometry; from backend.render import label; assert label(Product(name='Coaster',barcode='1000111',price='1200',symbol='Rs.',quantity=1),Geometry(width=33,height=24,safe=2)).width>0; print('Private runtime and renderer verified.')"
        if ($LASTEXITCODE -ne 0) { throw 'Private runtime verification failed. No downloads will be attempted.' }
        & $python -I -B -m scripts.provision_printer restore --folder (Join-Path $root 'PrinterBundle')
        if ($LASTEXITCODE -ne 0) { throw 'The app is installed, but printer setup is incomplete. Read the specific error above; connect/power on the TE200 and retry. No port was guessed.' }
    } finally { Pop-Location }
    $shell=New-Object -ComObject WScript.Shell
    $shortcut=$shell.CreateShortcut((Join-Path $shell.SpecialFolders.Item('Desktop') 'Barcode Studio.lnk'))
    $shortcut.TargetPath=Join-Path $target 'Start-Barcode.cmd'
    $pythonw=Join-Path $target 'Runtime\pythonw.exe'
    if (Test-Path -LiteralPath $pythonw) {
        $shortcut.TargetPath=$pythonw
        $shortcut.Arguments='-B "{0}"' -f (Join-Path $target 'scripts\desktop.pyw')
    }
    $shortcut.WorkingDirectory=$target
    $icon=Join-Path $target 'assets\windows\BarcodeStudio.ico'
    if (Test-Path -LiteralPath $icon) { $shortcut.IconLocation=$icon+',0' }
    $shortcut.Save()
    Write-Host 'OFFLINE SOFTWARE INSTALLATION COMPLETE' -ForegroundColor Green
    Write-Host 'No Internet downloads or global Python installation were required. Calibration checklists are optional.'
    if (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue) {
        Write-Host 'Click Close app in the sidebar (or close the old console) and open the new desktop shortcut.'
    } else { Start-Process -FilePath (Join-Path $shell.SpecialFolders.Item('Desktop') 'Barcode Studio.lnk') }
    $code=0
} catch {
    Write-Host ('SETUP STOPPED: '+$_.Exception.Message) -ForegroundColor Red
    if ($log) { Write-Host ('Log: '+$log) }
    $code=1
} finally {
    if ($transcript) { Stop-Transcript | Out-Null }
    if ($stage -and (Test-Path -LiteralPath $stage)) { Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue }
}
exit $code
