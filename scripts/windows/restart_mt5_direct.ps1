# Restart MT5 on VPS
$info = Get-Content "c:\Users\sofya\Downloads\AUREXIS\VPS_INFO.md" -Raw
$passMatch = [regex]::Match($info, "Password\s*:\s*(.+)")
$password = $passMatch.Groups[1].Value.Trim()
$sec = ConvertTo-SecureString $password -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential("Administrator", $sec)

Invoke-Command -ComputerName "103.67.244.220" -Credential $cred -ScriptBlock {
    # Kill running MT5
    Get-Process terminal64 -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 3
    
    # Start MT5
    $mt5 = "C:\Program Files\MetaTrader 5\terminal64.exe"
    Start-Process $mt5 -WindowStyle Normal
    Start-Sleep -Seconds 8
    
    $procs = Get-Process terminal64 -ErrorAction SilentlyContinue
    if($procs) {
        Write-Output "MT5 started: $($procs.Count) process(es)"
    } else {
        Write-Output "MT5 not detected yet"
    }
}
