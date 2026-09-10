$dataPath = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"
$setFile = "$dataPath\MQL5\Presets\AurexisAgent.set"
$chrFile = "$dataPath\MQL5\Profiles\Charts\Default\chart01.chr"

Write-Host "Stopping terminal64..." -ForegroundColor Yellow
Stop-Process -Name "terminal64" -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 3

Write-Host "Reading presets from $setFile..." -ForegroundColor Cyan
$setContent = Get-Content $setFile -Raw
$agentIdMatch = [regex]::Match($setContent, "(?m)^InpAgentId=(.+)$")
$secretMatch = [regex]::Match($setContent, "(?m)^InpAgentSecret=(.+)$")

if (-not $agentIdMatch.Success -or -not $secretMatch.Success) {
    throw "Could not extract credentials from AurexisAgent.set"
}

$agentId = $agentIdMatch.Groups[1].Value.Trim()
$secret = $secretMatch.Groups[1].Value.Trim()

Write-Host "Patching $chrFile..." -ForegroundColor Cyan
$chrContent = Get-Content $chrFile -Raw
$chrContent = $chrContent -replace '(?m)^InpAgentId=.*$', "InpAgentId=$agentId"
$chrContent = $chrContent -replace '(?m)^InpAgentSecret=.*$', "InpAgentSecret=$secret"
$chrContent = $chrContent -replace '(?m)^InpBackendHost=.*$', "InpBackendHost=app.aurexis.web.id"
$chrContent = $chrContent -replace '(?m)^InpBackendPort=.*$', "InpBackendPort=443"
Set-Content -Path $chrFile -Value $chrContent -Encoding UTF8 -NoNewline

Write-Host "Starting StartMT5 scheduled task..." -ForegroundColor Cyan
Start-ScheduledTask -TaskName "StartMT5"
Start-Sleep -Seconds 6

$p = Get-Process "terminal64" -ErrorAction SilentlyContinue
if ($p) {
    Write-Host "Terminal running successfully (PID: $($p.Id))" -ForegroundColor Green
} else {
    Write-Host "WARNING: terminal64 process not detected!" -ForegroundColor Red
}
