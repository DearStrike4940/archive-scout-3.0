param([switch]$SkipPackage)
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
Remove-Item build,dist,release -Recurse -Force -ErrorAction SilentlyContinue
python -m PyInstaller --noconfirm --clean --windowed --onedir --noupx --log-level WARN --name ArchiveScout --version-file packaging/windows/version_info.txt --collect-all truststore --collect-all urllib3 --collect-all httpx --collect-all httpcore run_app.py
New-Item -ItemType Directory -Path release | Out-Null
$Package = Join-Path $PWD "release\ArchiveScout-Windows-x64"
New-Item -ItemType Directory -Path $Package | Out-Null
Copy-Item dist\ArchiveScout $Package\ArchiveScout -Recurse
Copy-Item packaging\windows\README-WINDOWS.txt $Package
Copy-Item README.md $Package
if (-not $SkipPackage) {
    ./scripts/verify_windows_signature.ps1
    ./scripts/package_windows.ps1
}
