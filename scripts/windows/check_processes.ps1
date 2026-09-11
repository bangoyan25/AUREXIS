Get-Process | Where-Object { $_.ProcessName -match "update|terminal" } | Select-Object Id, ProcessName
Write-Output "---"
Get-Process -Name "terminal64" -ErrorAction SilentlyContinue | Select-Object Id, ProcessName
