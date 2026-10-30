@echo off
setlocal
set "BARCODE_UPDATE_FILE=%~f0"
powershell.exe -NoLogo -NoProfile -STA -Command "$text=[IO.File]::ReadAllText($env:BARCODE_UPDATE_FILE);$marker='# BARCODE_UPDATE_POWERSHELL'; & ([scriptblock]::Create($text.Substring($text.LastIndexOf($marker)+$marker.Length)))"
set "BARCODE_RESULT=%ERRORLEVEL%"
echo.
pause
exit /b %BARCODE_RESULT%
# BARCODE_UPDATE_POWERSHELL
$ErrorActionPreference='Stop'
try {
    Write-Host 'BARCODE STUDIO - OFFLINE APPLICATION UPDATE' -ForegroundColor Cyan
    Write-Host 'Close the Barcode Studio server/console window before continuing.'
    $root=[IO.Path]::GetDirectoryName($env:BARCODE_UPDATE_FILE)
    $archive=Join-Path $root 'Application.zip'
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash -ne '__APP_SHA256__') { throw 'Application archive checksum mismatch. Extract the whole update ZIP.' }
    $shell=New-Object -ComObject WScript.Shell
    $desktop=$shell.SpecialFolders.Item('Desktop')
    $shortcut=Join-Path $desktop 'Barcode Studio.lnk'
    $source=$null
    if (Test-Path -LiteralPath $shortcut) {
        $candidate=$shell.CreateShortcut($shortcut).WorkingDirectory
        if ($candidate -and (Test-Path -LiteralPath (Join-Path $candidate 'Start-Barcode.cmd'))) { $source=$candidate }
    }
    if (-not $source) {
        Add-Type -AssemblyName System.Windows.Forms
        $dialog=New-Object System.Windows.Forms.OpenFileDialog
        $dialog.Title='Select Start-Barcode.cmd from your working Barcode Studio folder'
        $dialog.Filter='Barcode launcher (Start-Barcode.cmd)|Start-Barcode.cmd'
        $dialog.InitialDirectory=$desktop
        if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { throw 'No app selected. Nothing was changed.' }
        $source=[IO.Path]::GetDirectoryName($dialog.FileName)
    }
    $python=Join-Path $source '.venv\Scripts\python.exe'
    if (-not (Test-Path -LiteralPath $python)) { $python=Join-Path $source 'Runtime\python.exe' }
    if (-not (Test-Path -LiteralPath $python)) { throw 'The selected folder has no working Python environment.' }
    & $python -B (Join-Path $root 'update_existing.py') --target $source --archive $archive --sha256 '__APP_SHA256__'
    if ($LASTEXITCODE -ne 0) { throw 'Update stopped. Read the error above; close the running app before retrying.' }
    Write-Host 'UPDATE COMPLETE. Opening Barcode Studio.' -ForegroundColor Green
    Start-Process -FilePath (Join-Path $source 'Start-Barcode.cmd') -WorkingDirectory $source
    $code=0
} catch {
    Write-Host ('UPDATE STOPPED: '+$_.Exception.Message) -ForegroundColor Red
    $code=1
}
exit $code
