param(
    [string]$PackageRoot = "release\ArchiveScout-Windows-x64",
    [string]$Output = "release\ArchiveScout-Windows-x64-defender-submission.zip"
)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$Exe = Join-Path $PackageRoot "ArchiveScout\ArchiveScout.exe"
if (-not (Test-Path $Exe)) { throw "ArchiveScout.exe was not found: $Exe" }
$Temp = Join-Path ([System.IO.Path]::GetTempPath()) ("archive-scout-defender-" + [guid]::NewGuid())
New-Item -ItemType Directory -Path $Temp | Out-Null
try {
    Copy-Item $Exe $Temp
    foreach ($file in @(
        "release\ArchiveScout-Windows-x64.signature.txt",
        "release\ArchiveScout-Windows-x64.files.sha256",
        "release\ArchiveScout-Windows-x64.spdx.json",
        "SOURCE_VALIDATION.txt"
    )) {
        if (Test-Path $file) { Copy-Item $file $Temp }
    }
    $Hash = (Get-FileHash $Exe -Algorithm SHA256).Hash.ToLower()
    @(
        "Archive Scout 3.0 Beta 1.3"
        "Submission category: Software developer / clean file incorrectly detected"
        "Reported detection: Trojan:Win32/Wacatac.C!ml"
        "ArchiveScout.exe SHA-256: $Hash"
        "Source repository: $env:GITHUB_SERVER_URL/$env:GITHUB_REPOSITORY"
        "The executable is a PyInstaller on-directory desktop client for public Wayback Machine research."
    ) | Set-Content (Join-Path $Temp "SUBMISSION_NOTES.txt") -Encoding utf8
    Remove-Item $Output -Force -ErrorAction SilentlyContinue
    Compress-Archive -Path "$Temp\*" -DestinationPath $Output -CompressionLevel Optimal
    Write-Host "Defender submission package: $Output"
} finally {
    Remove-Item $Temp -Recurse -Force -ErrorAction SilentlyContinue
}
