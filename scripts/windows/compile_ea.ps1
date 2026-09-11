param()
$src = "C:\Users\sofya\Downloads\AUREXIS\mt5\Experts\AurexisAgent.mq5"
$dst = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\AurexisAgent.mq5"
$dstEx5 = $dst.Replace(".mq5", ".ex5")
$localEx5 = $src.Replace(".mq5", ".ex5")

if(!(Test-Path $dst)) { New-Item -ItemType File -Force -Path $dst | Out-Null }
Copy-Item $src $dst -Force
Write-Output "Source uploaded to VPS"

$metaeditor = "C:\Program Files\MetaTrader 5\metaeditor64.exe"
if(Test-Path $metaeditor) {
    & $metaeditor /compile:$dst /log
    Start-Sleep -Seconds 8
    if(Test-Path $dstEx5) {
        Write-Output "Compilation succeeded"
        Write-Output "EX5 path: $dstEx5"
    } else {
        Write-Output "EX5 not found after compilation"
    }
} else {
    Write-Output "metaeditor64.exe not found at $metaeditor"
    $found = Get-ChildItem "C:\Program Files\MetaTrader*" -Filter "metaeditor64.exe" -Recurse -ErrorAction SilentlyContinue
    if($found) { Write-Output "Found at: $($found.FullName)" }
}
