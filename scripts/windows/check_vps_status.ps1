$info = Get-Content "c:\Users\sofya\Downloads\AUREXIS\VPS_INFO.md" -Raw
$passMatch = [regex]::Match($info, "Password\s*:\s*(.+)")
$password = $passMatch.Groups[1].Value.Trim()
$sec = ConvertTo-SecureString $password -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential("Administrator", $sec)

Invoke-Command -ComputerName "103.67.244.220" -Credential $cred -ScriptBlock {
    $logDir = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Logs"
    $latest = Get-ChildItem $logDir -Filter "*.log" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($latest) {
        Write-Host "Latest Expert Log: $($latest.FullName)"
        Get-Content $latest.FullName -Tail 50
    }
}
