# Run remote command or script on Windows VPS via WinRM
param(
    [string]$ScriptText = "",
    [string]$FilePath = "",
    [array]$ArgumentList = @()
)

$info = Get-Content "c:\Users\sofya\Downloads\AUREXIS\VPS_INFO.md" -Raw
$passMatch = [regex]::Match($info, "Password\s*:\s*(.+)")
if (-not $passMatch.Success) {
    Write-Error "Password not found in VPS_INFO.md"
    exit 1
}
$password = $passMatch.Groups[1].Value.Trim()

$sec = ConvertTo-SecureString $password -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential("Administrator", $sec)

if ($FilePath) {
    Invoke-Command -ComputerName "103.67.244.220" -Credential $cred -FilePath $FilePath -ArgumentList $ArgumentList
} else {
    $sb = [ScriptBlock]::Create($ScriptText)
    Invoke-Command -ComputerName "103.67.244.220" -Credential $cred -ScriptBlock $sb -ArgumentList $ArgumentList
}

