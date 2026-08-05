# Repository details

Product: `Archive Scout 3.0`

Release: `3.0.0-beta.1.4`

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

## Beta 1.4 scope

Beta 1.4 deliberately preserves the Beta 1.2.1 indexing, networking, database, timeout-recovery, downloading, scanning, and existing media fundamentals.

Focused changes:

- live read-only Dashboard totals retained from Beta 1.3.1
- official PNG, ICO, and ICNS application icons
- MM/DD/YYYY and ISO-style date input support
- friendly date validation before worker startup
- one dedicated text-first external embedded-media workflow
- signed Windows packaging that fails unless Authenticode verification is valid
- Windows Mark-of-the-Web, checksum, signature, and Defender false-positive documentation
- PyInstaller onedir packaging and UPX-disabled Windows builds retained

## External embedded-media workflow

The dedicated operation completes the normal text index, downloads and scans the selected pages, then reads the saved documents' extracted link lists. It looks up only matching external media URLs and downloads them after discovery is complete. It uses the existing media extension filters, size limit, snapshot strategy, retries, database tables, and reports.

## macOS bundle integrity

The macOS build verifies `Contents/Resources/base_library.zip`, the executable, and every symbolic link before signing. It packages the signed application with `ditto`, extracts the completed ZIP into a clean temporary directory, and verifies the extracted bundle and code signature again.

## Repository upload

Upload the contents of the extracted `archive-scout-3.0-beta1.4` folder to the repository root. The hidden `.github` folder must be included.
