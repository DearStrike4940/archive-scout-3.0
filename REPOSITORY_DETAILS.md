# Repository details

Product: `Archive Scout 3.0`

Release: `3.0.0-beta.1.2.1`

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

## Beta 1.2 focus

Beta 1.2 is a performance patch over the Alpha 4/Beta 1 integration release and the Beta 1.1 CDX/media hotfix.

Indexing systems:

- one yearly page queue for broad CDX targets
- six bounded parallel page requests by default
- six CDX blocks per page by default
- 80 request starts per minute through one shared fixed limiter
- text-first bulk CDX parsing with JSON fallback
- per-page retry queues and exact resume state
- page-count timeout fallback to smaller resume-key windows
- completed-state adoption across compatible Beta 1 page-size defaults
- media reuse from the normal site index
- one combined media extension query

Reliability systems:

- multi-backend HTTP transport: httpx, urllib3, and curl
- system proxy and certificate-environment support
- CDX endpoint rotation and last-success preference
- no backend/endpoint cascade after a read timeout
- coordinated HTTP 429 recovery
- persisted CDX queues and graceful connectivity pauses
- schema version 5 operation, network-event, backup, and repair records
- crash recovery, project backup, restore, repair, and diagnostics

Interface systems:

- dashboard and left navigation
- Simple and Advanced modes
- System, Light, and Dark themes
- font scaling and persistent interface state
- paginated results and visual review states
- CDX page-block and parallel-page controls

## macOS bundle integrity

The macOS build verifies `Contents/Resources/base_library.zip`, the executable, and every symbolic link before signing. It packages the signed application with `ditto`, extracts the completed ZIP into a clean temporary directory, and verifies the extracted bundle and code signature again.

## Repository upload

Upload the contents of the extracted `archive-scout-3.0-beta1.2` folder to the repository root. The hidden `.github` folder must be included.
