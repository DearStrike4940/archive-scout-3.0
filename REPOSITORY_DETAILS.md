# Repository details

Product: `Archive Scout 3.0`

Release: `3.0.0-beta.1.5`

Database schema: `5`

Supported build targets:

- Windows x64
- Linux x64
- macOS Universal 2 for Intel and Apple Silicon

Primary release files:

```text
ArchiveScout-Windows-x64.zip
ArchiveScout-Linux-x64.tar.gz
ArchiveScout-macOS-Universal.zip
```

Each package has a corresponding `.sha256` file.

## Beta 1.5 scope

Beta 1.5 changes only Wayback connection utilization and CDX transport batching. All Beta 1.4 features and workflows remain in place.

Focused changes:

- 10 bounded CDX page workers instead of 6
- 9 CDX blocks per numbered page instead of 6
- 50,000 rows per resume-key request instead of 25,000
- the same fixed 0.75-second global request-start spacing (80 starts per minute)
- 90-second HTTPX keep-alive retention instead of 45 seconds
- automatic migration only for untouched old defaults; custom values are preserved

## External embedded-media workflow

The dedicated operation completes the normal text index, downloads and scans the selected pages, then reads the saved documents' extracted link lists. It looks up only matching external media URLs and downloads them after discovery is complete. It uses the existing media extension filters, size limit, snapshot strategy, retries, database tables, and reports.

## macOS bundle integrity

The macOS build verifies `Contents/Resources/base_library.zip`, the executable, and every symbolic link before signing. It packages the signed application with `ditto`, extracts the completed ZIP into a clean temporary directory, and verifies the extracted bundle and code signature again.

## Repository upload

Upload the contents of the extracted `archive-scout-3.0-beta1.5` folder to the repository root. The hidden `.github` folder must be included.
