# Beta 1.6 stability and performance audit

## Release blockers

Two reported failures were treated as zero-tolerance bugs:

1. Process termination or crashes near the first 50,000-snapshot response, especially on macOS but also on Windows.
2. Indexing that displayed an active indexing state while repeatedly attempting Wayback connectivity without beginning useful work.

## 50,000-row memory findings

Beta 1.5 requested up to 50,000 resume-key rows. Its compatibility path could retain the network buffer, a complete decoded string, a list of split rows, a list of dictionaries, and a second list of SQLite values at the same time. Paged indexing could also retain several completed large pages until the slowest sibling returned.

Beta 1.6 now:

- Parses line-oriented CDX data directly into compact six-field tuples.
- Avoids a second project-sized dictionary representation.
- Writes capture and media rows in bounded 2,000-row batches.
- Commits numbered pages in completion order and clears each page immediately.
- Clears each resume-key page before requesting the next page.
- Limits nine-block numbered pages to four simultaneous parsed results while preserving the same fixed request-start interval.
- Converts an oversized response or Python parser `MemoryError` into splittable saved work, allowing the existing page-size reduction/window subdivision system to continue rather than crashing.

A focused local synthetic benchmark used 50,000 rows and a 5,977,794-byte input payload. Traced parser allocations were approximately 50,423,415 bytes for the former decoded-list/dictionary path and 22,824,796 bytes for the compact Beta 1.6 parser, a reduction of about 54.7%. The already allocated input payload was excluded. This is a focused parser comparison, not a whole-application memory guarantee.

## Connection and no-progress findings

All configured CDX endpoint paths use the same Wayback host. Repeating a complete DNS, proxy, TLS, or connect failure against every path multiplied delay without testing an independent destination.

Beta 1.6 separates connection setup from slow responses:

- DNS, proxy, certificate, TLS, socket, and connect failures try the available independent in-process/network backends, then return immediately to the exact saved queue.
- The same saved request is retried briefly and pauses cleanly after three complete connection failures.
- A complete failure across all paged workers enters the same connection circuit instead of being mislabeled as a slow page.
- Read timeouts preserve completed sibling pages and requeue or subdivide only the expensive work.
- Repeated transient failures without any successful response trigger a bounded operation-wide no-progress pause.
- Successful empty CDX responses are accepted as completed zero-result windows rather than being subdivided forever.
- Unexpected parser, SQLite, filesystem, and programming failures are surfaced once as local errors rather than re-entering the network retry queue.

The CDX-only connect-timeout ceiling is 15 seconds. Successful large-response reads retain their separate read-timeout ceiling.

## Whole-repository optimization audit

Project-sized hot paths were reviewed for duplicate buffering, unbounded collections, SQLite variable limits, stale resource state, and retry loops.

Changes include:

- Capture/media inserts use bounded `executemany` batches.
- Text and media download candidates use temporary SQLite queues and keyset pagination.
- Large explicit capture/media retry selections use temporary tables rather than thousands of `?` parameters.
- Error-ignore updates are chunked below SQLite parameter limits.
- Local rescanning, report generation, scan comparison, full-text repair, integrity checks, external-asset lookup, analysis reports, provenance, snapshot differences, project merge, and legacy migration use streaming or bounded batches where possible.
- Duplicate clustering no longer retains a global set containing every candidate pair; duplicate pairs are deterministically processed in their lowest shared SimHash band.
- The unused full provenance timeline materialization was removed from the analysis workflow.
- HTTP clients and SQLite connections close on failure paths, and stale `downloading` rows are reset after interrupted operations.
- GUI events are drained in bounded bursts and Activity history remains bounded.

## Preserved speed envelope

- Fixed request-start spacing: 0.75 seconds.
- Maximum request starts: 80 per minute.
- Resume-key request size: up to 50,000 rows.
- Numbered-page size: 9 CDX blocks.
- Configured page workers: up to 10 for small pages.
- Effective workers for nine-block pages: 4.
- Coordinated HTTP 429 gate and `Retry-After` behavior unchanged.

The worker cap reduces simultaneous resident result buffers; it does not insert additional request delay. Four large requests are enough to keep the 0.75-second start limiter occupied while Wayback prepares multi-second responses.

## Validation boundary

The final repository passed automated, syntax, import, workflow, packaging-script, archive-integrity, and synthetic 50,000-row checks in the development container. Live Internet Archive stress testing, native Windows/macOS packaging, proxy-specific testing, and real low-memory hardware testing still require GitHub Actions and physical systems.
