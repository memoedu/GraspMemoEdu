#Requires -Version 7.0
[CmdletBinding(DefaultParameterSetName = 'Install')]
param(
    [Parameter(ParameterSetName = 'Install')][int]$IntervalMinutes = 60,
    [string]$Config = 'D:\AppData\GraspMemoEduHydro\sync\config.json',
    [string]$HiddenRunner = 'D:\Projects\DeveloperGovernance\run-hidden.pyw',
    [Parameter(Mandatory, ParameterSetName = 'Update')][switch]$UpdateActionOnly
)
$ErrorActionPreference = 'Stop'
if ($IntervalMinutes -lt 15) { throw 'Synchronization interval must be at least 15 minutes.' }
$taskName = 'SUSTech-CS109-OJ-Sync'
$script = Join-Path $PSScriptRoot 'Sync-Hydro.ps1'
$existing = Get-ScheduledTask -TaskName $taskName -TaskPath '\' -ErrorAction SilentlyContinue
if ($existing -and ($existing.Actions.Count -ne 1 -or
    -not ([string]$existing.Actions[0].Arguments).Contains(('"' + $script + '"'), [StringComparison]::OrdinalIgnoreCase))) {
    throw 'The existing task belongs to another application.'
}
if ($UpdateActionOnly) {
    if (-not $existing) { throw 'The scheduled task must exist to update its action.' }
    if (-not $PSBoundParameters.ContainsKey('Config')) {
        if ($existing.Actions[0].Arguments -notmatch '(?:^|\s)-Config\s+"([^"]+)"(?:\s|$)') {
            throw 'Specify the existing configuration path with -Config.'
        }
        $Config = $Matches[1]
    }
}
if (-not (Test-Path -LiteralPath $Config -PathType Leaf)) { throw 'Complete the account binding before scheduling.' }
$Config = (Resolve-Path -LiteralPath $Config).Path
$pythonw = 'D:\AppData\GraspMemoEdu\venv\Scripts\pythonw.exe'
$pwsh = (Get-Command pwsh.exe -CommandType Application -ErrorAction Stop | Select-Object -First 1).Source
foreach ($file in @($pythonw, $HiddenRunner, $script)) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing task runtime: $file" }
}
$HiddenRunner = (Resolve-Path -LiteralPath $HiddenRunner).Path
$arguments = '"{0}" --no-timeout -- "{1}" -NoLogo -NoProfile -NonInteractive -WindowStyle Hidden -File "{2}" -Config "{3}"' -f $HiddenRunner, $pwsh, $script, $Config
$action = New-ScheduledTaskAction -Execute $pythonw -Argument $arguments -WorkingDirectory $PSScriptRoot
if ($UpdateActionOnly) {
    Set-ScheduledTask -TaskName $taskName -TaskPath '\' -Action $action | Out-Null
    Write-Output ('Updated Windows scheduled task action: ' + $taskName)
    return
}
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$triggers = @((New-ScheduledTaskTrigger -AtLogOn -User $user), (New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes $IntervalMinutes)))
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 45) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)
$principal = New-ScheduledTaskPrincipal -UserId $user -LogonType Interactive -RunLevel Limited
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $triggers -Settings $settings -Principal $principal -Description 'Read the CS109 OJ problem bank and this user submission/AC status, preserve learner source files, and synchronize the existing IDEA/GraspMemoEdu OJ catalog.' -Force | Out-Null
Write-Output ('Installed Windows scheduled task: ' + $taskName + '; every ' + $IntervalMinutes + ' minutes and at logon.')
