param([string]$cmd)
$key = "C:\Users\sofya\Downloads\AUREXIS\ssh-key-2026-09-08.key"
& ssh -o StrictHostKeyChecking=no -i $key ubuntu@129.225.33.77 "$cmd"
