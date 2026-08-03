# Repository details

Product: `Archive Scout 3.0`

Release: `3.0.0-beta.1`

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

## Beta 1 scope

This repository combines the planned Alpha 4 integration and reliability milestone with the planned Beta 1 interface redesign.

Major reliability systems:

- multi-backend HTTP transport: httpx, urllib3, and curl
- system proxy and certificate-environment support
- CDX endpoint rotation
- paged and resume-key indexing strategies
- persisted CDX queues and graceful connectivity pauses
- coordinated HTTP 429 recovery
- combined direct-media indexing
- schema version 5 operation, network-event, backup, and repair records
- crash recovery
- project backup, restore, repair, and diagnostics
- per-target settings

Major interface systems:

- dashboard
- left navigation
- Simple and Advanced modes
- System, Light, and Dark themes
- font scaling
- persistent interface state
- paginated results
- visual review states
- project-maintenance controls
- network-recovery controls

## macOS bundle integrity

The macOS build verifies `Contents/Resources/base_library.zip`, the executable, and every symbolic link before signing. It packages the signed application with `ditto`, extracts the completed ZIP into a clean temporary directory, and verifies the extracted bundle and code signature again.

## Repository upload

Upload the contents of the extracted `archive-scout-3.0-beta1` folder to the root of a new GitHub repository. The hidden `.github` folder must be included.
