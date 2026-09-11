$lu = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\liveupdate"
$main = "C:\Program Files\MetaTrader 5"
Write-Output "Liveupdate folder:"
Get-ChildItem $lu -ErrorAction SilentlyContinue | Select-Object Name, LastWriteTime
Write-Output "Main terminal64.exe:"
Get-Item "$main\terminal64.exe" -ErrorAction SilentlyContinue | Select-Object Name, LastWriteTime, Length
