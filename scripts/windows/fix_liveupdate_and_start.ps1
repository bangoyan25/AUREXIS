# Remove pending liveupdate folder so MT5 doesn't exit immediately to update
$lu = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\liveupdate"
if(Test-Path $lu) {
    Remove-Item -Path $lu -Recurse -Force
    Write-Output "Removed pending liveupdate folder"
} else {
    Write-Output "No liveupdate folder found"
}

# Now launch MT5 directly
$mt5 = "C:\Program Files\MetaTrader 5\terminal64.exe"
$proc = Start-Process -FilePath $mt5 -PassThru
Start-Sleep -Seconds 5
$running = Get-Process terminal64 -ErrorAction SilentlyContinue
Write-Output "terminal64 running: $($running -ne $null)"
if($running) {
    Write-Output "PID: $($running.Id)"
}
