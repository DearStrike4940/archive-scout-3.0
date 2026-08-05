# Archive Scout 3.0 Beta 1.4

Beta 1.4 stays deliberately close to Beta 1.2.1 and Beta 1.3.1. The core CDX indexing, timeout recovery, networking, database, text downloading, scanning, and existing media behavior are unchanged.

## Application icon

The supplied Archive Scout icon is bundled as PNG, Windows ICO, and macOS ICNS assets. The GUI loads the PNG at runtime, Windows packages embed the ICO, macOS packages embed the ICNS, and Linux packages use the PNG. The PNG has a transparent background outside the black circular badge.

## Date input fix

The CDX date parser now accepts the existing compact formats plus common user-entered formats:

```text
YYYY
YYYYMM
YYYYMMDD
YYYYMMDDhhmmss
MM/DD/YYYY
MM-DD-YYYY
YYYY-MM-DD
YYYY/MM/DD
```

For example, `09/01/2008` becomes `20080901000000`, and an end date of `12/31/2009` becomes `20091231235959`. Invalid dates are rejected with a readable message before the worker starts.

## External embedded media after text scanning

A new operation named **Index, download, scan, then download external embedded media** runs in this order:

1. Index the selected text targets.
2. Download and scan the selected text captures.
3. Read the completed documents' extracted URL lists.
4. Keep only external image/video links matching the Media extension settings.
5. Look up those exact URLs in Wayback.
6. Apply the selected earliest/latest/all snapshot strategy.
7. Download the queued external media only after discovery finishes.

This uses the existing media tables, retries, reports, limits, and download engine. It does not run a broad CDX media crawl of every external host.

## Windows trust and signing

The Windows application remains a PyInstaller onedir package with UPX disabled. Tagged releases require Azure Artifact Signing when configured. The build now separates build and packaging stages: the executable is built, signed, and then packaged only after `Get-AuthenticodeSignature` reports `Valid`.

The Windows package includes `README-WINDOWS.txt` with checksum verification, Digital Signatures verification, Mark-of-the-Web / Unblock instructions, and Microsoft Defender false-positive submission steps. Signing and submission reduce false positives but cannot guarantee a particular antivirus determination.

## Dashboard

The read-only live Dashboard counters remain enabled and continue updating during active and idle use without requiring manual refreshes.
