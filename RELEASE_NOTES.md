# Archive Scout 3.0 Beta 1

Archive Scout 3.0 Beta 1 combines the planned final Alpha 4 reliability milestone with the planned Beta 1 interface redesign in a new repository.

## Highlights

- Rebuilt Wayback connection layer with httpx, urllib3, and operating-system curl fallback
- Operating-system proxy and certificate-environment support
- Standard CDX and timemap endpoint rotation
- Page-based CDX retrieval for broad site searches
- Resume-key retrieval and automatic paging fallback
- Clean network pauses with the exact pending queue saved
- Coordinated HTTP 429 waiting and one-probe recovery
- One combined media-index stream for all selected image/video extensions
- Database schema version 5
- Crash recovery, backups, restore, repair, diagnostics, and operation history
- Per-target network and indexing settings
- New dashboard and left navigation
- Simple and Advanced workspaces
- System, Light, and Dark themes
- Font scaling, persistent layout, keyboard shortcuts, and first-run guide
- Paginated results and review-status coloring
- Complete Alpha 3 archive-analysis feature set retained

## Supported platforms

- Windows x64
- Linux x64
- macOS Intel and Apple Silicon

## Migration

Archive Scout 3.0 can migrate schema versions 2, 3, and 4 to schema version 5. Back up important projects before opening them in the new release, then run the project-integrity check.

## Release assets

```text
ArchiveScout-Windows-x64.zip
ArchiveScout-Windows-x64.zip.sha256
ArchiveScout-Linux-x64.tar.gz
ArchiveScout-Linux-x64.tar.gz.sha256
ArchiveScout-macOS-Universal.zip
ArchiveScout-macOS-Universal.zip.sha256
```

## Testing note

The source passed the complete local automated suite and virtual-display interface checks. Native packages, real proxy/firewall environments, and live Internet Archive stress behavior still require GitHub Actions and real-machine testing.
