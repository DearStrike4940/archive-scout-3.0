# Repository details

Product: `Archive Scout 3.0`

Release: `3.0.0-beta.1.6`

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

## Beta 1.6 scope

Beta 1.6 is a whole-repository reliability and large-project optimization pass. The existing request-rate limit, project schema, visible workflows, media behavior, live Dashboard, icon, date handling, external-media operation, and signing workflow remain in place.

Release-blocker fixes:

- compact and bounded handling of 50,000-row CDX responses
- immediate release of completed numbered pages
- safe reduction/subdivision after oversized responses or parser memory pressure
- bounded connection-setup retries followed by a clean saved pause
- operation-wide no-progress protection
- complete paged connection failures routed into the same connection circuit

Repository-wide audit work:

- streaming/bounded database, download, rescan, reporting, analysis, repair, integrity, merge, migration, and retry paths
- temporary tables for large explicit ID selections
- deterministic duplicate candidate de-duplication without a global pair set
- resource cleanup on client/database/operation failures
- bounded GUI event/log retention

## Preserved Wayback speed envelope

- fixed 0.75-second request-start interval
- 50,000 rows per resume-key request
- nine CDX blocks per numbered page
- ten configured workers for small pages
- four effective resident workers for nine-block pages
- coordinated HTTP 429 backpressure

## External embedded-media workflow

The dedicated operation completes the normal text index, downloads and scans selected pages, then reads saved documents' extracted link lists. It looks up matching external media URLs and downloads them after discovery is complete using the existing media filters, size limit, snapshot strategy, retries, database tables, and reports.

## macOS bundle integrity

The macOS build verifies `Contents/Resources/base_library.zip`, the executable, and every symbolic link before signing. It packages the signed application with `ditto`, extracts the completed ZIP into a clean temporary directory, and verifies the extracted bundle and code signature again.

## Repository upload

Upload the contents of the extracted `archive-scout-3.0-beta1.6` folder to the repository root. The hidden `.github` folder must be included.
