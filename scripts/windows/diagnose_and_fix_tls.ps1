<#
.SYNOPSIS
    Diagnose and Fix Windows Server 2019 TLS & MT5 WebSocket Environment.
#>

param (
    [string]$TargetHost = "app.aurexis.web.id",
    [int]$TargetPort = 443
)

$ErrorActionPreference = "Continue"

Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  AUREXIS TLS & SCHANNEL DIAGNOSTIC FOR WINDOWS SERVER  " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

# 1. DNS Resolution
Write-Host "`n[1/8] DNS Resolution for $TargetHost..." -ForegroundColor Yellow
try {
    $dns = [System.Net.Dns]::GetHostAddresses($TargetHost)
    foreach ($addr in $dns) {
        Write-Host "  IP: $($addr.IPAddressToString)" -ForegroundColor Green
    }
} catch {
    Write-Host "  DNS failed: $_" -ForegroundColor Red
}

# 2. TCP Port Connectivity
Write-Host "`n[2/8] Testing TCP connectivity to ${TargetHost}:${TargetPort}..." -ForegroundColor Yellow
$tcpTest = Test-NetConnection -ComputerName $TargetHost -Port $TargetPort -WarningAction SilentlyContinue
Write-Host "  TcpTestSucceeded: $($tcpTest.TcpTestSucceeded)" -ForegroundColor $(if ($tcpTest.TcpTestSucceeded) { "Green" } else { "Red" })

# 3. Native Windows TLS Handshake via .NET SslStream
Write-Host "`n[3/8] Testing native SChannel TLS 1.2 handshake via SslStream..." -ForegroundColor Yellow
try {
    $tcp = New-Object System.Net.Sockets.TcpClient($TargetHost, $TargetPort)
    $ssl = New-Object System.Net.Security.SslStream($tcp.GetStream(), $false)
    $ssl.AuthenticateAsClient($TargetHost, $null, [System.Security.Authentication.SslProtocols]::Tls12, $true)
    Write-Host "  TLS Handshake: SUCCESS" -ForegroundColor Green
    Write-Host "  Protocol: $($ssl.SslProtocol)"
    Write-Host "  Cipher: $($ssl.CipherAlgorithm) ($($ssl.CipherStrength) bits)"
    Write-Host "  KeyExchange: $($ssl.KeyExchangeAlgorithm)"
    Write-Host "  Cert Subject: $($ssl.RemoteCertificate.Subject)"
    Write-Host "  Cert Issuer: $($ssl.RemoteCertificate.Issuer)"
    $ssl.Close()
    $tcp.Close()
} catch {
    Write-Host "  TLS Handshake FAILED: $_" -ForegroundColor Red
}

# 4. Check Root Certificate Store for ISRG Root X1 / X2
Write-Host "`n[4/8] Checking Trusted Root CAs (ISRG Root X1 / X2)..." -ForegroundColor Yellow
$x1 = Get-ChildItem -Path Cert:\LocalMachine\Root | Where-Object { $_.Subject -match "ISRG Root X1" }
if ($x1) {
    Write-Host "  ISRG Root X1: PRESENT (Thumbprint: $($x1.Thumbprint))" -ForegroundColor Green
} else {
    Write-Host "  ISRG Root X1: MISSING! Downloading and installing..." -ForegroundColor Red
    try {
        $x1_der = (New-Object System.Net.WebClient).DownloadData("https://letsencrypt.org/certs/isrgrootx1.der")
        $cert1 = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2(,$x1_der)
        $store = New-Object System.Security.Cryptography.X509Certificates.X509Store([System.Security.Cryptography.X509Certificates.StoreName]::Root, [System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine)
        $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
        $store.Add($cert1)
        $store.Close()
        Write-Host "  ISRG Root X1: INSTALLED" -ForegroundColor Green
    } catch {
        Write-Host "  Failed to install ISRG Root X1: $_" -ForegroundColor Red
    }
}

$x2 = Get-ChildItem -Path Cert:\LocalMachine\Root | Where-Object { $_.Subject -match "ISRG Root X2" }
if ($x2) {
    Write-Host "  ISRG Root X2: PRESENT (Thumbprint: $($x2.Thumbprint))" -ForegroundColor Green
} else {
    Write-Host "  ISRG Root X2: MISSING! Downloading and installing..." -ForegroundColor Red
    try {
        $x2_der = (New-Object System.Net.WebClient).DownloadData("https://letsencrypt.org/certs/isrg-root-x2.der")
        $cert2 = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2(,$x2_der)
        $store = New-Object System.Security.Cryptography.X509Certificates.X509Store([System.Security.Cryptography.X509Certificates.StoreName]::Root, [System.Security.Cryptography.X509Certificates.StoreLocation]::LocalMachine)
        $store.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
        $store.Add($cert2)
        $store.Close()
        Write-Host "  ISRG Root X2: INSTALLED" -ForegroundColor Green
    } catch {
        Write-Host "  Failed to install ISRG Root X2: $_" -ForegroundColor Red
    }
}

# 5. Check SChannel TLS 1.2 Client Registry Settings
Write-Host "`n[5/8] Checking SChannel TLS 1.2 client configuration..." -ForegroundColor Yellow
$tls12Proto = "HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.2"
$tls12Path = "HKLM:\SYSTEM\CurrentControlSet\Control\SecurityProviders\SCHANNEL\Protocols\TLS 1.2\Client"
try {
    if (-not (Test-Path $tls12Proto)) { New-Item -Path $tls12Proto -Force | Out-Null }
    if (-not (Test-Path $tls12Path)) { New-Item -Path $tls12Path -Force | Out-Null }
    Set-ItemProperty -Path $tls12Path -Name "DisabledByDefault" -Value 0 -Type DWord -ErrorAction SilentlyContinue
    Set-ItemProperty -Path $tls12Path -Name "Enabled" -Value 1 -Type DWord -ErrorAction SilentlyContinue
    Write-Host "  TLS 1.2 Client: ENABLED in SChannel registry" -ForegroundColor Green
} catch {
    Write-Host "  Registry update requires admin privileges: $_" -ForegroundColor Yellow
}

# 6. SChannel System Event Log Inspection
Write-Host "`n[6/8] Recent SChannel System Events (last 10)..." -ForegroundColor Yellow
$schEvents = Get-WinEvent -LogName System -MaxEvents 200 -ErrorAction SilentlyContinue |
    Where-Object { $_.ProviderName -match 'Schannel' } |
    Select-Object -First 10 TimeCreated,Id,LevelDisplayName,Message
if ($schEvents) {
    foreach ($ev in $schEvents) {
        Write-Host "  [$($ev.TimeCreated)] ID $($ev.Id) ($($ev.LevelDisplayName)): $($ev.Message)"
    }
} else {
    Write-Host "  No recent Schannel error events." -ForegroundColor Green
}

# 7. Check MT5 Terminal Process
Write-Host "`n[7/8] MT5 terminal64 process status..." -ForegroundColor Yellow
$mt5 = Get-Process terminal64 -ErrorAction SilentlyContinue
if ($mt5) {
    Write-Host "  terminal64: RUNNING (PID $($mt5.Id), Path: $($mt5.Path))" -ForegroundColor Green
} else {
    Write-Host "  terminal64: NOT RUNNING" -ForegroundColor Yellow
}

# 8. Test HTTP/TLS via curl.exe
Write-Host "`n[8/8] Testing curl.exe -Iv https://$TargetHost/..." -ForegroundColor Yellow
$curlOut = & curl.exe -s -Iv "https://$TargetHost/" 2>&1
$curlHead = $curlOut | Select-String "HTTP/|schannel:" | Select-Object -First 6
foreach ($line in $curlHead) {
    Write-Host "  $line"
}

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host "  DIAGNOSIS & PROVISIONING COMPLETE" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan
