Write-Host "Stopping terminal64..." -ForegroundColor Yellow
Stop-Process -Name "terminal64" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

Write-Host "Starting StartMT5 scheduled task..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName "StartMT5"
Start-Sleep -Seconds 5

$proc = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "MT5 Terminal restarted successfully (PID: $($proc.Id), SessionId: $($proc.SessionId))." -ForegroundColor Green
} else {
    Write-Host "WARNING: terminal64 process not detected yet!" -ForegroundColor Red
}
