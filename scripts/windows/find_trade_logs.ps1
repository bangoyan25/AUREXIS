Get-ChildItem "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\logs\*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 3 | ForEach-Object {
    Write-Output "--- $($_.Name) ---"
    Get-Content $_.FullName | Select-String "order|deal|58402254872" | Select-Object -Last 10
}
