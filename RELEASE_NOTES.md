# Archive Scout 3.0 Beta 1.2

Beta 1.2 is the indexing-performance patch. It keeps every Alpha 4/Beta 1 feature and the Beta 1.1 malformed-CDX/media fixes, but replaces the slow serial broad-index path.

## Faster broad indexing

- Broad wildcard, prefix, host, and domain targets use one yearly CDX page queue instead of twelve separate monthly page queues.
- Six CDX pages can be in flight at once by default.
- One shared limiter still spaces request starts by 0.75 seconds, so concurrency hides response latency without producing an uncontrolled burst.
- Each page requests six CDX blocks by default, reducing round trips.
- Bulk responses use line-oriented text first, avoiding large JSON-array decoding and retaining malformed-response recovery.
- Successful pages are written in one SQLite transaction per batch.
- A failed page is saved and requeued without repeating successful pages.
- A page that remains slow twice is removed from the paged bottleneck and continued as smaller resume-key windows while successful page data remains stored.

## Faster media indexing

- Media extensions remain combined into one query stream.
- Media CDX pages use the same bounded parallel engine.
- When the normal site index is already complete, Archive Scout filters media URLs from SQLite and skips the second network index entirely.

## Timeout behavior

- A read timeout no longer repeats the full wait through every HTTP backend and endpoint.
- CDX page requests return to the persistent queue after one failed network attempt instead of consuming a second full timeout first.
- A failed page-count request switches to resume-key indexing with smaller saved windows instead of entering a count-timeout loop.
- Page position, failed pages, per-page failure counts, and successful captures remain resumable.

## Upgrading

Beta 1 projects using the original 5,000-row, one-block, one-second defaults are moved to 25,000 rows, six blocks, six page workers, and 0.75-second spacing. Compatible completed index state is adopted so a transport-page-size change alone does not force a complete re-index.

## Release assets

```text
ArchiveScout-Windows-x64.zip
ArchiveScout-Windows-x64.zip.sha256
ArchiveScout-Linux-x64.tar.gz
ArchiveScout-Linux-x64.tar.gz.sha256
ArchiveScout-macOS-Universal.zip
ArchiveScout-macOS-Universal.zip.sha256
```
