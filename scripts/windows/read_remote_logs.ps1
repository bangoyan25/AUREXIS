$dataPath = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"

$mqlLogs = Get-ChildItem "$dataPath\MQL5\Logs" -Filter "*.log" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^\d{8}\.log$' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($mqlLogs) {
    Write-Host "=== MQL5 EXPERTS LOG: $($mqlLogs.Name) ===" -ForegroundColor Cyan
    Get-Content $mqlLogs.FullName -Encoding Unicode -Tail 30
}

$termLogs = Get-ChildItem "$dataPath\Logs" -Filter "*.log" -ErrorAction SilentlyContinue | Where-Object { $_.Name -match '^\d{8}\.log$' } | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if ($termLogs) {
    Write-Host "`n=== TERMINAL LOG: $($termLogs.Name) ===" -ForegroundColor Cyan
    Get-Content $termLogs.FullName -Encoding Unicode -Tail 30
}

