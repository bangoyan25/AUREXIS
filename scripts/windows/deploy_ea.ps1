# Upload updated AurexisAgent.mq5 to Windows VPS and recompile it
$content = Get-Content "c:\Users\sofya\Downloads\AUREXIS\mt5\Experts\AurexisAgent.mq5" -Raw
$bytes = [System.Text.Encoding]::UTF8.GetBytes($content)
$b64 = [System.Convert]::ToBase64String($bytes)

$info = Get-Content "c:\Users\sofya\Downloads\AUREXIS\VPS_INFO.md" -Raw
$passMatch = [regex]::Match($info, "Password\s*:\s*(.+)")
$password = $passMatch.Groups[1].Value.Trim()
$sec = ConvertTo-SecureString $password -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential("Administrator", $sec)

Invoke-Command -ComputerName "103.67.244.220" -Credential $cred -ScriptBlock {
    param($b64Data)
    $bytes = [System.Convert]::FromBase64String($b64Data)
    $content = [System.Text.Encoding]::UTF8.GetString($bytes)
    
    $mq5Path = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\MQL5\Experts\AurexisAgent.mq5"
    [System.IO.File]::WriteAllText($mq5Path, $content, [System.Text.Encoding]::UTF8)
    Write-Output "Written $mq5Path ($($content.Length) chars)"
    
    # Recompile
    $metaeditor = "C:\Program Files\MetaTrader 5\metaeditor64.exe"
    $proc = Start-Process -FilePath $metaeditor -ArgumentList "/compile:`"$mq5Path`" /log" -PassThru -Wait
    Start-Sleep -Seconds 3
    
    # Read compiler log
    $log = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075\logs\metaeditor.log"
    if(Test-Path $log) {
        Get-Content $log -Tail 5
    }
} -ArgumentList $b64
