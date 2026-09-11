$mt5 = "C:\Program Files\MetaTrader 5\terminal64.exe"
Write-Output "MT5 exists: $(Test-Path $mt5)"
if(Test-Path $mt5) {
    Write-Output "MT5 path: $mt5"
    $proc = Start-Process -FilePath $mt5 -PassThru -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 3
    $still = Get-Process terminal64 -ErrorAction SilentlyContinue
    Write-Output "MT5 running: $($still -ne $null)"
    if($still) { Write-Output "PID: $($still.Id)" }
    else {
        $err = $Error[0]
        Write-Output "Error: $err"
    }
}
