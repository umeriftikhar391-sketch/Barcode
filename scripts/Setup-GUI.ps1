$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[Windows.Forms.Application]::EnableVisualStyles()
$root=$env:BARCODE_SETUP_GUI_ROOT
$script:engine=$null
$script:finished=$false
$desktop=(New-Object -ComObject WScript.Shell).SpecialFolders.Item('Desktop')
$form=New-Object Windows.Forms.Form
$form.Text='Barcode Studio Setup'
$form.Size=New-Object Drawing.Size(650,580)
$form.MinimumSize=$form.Size
$form.StartPosition='CenterScreen'
$form.Font=New-Object Drawing.Font('Segoe UI',10)
$form.BackColor=[Drawing.Color]::FromArgb(243,246,247)
$form.Icon=New-Object Drawing.Icon((Join-Path $root 'BarcodeStudio.ico'))
function Label($text,$x,$y,$width,$height) {
    $c=New-Object Windows.Forms.Label
    $c.Text=$text;$c.Location=New-Object Drawing.Point($x,$y);$c.Size=New-Object Drawing.Size($width,$height)
    $form.Controls.Add($c)
    return $c
}
$title=Label 'Install Barcode Studio' 25 22 570 38
$title.Font=New-Object Drawing.Font('Segoe UI',20,[Drawing.FontStyle]::Bold)
$subtitle=Label 'Import Excel, preview your labels and print to your TSC TE200.' 27 69 570 32
$instructions=Label 'Connect and switch on the TE200. Setup reuses compatible Python or downloads it from python.org, installs app dependencies, and checks the connected printer driver through Windows Update.' 27 109 570 67
$folderLabel=Label 'Install location' 27 185 560 25
$folder=New-Object Windows.Forms.TextBox
$folder.Location=New-Object Drawing.Point(27,214);$folder.Size=New-Object Drawing.Size(465,28)
$folder.Text=Join-Path $env:LOCALAPPDATA 'BarcodeStudio'
$form.Controls.Add($folder)
$browse=New-Object Windows.Forms.Button
$browse.Text='Browse...';$browse.Location=New-Object Drawing.Point(503,212);$browse.Size=New-Object Drawing.Size(95,32)
$form.Controls.Add($browse)
$browse.Add_Click({
    $dialog=New-Object Windows.Forms.FolderBrowserDialog
    $dialog.Description='Choose the folder for Barcode Studio and any downloaded Python runtime'
    $dialog.SelectedPath=$folder.Text
    if($dialog.ShowDialog() -eq [Windows.Forms.DialogResult]::OK){$folder.Text=$dialog.SelectedPath}
    $dialog.Dispose()
})
$status=Label 'Ready. Internet is used only when components are missing.' 27 258 570 40
$progress=New-Object Windows.Forms.ProgressBar
$progress.Location=New-Object Drawing.Point(27,304);$progress.Size=New-Object Drawing.Size(570,18)
$form.Controls.Add($progress)
$details=New-Object Windows.Forms.TextBox
$details.Location=New-Object Drawing.Point(27,337);$details.Size=New-Object Drawing.Size(570,135)
$details.Multiline=$true;$details.ReadOnly=$true;$details.ScrollBars='Vertical'
$details.Text='Windows administrator approval may be needed for printer driver installation. No calibration checkboxes are required. Your products and saved media dimensions are preserved.'
$form.Controls.Add($details)
$install=New-Object Windows.Forms.Button
$install.Text='Install';$install.Location=New-Object Drawing.Point(377,491);$install.Size=New-Object Drawing.Size(106,35)
$form.Controls.Add($install)
$close=New-Object Windows.Forms.Button
$close.Text='Close';$close.Location=New-Object Drawing.Point(494,491);$close.Size=New-Object Drawing.Size(104,35)
$form.Controls.Add($close)
$close.Add_Click({$form.Close()})
$timer=New-Object Windows.Forms.Timer
$timer.Interval=500
$install.Add_Click({
    if($script:finished){
        $shortcut=Join-Path $desktop 'Barcode Studio.lnk'
        if(Test-Path -LiteralPath $shortcut){Invoke-Item -LiteralPath $shortcut}
        $form.Close();return
    }
    try {
        if(-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64' -or $env:PROCESSOR_ARCHITEW6432 -eq 'ARM64'){throw 'This installer requires Windows 10/11 x64.'}
        if([Environment]::OSVersion.Version.Major -lt 10){throw 'Windows 10 or Windows 11 is required.'}
        $chosen=[IO.Path]::GetFullPath($folder.Text.Trim())
        if($chosen.StartsWith('\\')){throw 'Choose a local drive, not a network share.'}
        $driveRoot=[IO.Path]::GetPathRoot($chosen)
        if($chosen.TrimEnd('\') -eq $driveRoot.TrimEnd('\')){throw 'Choose an application folder rather than the root of a drive.'}
        if((New-Object IO.DriveInfo($driveRoot)).AvailableFreeSpace -lt 786432000){throw 'At least 750 MB of free space is required on the selected drive.'}
        New-Item -ItemType Directory -Force -Path $chosen | Out-Null
        $test=Join-Path $chosen ('.setup-write-'+[guid]::NewGuid().ToString('N'))
        [IO.File]::WriteAllText($test,'test');Remove-Item -LiteralPath $test
        $env:BARCODE_INSTALL_ROOT=$chosen
        $env:BARCODE_DOWNLOAD_PRINTER='1'
        $env:BARCODE_NO_LAUNCH='1'
        $env:BARCODE_SETUP_ICON=Join-Path $root 'BarcodeStudio.ico'
        $logs=Join-Path $env:LOCALAPPDATA 'BarcodeStudio\setup-logs'
        New-Item -ItemType Directory -Force -Path $logs | Out-Null
        $stamp=Get-Date -Format 'yyyyMMdd-HHmmss-fff'
        $script:outLog=Join-Path $logs ($stamp+'.out.log')
        $script:errLog=Join-Path $logs ($stamp+'.err.log')
        $code='$ErrorActionPreference="Stop";$t=[IO.File]::ReadAllText($env:BARCODE_SETUP_FILE);$m="# BARCODE_POWERSHELL_BEGIN";&([scriptblock]::Create($t.Substring($t.LastIndexOf($m)+$m.Length)))'
        $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($code))
        $ps=Join-Path $env:SystemRoot 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $script:engine=Start-Process -FilePath $ps -ArgumentList @('-NoLogo','-NoProfile','-STA','-EncodedCommand',$encoded) -WindowStyle Hidden -RedirectStandardOutput $script:outLog -RedirectStandardError $script:errLog -PassThru
        $install.Enabled=$false;$browse.Enabled=$false;$folder.Enabled=$false;$close.Enabled=$false
        $progress.Style='Marquee';$status.Text='Installing. Approve a Windows driver prompt if one appears.'
        $timer.Start()
    } catch {
        [Windows.Forms.MessageBox]::Show($_.Exception.Message+"`r`nChoose a writable folder in your account, or run Setup as administrator if your chosen folder requires it.",'Barcode Studio Setup','OK','Error') | Out-Null
    }
})
$timer.Add_Tick({
    try {
        if(Test-Path -LiteralPath $script:outLog){$details.Text=(@(Get-Content -LiteralPath $script:outLog -Tail 8 -ErrorAction SilentlyContinue) -join "`r`n")}
        if(-not $script:engine.HasExited){return}
        $timer.Stop();$script:engine.WaitForExit();$script:engine.Refresh();$progress.Style='Blocks';$progress.Value=100
        $close.Enabled=$true
        if($script:engine.ExitCode -eq 0){
            $script:finished=$true
            $status.Text='App installation complete. Your desktop shortcut is ready.'
            $install.Text='Open app';$install.Enabled=$true
            $pending=@(Select-String -LiteralPath $script:outLog -Pattern 'PRINTER PENDING' -ErrorAction SilentlyContinue)
            if($pending.Count -gt 0){$status.Text='App installed. Printer setup needs attention.';$details.Text=$pending[-1].Line+"`r`nLog: "+$script:outLog}
        } else {
            $status.Text='Setup needs attention. Read the details and retry.'
            $details.Text+= "`r`n"+(@(Get-Content -LiteralPath $script:errLog -Tail 8 -ErrorAction SilentlyContinue) -join "`r`n")+"`r`nLog: "+$script:outLog
            $install.Enabled=$true;$browse.Enabled=$true;$folder.Enabled=$true
        }
    } catch {$timer.Stop();$close.Enabled=$true;$status.Text=$_.Exception.Message}
})
$form.Add_FormClosing({param($sender,$event) if($script:engine -and -not $script:engine.HasExited){$event.Cancel=$true;[Windows.Forms.MessageBox]::Show('Installation is still running. Please wait for it to finish.','Barcode Studio Setup')|Out-Null}})
[void]$form.ShowDialog()
$timer.Dispose();$form.Dispose()
