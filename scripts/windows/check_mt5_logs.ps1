$logPath = "$env:APPDATA\MetaQuotes\Terminal"
Get-ChildItem -Path $logPath -Recurse -Filter "*.log" -ErrorAction SilentlyContinue | 
    Sort-Object LastWriteTime -Descending | 
    Select-Object -First 5 |
    ForEach-Object { 
        Write-Output "=== $($_.FullName)"
        Get-Content $_.FullName -Tail 20 -ErrorAction SilentlyContinue 
    }
