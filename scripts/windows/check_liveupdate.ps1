$lu = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\liveupdate"
if(Test-Path $lu) {
    Write-Output "Liveupdate contents:"
    Get-ChildItem $lu
} else {
    Write-Output "No liveupdate folder"
}

# Check most recent terminal log
$log = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\logs\20260911.log"
if(Test-Path $log) {
    Write-Output "Last 10 lines of today's log:"
    Get-Content $log -Tail 10
}
