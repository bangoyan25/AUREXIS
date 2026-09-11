# Create scheduled task to run MT5 interactively as SYSTEM/Administrator in user session
$action = New-ScheduledTaskAction -Execute "C:\Program Files\MetaTrader 5\terminal64.exe"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Hours 24) -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
$principal = New-ScheduledTaskPrincipal -UserId "Administrator" -LogonType Interactive -RunLevel Highest

# Remove old task if exists
Unregister-ScheduledTask -TaskName "StartMT5Interactive" -Confirm:$false -ErrorAction SilentlyContinue

Register-ScheduledTask -TaskName "StartMT5Interactive" -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force
Write-Output "Task registered"

Start-ScheduledTask -TaskName "StartMT5Interactive"
Start-Sleep -Seconds 8

$running = Get-ScheduledTaskInfo -TaskName "StartMT5Interactive"
Write-Output "Task last run time: $($running.LastRunTime)"
Write-Output "Task last result: $($running.LastTaskResult)"

$procs = Get-Process terminal64 -ErrorAction SilentlyContinue
Write-Output "terminal64 processes: $($procs.Count)"
