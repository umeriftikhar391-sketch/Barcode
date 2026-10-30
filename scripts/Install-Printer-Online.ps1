# Runs only with explicit Windows administrator approval from the app installer.
$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Windows.Forms
$devices=@(Get-PnpDevice -PresentOnly | Where-Object {$_.FriendlyName -match '(?i)TE200' -or $_.InstanceId -match '(?i)TE200'})
$hardware=New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach($device in $devices){
    foreach($key in @('DEVPKEY_Device_HardwareIds','DEVPKEY_Device_CompatibleIds')){
        $property=Get-PnpDeviceProperty -InstanceId $device.InstanceId -KeyName $key -ErrorAction SilentlyContinue
        foreach($id in @($property.Data)){if($id){[void]$hardware.Add([string]$id)}}
    }
}
if($hardware.Count -eq 0){throw 'No connected TE200 hardware was identified. Connect and power on the printer, then rerun Setup.'}
$session=New-Object -ComObject Microsoft.Update.Session
$session.ClientApplicationID='Barcode Studio Setup'
$search=$session.CreateUpdateSearcher()
# Windows Update selects compatible, signed driver candidates for this Windows PC.
$result=$search.Search("IsInstalled=0 and Type='Driver' and IsHidden=0")
$collection=New-Object -ComObject Microsoft.Update.UpdateColl
$seen=New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
foreach($update in $result.Updates){
    if(-not $hardware.Contains([string]$update.DriverHardwareID)){continue}
    $id=[string]$update.DriverHardwareID
    if($seen.Contains($id)){continue}
    if(-not $update.EulaAccepted){
        $answer=[Windows.Forms.MessageBox]::Show($update.Title+"`r`n`r`n"+$update.EulaText+"`r`n`r`nAccept the license and install this driver?",'Printer driver license','YesNo','Question')
        if($answer -ne [Windows.Forms.DialogResult]::Yes){continue}
        $update.AcceptEula()
    }
    [void]$collection.Add($update);[void]$seen.Add($id)
}
if($collection.Count -eq 0){throw 'Windows Update has no compatible TE200 driver available for this connected device. The app is installed; an official TSC driver or captured driver bundle is needed.'}
$downloader=$session.CreateUpdateDownloader();$downloader.Updates=$collection
$download=$downloader.Download()
if($download.ResultCode -notin @(2,3)){throw 'Windows Update could not download the printer driver.'}
$installer=$session.CreateUpdateInstaller();$installer.Updates=$collection
$installed=$installer.Install()
for($i=0;$i -lt $collection.Count;$i++){if($installed.GetUpdateResult($i).ResultCode -ne 2){throw 'Windows Update did not complete the printer driver installation.'}}
pnputil.exe /scan-devices | Out-Null
if($LASTEXITCODE -ne 0){throw 'Windows device rescan failed.'}
if($installed.RebootRequired){Write-Host 'Windows reports a restart is required for the printer driver.'}
Write-Host 'Compatible printer driver installed by Windows Update.'
