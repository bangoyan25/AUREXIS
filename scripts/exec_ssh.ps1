param(
    [Parameter(Mandatory=$true)]
    [string]$Command
)

$key = "C:\Users\sofya\Downloads\AUREXIS\ssh-key-2026-09-08.key"
$hostIp = "129.225.33.77"
& ssh -o BatchMode=yes -o ConnectTimeout=10 -o StrictHostKeyChecking=no -i $key "ubuntu@$hostIp" $Command
