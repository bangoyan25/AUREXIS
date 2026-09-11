$logs = Get-ChildItem "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\logs\*.log" | Sort-Object LastWriteTime -Descending | Select-Object -First 1
Write-Output "Latest log: $($logs.FullName)"
Get-Content $logs.FullName -Tail 25
$crashes = Get-ChildItem "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\crash\*" -ErrorAction SilentlyContinue
if($crashes) {
    Write-Output "Crashes found:"
    $crashes | Select-Object Name, LastWriteTime
}
