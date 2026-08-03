# Archive Scout 3.0 Beta 1.1

Beta 1.1 is a focused reliability hotfix for the Archive Scout 3.0 Beta 1 release.

## Fixed

- Malformed or truncated CDX JSON returned with HTTP 200 no longer terminates indexing with `JSONDecodeError` or `RuntimeError`.
- Archive Scout automatically retries the same CDX query as uncompressed plain text, including resume-key and page-count support.
- If both formats are unusable, the request becomes resumable transient work and follows the existing endpoint rotation, date-window subdivision, and saved-queue recovery system.
- Combined media indexing now uses the documented `filter=original:regex` syntax rather than `~original:`.
- Explicit media targets correctly remove wildcard suffixes when `matchType=prefix`, `host`, or `domain` is selected.
- Historical media URLs such as `photo.jpg&ref=thumb` and media filenames stored in query values are recognized locally.
- Extensionless Flash, RealMedia, and Windows Media captures can be recognized from MIME type.
- The media-index state revision was increased so an empty Beta 1 media index is not incorrectly treated as complete after the update.

## Required after upgrading

Run **Index and download selected media** or **Index media URLs only** once. Beta 1.1 creates a new media-index state signature while preserving the existing capture signature, so it does not trust the old completed Beta 1 media state or duplicate valid media records.

## Release assets

```text
ArchiveScout-Windows-x64.zip
ArchiveScout-Windows-x64.zip.sha256
ArchiveScout-Linux-x64.tar.gz
ArchiveScout-Linux-x64.tar.gz.sha256
ArchiveScout-macOS-Universal.zip
ArchiveScout-macOS-Universal.zip.sha256
```
