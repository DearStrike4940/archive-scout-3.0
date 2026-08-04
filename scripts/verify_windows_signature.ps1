param(
    [string]$ApplicationPath = "release\ArchiveScout-Windows-x64\ArchiveScout\ArchiveScout.exe",
    [switch]$RequireSigned
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path $ApplicationPath)) { throw "Windows executable not found: $ApplicationPath" }
$Signature = Get-AuthenticodeSignature $ApplicationPath
$Report = @(
    "File: $ApplicationPath"
    "Status: $($Signature.Status)"
    "StatusMessage: $($Signature.StatusMessage)"
    "SignerCertificate: $($Signature.SignerCertificate.Subject)"
    "TimestampCertificate: $($Signature.TimeStamperCertificate.Subject)"
)
$Report | Set-Content "release\ArchiveScout-Windows-x64.signature.txt" -Encoding utf8
$Report | ForEach-Object { Write-Host $_ }
if ($RequireSigned -and $Signature.Status -ne "Valid") {
    throw "ArchiveScout.exe must have a valid Authenticode signature before packaging."
}
