<#
.SYNOPSIS
    FlashDock Windows Authenticode Digital Signing Script.
.DESCRIPTION
    Creates or retrieves a trusted local code-signing certificate and signs
    FlashDock.exe with SHA-256. Exports public certificate for SmartScreen / SAC trust.
#>

param(
    [string]$TargetExe = "$PSScriptRoot\..\dist\FlashDock_Dist\FlashDock.exe",
    [string]$ExportCertPath = "$PSScriptRoot\..\dist\FlashDock_Dist\FlashDock-Security-Certificate.cer"
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  FlashDock Authenticode Code-Signing Pipeline" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

if (-not (Test-Path $TargetExe)) {
    Write-Warning "Target binary not found: $TargetExe"
    exit 1
}

$certSubject = "CN=FlashDock Workstation Authority, O=Klein Systems, C=US"
$cert = Get-ChildItem -Path "Cert:\CurrentUser\My" -Recurse -ErrorAction SilentlyContinue |
    Where-Object { $_.Subject -eq $certSubject } |
    Select-Object -First 1

if (-not $cert) {
    Write-Host "[*] Generating dedicated local Code-Signing Certificate..." -ForegroundColor Yellow
    $cert = New-SelfSignedCertificate `
        -Type CodeSigningCert `
        -Subject $certSubject `
        -CertStoreLocation "Cert:\CurrentUser\My" `
        -KeyUsage DigitalSignature `
        -FriendlyName "FlashDock Workstation Authenticode Certificate" `
        -NotAfter (Get-Date).AddYears(5)
    Write-Host "  [OK] Created certificate thumbprint: $($cert.Thumbprint)" -ForegroundColor Green
} else {
    Write-Host "[*] Found existing certificate thumbprint: $($cert.Thumbprint)" -ForegroundColor Green
}

# Export public certificate
$exportDir = [System.IO.Path]::GetDirectoryName($ExportCertPath)
if (-not (Test-Path $exportDir)) {
    New-Item -ItemType Directory -Path $exportDir -Force | Out-Null
}

Export-Certificate -Cert $cert -FilePath $ExportCertPath -Force | Out-Null
Write-Host "[OK] Public security certificate exported to: $ExportCertPath" -ForegroundColor Green

# Also export copy to project root dist
$distCertPath = "$PSScriptRoot\..\dist\FlashDock-Security-Certificate.cer"
if (Test-Path "$PSScriptRoot\..\dist") {
    Copy-Item $ExportCertPath $distCertPath -Force
}

# Sign binary
Write-Host "[*] Digitally signing executable: $TargetExe..." -ForegroundColor Yellow
try {
    # Attempt with public Digicert timestamp server first
    $sig = Set-AuthenticodeSignature -FilePath $TargetExe -Certificate $cert -HashAlgorithm SHA256 -TimestampServer "http://timestamp.digicert.com" -ErrorAction Stop
} catch {
    # Fallback to local SHA-256 signature without timestamp (offline mode)
    $sig = Set-AuthenticodeSignature -FilePath $TargetExe -Certificate $cert -HashAlgorithm SHA256
}

Write-Host "  [OK] Authenticode Signature Status: $($sig.Status)" -ForegroundColor Green
Write-Host "       Signer: $($sig.SignerCertificate.Subject)" -ForegroundColor Gray
Write-Host "==========================================================" -ForegroundColor Cyan
