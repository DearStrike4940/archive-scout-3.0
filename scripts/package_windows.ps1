$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)
$Package = Join-Path $PWD "release\ArchiveScout-Windows-x64"
if (-not (Test-Path "$Package\ArchiveScout\ArchiveScout.exe")) { throw "Staged Windows application is missing." }
$Sbom = Join-Path $PWD "release\ArchiveScout-Windows-x64.spdx.json"
python scripts/generate_sbom.py --output $Sbom --version "3.0.0-beta.1.3" --root truststore --root urllib3 --root httpx
Copy-Item $Sbom "$Package\ArchiveScout-Windows-x64.spdx.json" -Force
if (Test-Path "release\ArchiveScout-Windows-x64.signature.txt") { Copy-Item "release\ArchiveScout-Windows-x64.signature.txt" "$Package\ArchiveScout-Windows-x64.signature.txt" -Force }
python scripts/generate_sha256_manifest.py $Package "$Package\SHA256SUMS.txt"
Copy-Item "$Package\SHA256SUMS.txt" "release\ArchiveScout-Windows-x64.files.sha256" -Force
$Zip = Join-Path $PWD "release\ArchiveScout-Windows-x64.zip"
Remove-Item $Zip -Force -ErrorAction SilentlyContinue
Compress-Archive -Path "$Package\*" -DestinationPath $Zip -CompressionLevel Optimal
$Hash = (Get-FileHash $Zip -Algorithm SHA256).Hash.ToLower()
"$Hash  ArchiveScout-Windows-x64.zip" | Set-Content "release\ArchiveScout-Windows-x64.zip.sha256" -Encoding ascii
