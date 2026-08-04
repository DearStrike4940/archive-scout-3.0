# Archive Scout 3.0 Beta 1.3

Beta 1.3 preserves the Beta 1.2 indexing engine and adds two focused changes: Windows release hardening and live Dashboard totals.

## Windows release hardening

- PyInstaller remains in `--onedir` mode.
- UPX is explicitly disabled.
- Stable Windows product/version metadata is embedded in the executable.
- PowerShell installer and uninstaller launchers are no longer distributed.
- Windows builds use only the in-process httpx and urllib3 transport stacks.
- Tagged Windows releases require Microsoft Artifact Signing to be enabled.
- The signed executable is verified before ZIP creation.
- The Windows package includes a signature report, `SHA256SUMS.txt`, and an SPDX 2.3 SBOM.

## Live Dashboard

Indexed captures, saved documents, ranked matches, and open errors update automatically while an operation is active and while the Dashboard page is visible. The updater uses a read-only SQLite connection with a short busy timeout and retains the last good values during a batch-write lock.

## Important signing requirement

The source code can prepare and verify a signed release, but the repository owner must configure an Artifact Signing account/profile and the documented GitHub variables/secrets. Manual builds may remain unsigned for testing. Tagged release builds intentionally fail until signing is enabled.

## Release assets

```text
ArchiveScout-Windows-x64.zip
ArchiveScout-Windows-x64.zip.sha256
ArchiveScout-Windows-x64.files.sha256
ArchiveScout-Windows-x64.spdx.json
ArchiveScout-Linux-x64.tar.gz
ArchiveScout-Linux-x64.tar.gz.sha256
ArchiveScout-macOS-Universal.zip
ArchiveScout-macOS-Universal.zip.sha256
```
