# Deploy MT5 MQL5 files to Windows VPS and compile AurexisAgent.mq5 using MetaEditor64
$ErrorActionPreference = "Stop"

$info = Get-Content "c:\Users\sofya\Downloads\AUREXIS\VPS_INFO.md" -Raw
$passMatch = [regex]::Match($info, "Password\s*:\s*(.+)")
if (-not $passMatch.Success) {
    Write-Error "Password not found in VPS_INFO.md"
    exit 1
}
$password = $passMatch.Groups[1].Value.Trim()

$sec = ConvertTo-SecureString $password -AsPlainText -Force
$cred = New-Object System.Management.Automation.PSCredential("Administrator", $sec)

Write-Host "Creating PSSession to Windows VPS 103.67.244.220..." -ForegroundColor Cyan
$sess = New-PSSession -ComputerName "103.67.244.220" -Credential $cred

try {
    $remoteDataPath = "C:\Users\Administrator\AppData\Roaming\MetaQuotes\Terminal\D0E8209F77C8CF37AD8BF550E51FF075"
    $remoteInclude = "$remoteDataPath\MQL5\Include"
    $remoteExperts = "$remoteDataPath\MQL5\Experts"
    $remotePresets = "$remoteDataPath\MQL5\Presets"

    Write-Host "Ensuring remote directories exist..." -ForegroundColor Cyan
    Invoke-Command -Session $sess -ScriptBlock {
        param($inc, $exp, $pre)
        New-Item -ItemType Directory -Path $inc -Force | Out-Null
        New-Item -ItemType Directory -Path $exp -Force | Out-Null
        New-Item -ItemType Directory -Path $pre -Force | Out-Null
    } -ArgumentList $remoteInclude, $remoteExperts, $remotePresets

    Write-Host "Copying Include files..." -ForegroundColor Cyan
    Copy-Item -Path "c:\Users\sofya\Downloads\AUREXIS\mt5\Include\*" -Destination $remoteInclude -ToSession $sess -Recurse -Force

    Write-Host "Copying Experts files..." -ForegroundColor Cyan
    Copy-Item -Path "c:\Users\sofya\Downloads\AUREXIS\mt5\Experts\*" -Destination $remoteExperts -ToSession $sess -Recurse -Force

    Write-Host "Copying Presets files..." -ForegroundColor Cyan
    Copy-Item -Path "c:\Users\sofya\Downloads\AUREXIS\mt5\Presets\*" -Destination $remotePresets -ToSession $sess -Recurse -Force

    Write-Host "Compiling AurexisAgent.mq5 with MetaEditor64..." -ForegroundColor Cyan
    $compileResult = Invoke-Command -Session $sess -ScriptBlock {
        param($dataPath)
        $mq5Path = "$dataPath\MQL5\Experts\AurexisAgent.mq5"
        $logPath = "$dataPath\MQL5\Experts\compile.log"
        $editorPath = "C:\Program Files\MetaTrader 5\metaeditor64.exe"

        if (Test-Path $logPath) { Remove-Item $logPath -Force }

        $proc = Start-Process -FilePath $editorPath -ArgumentList "/compile:`"$mq5Path`"", "/log:`"$logPath`"" -PassThru -Wait
        Start-Sleep -Seconds 2

        $logContent = if (Test-Path $logPath) {
            # MetaEditor logs are typically UTF-16 LE
            Get-Content $logPath -Encoding Unicode -Raw
        } else {
            "NO_LOG_FILE_FOUND"
        }

        $ex5Path = "$dataPath\MQL5\Experts\AurexisAgent.ex5"
        $ex5Exists = Test-Path $ex5Path
        $ex5Info = if ($ex5Exists) { Get-Item $ex5Path | Select-Object Length, LastWriteTime } else { $null }

        return [PSCustomObject]@{
            ExitCode = $proc.ExitCode
            Log = $logContent
            Ex5Exists = $ex5Exists
            Ex5Length = if ($ex5Info) { $ex5Info.Length } else { 0 }
            Ex5Time = if ($ex5Info) { $ex5Info.LastWriteTime } else { $null }
        }
    } -ArgumentList $remoteDataPath

    Write-Host "MetaEditor Exit Code: $($compileResult.ExitCode)"
    Write-Host "MetaEditor Log:`n$($compileResult.Log)"
    Write-Host "AurexisAgent.ex5 exists: $($compileResult.Ex5Exists) (Size: $($compileResult.Ex5Length) bytes, Time: $($compileResult.Ex5Time))"

    if (-not $compileResult.Ex5Exists) {
        throw "Compilation failed! AurexisAgent.ex5 was not generated."
    }
}
finally {
    Remove-PSSession $sess
}
