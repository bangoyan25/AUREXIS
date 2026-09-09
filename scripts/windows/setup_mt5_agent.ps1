<#
.SYNOPSIS
    AUREXIS MT5 Agent Setup & Host Provisioning Script for Windows Server 2019.
.DESCRIPTION
    Installs AurexisAgent MQL5 files to MT5 data folder, configures common.ini,
    patches active chart .chr profile files with agent credentials,
    sets RDP session timeouts to prevent suspension, and registers Task Scheduler
    job for continuous agent execution.

    CREDENTIAL INJECTION STRATEGY:
    MT5 does NOT auto-apply .set files to an already-attached EA on a chart.
    Chart profile .chr files (MQL5\Profiles\Charts\<Profile>\chartNN.chr) hold
    the actual runtime EA input parameters. This script:
      1. Writes AurexisAgent.set with credentials (for manual Load use).
      2. Directly patches all .chr files that have AurexisAgent attached,
         injecting InpAgentId and InpAgentSecret into the <inputs> block.
      3. Stops and restarts MT5 when -RestartMT5 is passed so MT5 reads the
         patched .chr files fresh rather than overwriting them on shutdown.

    SECURITY:
    Credentials written to local VPS filesystem only (never git-tracked).
    Credentials never logged in full. default.set stays credential-free.
#>

param (
    [string]$AgentId = "",
    [string]$AgentSecret = "",
    [string]$BackendHost = "app.aurexis.web.id",
    [uint32]$BackendPort = 443,
    [uint32]$HeartbeatSec = 15,
    [string]$MT5InstallPath = "C:\Program Files\MetaTrader 5",
    [string]$DataPath = "",
    [switch]$RestartMT5 = $false
)

$ErrorActionPreference = "Stop"

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host " AUREXIS MT5 Agent Setup & Configuration" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

# 1. Resolve repository root
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
Write-Host "[1/6] Repository Root: $RepoRoot"

# 2. Locate MT5 Data Path
if (-not $DataPath) {
    $RoamingBase = Join-Path $env:APPDATA "MetaQuotes\Terminal"
    if (Test-Path $RoamingBase) {
        $Terminals = Get-ChildItem $RoamingBase -Directory | Where-Object { Test-Path (Join-Path $_.FullName "MQL5") }
        if ($Terminals) {
            $DataPath = $Terminals[0].FullName
        }
    }
}

if (-not $DataPath -or -not (Test-Path $DataPath)) {
    throw "MT5 Roaming Data Path not found. Run MT5 at least once or pass -DataPath explicitly."
}
Write-Host "[2/6] MT5 Roaming Data Path: $DataPath"

# 3. Copy MQL5 Files
$TargetInclude = Join-Path $DataPath "MQL5\Include"
$TargetExperts = Join-Path $DataPath "MQL5\Experts"
$TargetPresets = Join-Path $DataPath "MQL5\Presets"

New-Item -ItemType Directory -Path $TargetInclude -Force | Out-Null
New-Item -ItemType Directory -Path $TargetExperts -Force | Out-Null
New-Item -ItemType Directory -Path $TargetPresets -Force | Out-Null

Copy-Item (Join-Path $RepoRoot "mt5\Include\*") -Destination $TargetInclude -Recurse -Force
Copy-Item (Join-Path $RepoRoot "mt5\Experts\*") -Destination $TargetExperts -Recurse -Force
Copy-Item (Join-Path $RepoRoot "mt5\Presets\*") -Destination $TargetPresets -Recurse -Force

Write-Host "[3/6] MQL5 source files and binaries installed successfully."

# 4. Write credentialed AurexisAgent.set (local VPS configuration only)
if ($AgentId -and $AgentSecret) {
    $PresetFile = Join-Path $TargetPresets "AurexisAgent.set"
    $PresetContent = @"
InpBackendHost=$BackendHost
InpBackendPort=$BackendPort
InpAgentId=$AgentId
InpAgentSecret=$AgentSecret
InpHeartbeatSec=$HeartbeatSec
InpReconnectSec=5
InpSymbolMap=XAUUSD=XAUUSD
"@
    Set-Content -Path $PresetFile -Value $PresetContent -Encoding ASCII
    $tail = if ($AgentSecret.Length -ge 6) { $AgentSecret.Substring($AgentSecret.Length - 6) } else { "******" }
    Write-Host "[4/8] Configured agent preset: $PresetFile (secret: ...${tail})"
} else {
    Write-Host "[4/8] Credentials not provided; default.set installed without credentials." -ForegroundColor Yellow
}

# 5. Stop MT5 if RestartMT5 specified (must stop BEFORE patching .chr to prevent MT5 overwriting on exit)
if ($RestartMT5) {
    Write-Host "[5/8] Stopping MT5 (terminal64.exe) to prepare for chart credential injection..." -ForegroundColor Yellow
    $procs = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
    if ($procs) {
        $procs | ForEach-Object { $_.CloseMainWindow() | Out-Null }
        Start-Sleep -Seconds 3
        $procs = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
        if ($procs) {
            Stop-Process -Name "terminal64" -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 2
        }
        Write-Host "[5/8] MT5 stopped."
    } else {
        Write-Host "[5/8] MT5 not running."
    }
} else {
    Write-Host "[5/8] -RestartMT5 not passed; MT5 not stopped."
}

# 6. Patch chart profile .chr files with credentials
#    Live EA inputs live in MQL5\Profiles\Charts\<Profile>\chartNN.chr
if ($AgentId -and $AgentSecret) {
    $ChartsRoot = Join-Path $DataPath "MQL5\Profiles\Charts"
    $PatchedCount = 0
    if (Test-Path $ChartsRoot) {
        $ChrFiles = Get-ChildItem $ChartsRoot -Recurse -Filter "*.chr"
        foreach ($f in $ChrFiles) {
            $raw = Get-Content $f.FullName -Encoding UTF8 -Raw
            if ($raw -match 'name=AurexisAgent') {
                $raw = $raw -replace '(?m)^InpAgentId=.*$', "InpAgentId=$AgentId"
                $raw = $raw -replace '(?m)^InpAgentSecret=.*$', "InpAgentSecret=$AgentSecret"
                $raw = $raw -replace '(?m)^InpBackendHost=.*$', "InpBackendHost=$BackendHost"
                $raw = $raw -replace '(?m)^InpBackendPort=.*$', "InpBackendPort=$BackendPort"
                Set-Content -Path $f.FullName -Value $raw -Encoding UTF8 -NoNewline
                Write-Host "[6/8] Patched chart profile: $($f.FullName)"
                $PatchedCount++
            }
        }
    }
    if ($PatchedCount -eq 0) {
        Write-Host "[6/8] WARNING: No active .chr files found containing name=AurexisAgent." -ForegroundColor Yellow
    } else {
        Write-Host "[6/8] Patched $PatchedCount chart file(s) with agent credentials."
    }
} else {
    Write-Host "[6/8] Credentials not provided; chart files not patched." -ForegroundColor Yellow
}

# 7. Configure common.ini and Windows RDP
$CommonIni = Join-Path $DataPath "config\common.ini"
if (Test-Path $CommonIni) {
    $iniText = Get-Content $CommonIni -Encoding Unicode -Raw
    if ($iniText -match '\[Experts\]') {
        $iniText = $iniText -replace 'WebRequest=0', 'WebRequest=1'
        $iniText = $iniText -replace 'Enabled=0', 'Enabled=1'
        Set-Content -Path $CommonIni -Value $iniText -Encoding Unicode
        Write-Host "[7/8] Configured MT5 common.ini (WebRequest & AutoTrading enabled)."
    }
}

try {
    $RdpRegPath = "HKLM:\SYSTEM\CurrentControlSet\Control\Terminal Server\WinStations\RDP-Tcp"
    if (Test-Path $RdpRegPath) {
        Set-ItemProperty -Path $RdpRegPath -Name "MaxDisconnectionTime" -Value 0 -ErrorAction SilentlyContinue
        Set-ItemProperty -Path $RdpRegPath -Name "MaxIdleTime" -Value 0 -ErrorAction SilentlyContinue
        Set-ItemProperty -Path $RdpRegPath -Name "MaxConnectionTime" -Value 0 -ErrorAction SilentlyContinue
        Write-Host "[7/8] Windows Server RDP timeouts configured: 0 (Never disconnect)."
    }
} catch {
    Write-Host "[7/8] RDP registry update requires elevated privileges: $_" -ForegroundColor Yellow
}

# 8. Start MT5 if RestartMT5 was requested
if ($RestartMT5) {
    Write-Host "[8/8] Starting MT5 via StartMT5 scheduled task (Interactive Session)..." -ForegroundColor Cyan
    Start-ScheduledTask -TaskName "StartMT5" -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 4
    $running = Get-Process -Name "terminal64" -ErrorAction SilentlyContinue
    if ($running) {
        Write-Host "[8/8] MT5 restarted successfully (PID: $($running.Id))." -ForegroundColor Green
    } else {
        Write-Host "[8/8] WARNING: MT5 process not found. Check StartMT5 task." -ForegroundColor Yellow
    }
} else {
    Write-Host "[8/8] Done. Restart MT5 to load patched chart parameters."
}

Write-Host "=================================================" -ForegroundColor Green
Write-Host " Setup complete! MT5 Agent is ready to run." -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
