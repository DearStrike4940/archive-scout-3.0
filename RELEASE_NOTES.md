# Archive Scout 3.0 Beta 1.6

Beta 1.6 is a whole-repository reliability and large-project optimization pass. It keeps the Beta 1.5 request-rate envelope and existing user-facing workflows while addressing the two zero-tolerance failures reported in real use: crashes around 50,000 snapshots and indexing sessions that never move beyond repeated Wayback contact attempts.

## 50,000-snapshot stability

Bulk CDX responses now follow a compact path from the network into SQLite. Line-oriented output is parsed directly into fixed tuples, database values are generated in bounded batches, and a numbered page is written and released as soon as it completes. The raw response, a full decoded copy, a list-of-lists, a list-of-dictionaries, and a second database-values list no longer coexist for the same 50,000 rows.

Large nine-block pages use a memory-aware maximum of four resident page workers. Smaller page configurations can still use all ten workers. The global 0.75-second request-start interval remains unchanged, so the change protects memory without adding artificial delay to request starts.

Text-download selection, media-download selection, and local rescanning now stream through SQLite instead of loading the complete project into Python lists. Media earliest/latest selection is performed by SQLite rather than grouping every media row in memory.

## Connection and no-progress recovery

A complete DNS, proxy, TLS, or connection-setup failure now returns directly to the saved operation queue after the available independent HTTP backends have been tried. Archive Scout retries that exact request briefly and pauses after three complete failures. It no longer repeats the same host-level failure against every alternate CDX path or rotates through all date windows indefinitely.

Repeated read timeouts and retryable HTTP failures are protected by an operation-wide no-progress watchdog. Successful responses, including valid empty result windows, reset the watchdog. When no usable response arrives after the bounded recovery attempts, the exact queue is saved and the operation enters the existing paused state.

The CDX connect-timeout ceiling is 15 seconds in this release. This affects only failed connection setup; it does not shorten the read timeout for large responses or slow successful requests.

## Repository-wide safeguards

- Unexpected local and programming errors are recorded once and surfaced instead of being mislabeled as transient network errors.
- Capture and media upserts use bounded 2,000-row batches.
- Oversized CDX bodies and parser memory pressure are converted into resumable smaller saved work instead of terminating the process.
- Full-text repair, project integrity checks, scan comparisons, external-asset lookup, retry selections, duplicate clustering, reports, provenance, project merge, and migration paths were audited and changed to bounded or streaming processing where project-sized lists were unnecessary.
- Large explicit capture/media retry selections and error selections no longer depend on SQLite's platform-specific parameter limit.
- Composite SQLite indexes accelerate pending download selection.
- The GUI Activity log retains a bounded recent history, and event bursts yield back to Tk so the interface remains responsive.
- Legacy/mock clients that expose only `get_cdx_any` remain supported.
- The database schema remains version 5 and existing projects require no destructive migration.

## Preserved behavior

Beta 1.5's 50,000-row resume requests, nine CDX blocks per numbered page, ten configured page workers, fixed 0.75-second shared request-start spacing, combined media indexing, live Dashboard, date formats, icon, external embedded-media operation, and Windows signing workflow remain in place.

## Validation boundary

The repository was compile-checked, parsed, tested, and packaged in the development container. A live Internet Archive stress test, native Windows/macOS build, Defender scan, and long real-world 50,000+ snapshot run still require GitHub Actions and physical machines.
