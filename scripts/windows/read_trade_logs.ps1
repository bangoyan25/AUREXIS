$today = Get-Date -Format "yyyyMMdd"
$log1 = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\logs\$today.log"
$log2 = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\logs\$today.log"

Write-Output "=== TERMINAL LOG ==="
if(Test-Path $log1) {
    Get-Content $log1 | Select-String -Pattern "58402254872|58402254901|58030466265|58030466297|deal|order" | Select-Object -Last 10
}
Write-Output "=== MQL5 LOG ==="
if(Test-Path $log2) {
    Get-Content $log2 | Select-String -Pattern "58402254872|58402254901|OPEN_POSITION|CLOSE_POSITION|OrderSend|result" | Select-Object -Last 10
}
