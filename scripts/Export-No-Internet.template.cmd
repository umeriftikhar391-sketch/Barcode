@echo off
setlocal
set "BARCODE_EXPORT_FILE=%~f0"
powershell.exe -NoLogo -NoProfile -STA -Command "$text=[IO.File]::ReadAllText($env:BARCODE_EXPORT_FILE);$marker='# BARCODE_EXPORT_POWERSHELL'; & ([scriptblock]::Create($text.Substring($text.LastIndexOf($marker)+$marker.Length)))"
set "BARCODE_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %BARCODE_RESULT%
# BARCODE_EXPORT_POWERSHELL
$ErrorActionPreference='Stop'
$ProgressPreference='SilentlyContinue'
$work=$null
$transcript=$false
try {
    $base=Join-Path $env:LOCALAPPDATA 'BarcodeStudio'
    New-Item -ItemType Directory -Force -Path $base | Out-Null
    $log=Join-Path $base ('offline-export-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.log')
    Start-Transcript -LiteralPath $log | Out-Null
    $transcript=$true
    Write-Host 'ZERO-INTERNET OFFLINE EXPORT' -ForegroundColor Cyan
    Write-Host 'Keep the working TE200 connected. This tool copies already installed software; it never downloads anything.'
    $archive=Join-Path ([IO.Path]::GetDirectoryName($env:BARCODE_EXPORT_FILE)) 'Application.zip'
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne '__APP_SHA256__') { throw 'Application archive checksum mismatch. Extract the whole exporter ZIP.' }
    $shell=New-Object -ComObject WScript.Shell
    $desktop=$shell.SpecialFolders.Item('Desktop')
    $source=$null
    $shortcut=Join-Path $desktop 'Barcode Studio.lnk'
    if (Test-Path -LiteralPath $shortcut) {
        $candidate=$shell.CreateShortcut($shortcut).WorkingDirectory
        if ($candidate -and ((Test-Path -LiteralPath (Join-Path $candidate '.venv\Scripts\python.exe')) -or (Test-Path -LiteralPath (Join-Path $candidate 'Runtime\python.exe')))) { $source=$candidate }
    }
    if (-not $source) {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog=New-Object System.Windows.Forms.OpenFileDialog
        $dialog.Title='Select Start-Barcode.cmd from the folder where your app already works'
        $dialog.Filter='Barcode launcher (Start-Barcode.cmd)|Start-Barcode.cmd'
        $dialog.InitialDirectory=$desktop
        if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { throw 'No working application folder selected. Nothing was changed.' }
        $source=[IO.Path]::GetDirectoryName($dialog.FileName)
    }
    $python=Join-Path $source '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) {
        $python=Join-Path $source 'Runtime\python.exe'
    }
    if (-not (Test-Path -LiteralPath $python)) { throw 'The selected app has no installed Python environment. Choose the folder containing your working app.' }
    $work=Join-Path ([IO.Path]::GetTempPath()) ('BarcodeLocalExport-'+[guid]::NewGuid().ToString('N'))
    Expand-Archive -LiteralPath $archive -DestinationPath $work
    $app=Join-Path $work 'Barcode'
    $output=Join-Path $desktop ('Barcode-NO-INTERNET-Setup-'+(Get-Date -Format 'yyyyMMdd-HHmmss')+'.zip')
    Push-Location -LiteralPath $app
    try {
        & $python -B -c "import runpy,sys;root=sys.argv[1];out=sys.argv[2];sys.path.insert(0,root);sys.argv=['portable-offline','--output',out];runpy.run_module('scripts.portable_offline',run_name='__main__')" $app $output
        if ($LASTEXITCODE -ne 0) { throw 'Offline export did not finish. Read the specific runtime/dependency/driver error above. No downloads were attempted.' }
    } finally { Pop-Location }
    Write-Host ('FINISHED. Your reusable offline installer is: '+$output) -ForegroundColor Green
    Start-Process explorer.exe -ArgumentList ('/select,"{0}"' -f $output)
    $code=0
} catch {
    Write-Host ('EXPORT STOPPED: '+$_.Exception.Message) -ForegroundColor Red
    if ($log) { Write-Host ('Log: '+$log) }
    $code=1
} finally {
    if ($transcript) { Stop-Transcript | Out-Null }
    if ($work -and (Test-Path -LiteralPath $work)) { Remove-Item -LiteralPath $work -Recurse -Force -ErrorAction SilentlyContinue }
}
exit $code
