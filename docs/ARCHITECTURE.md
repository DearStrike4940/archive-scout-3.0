# Architecture

Archive Scout separates capture discovery, downloaded material, searches, analysis, and human review so each stage can be resumed or rerun independently.

## Core storage

- `targets` stores normalized site and path targets.
- `captures` stores archived text-capture identity and download state.
- `documents` stores parsed text, local paths, links, and hashes.
- `media_captures` stores image/video capture identity, state, local path, and hash.
- `keyword_sets` stores normalized rule definitions.
- `scan_runs` stores a separate history entry for each search.
- `document_matches` stores one document's score and evidence for one scan.
- `reviews`, `notes`, and `tags` store human research decisions.
- `errors` stores retryable, deferred, resolved, and permanent failures.
- `documents_fts` provides offline SQLite full-text search.

## Archive-analysis storage

- `analysis_runs` records each analysis execution and its summary.
- `forum_threads` stores canonical thread identity and aggregate dates/counts.
- `forum_posts` stores reconstructed posts tied to source documents and captures.
- `extractions` stores built-in and custom identifier matches with field and offsets.
- `legacy_assets` stores recovered player/embed assets and lookup state.
- `duplicate_groups` and `duplicate_members` store exact and near-duplicate clusters.
- `provenance_edges` stores inferred source-to-mirror relationships.
- `snapshot_diffs` stores adjacent-snapshot change summaries.
- `first_appearances` stores earliest and latest captures for extracted values.
- `project_merges` prevents the same source project from being merged repeatedly.

## Schema version 5 reliability storage

- `operation_runs` records operation type, version, start, finish, state, and summary.
- `network_events` records backend changes, rate limits, timeouts, and graceful pauses.
- `project_backups` records managed SQLite backups.
- `repair_actions` records project-repair changes.

Opening a project resets records left in transient `downloading` or `running` states after an application or operating-system interruption.

## Packages

```text
archive_scout/cdx          CDX endpoint selection, paging, resume keys, window queues, and indexing
archive_scout/network      httpx, urllib3, and curl transport backends
archive_scout/downloads    shared backpressure, fixed pacing, text downloading, and retries
archive_scout/scanning     keyword parsing, scoring, snippets, rescanning, and FTS
archive_scout/media        combined media indexing, downloading, discovery, and reports
archive_scout/parsing      forum and legacy-embed parsing
archive_scout/extraction   regex extraction and provenance construction
archive_scout/analysis     duplicates, snapshot diffs, first appearances, and orchestration
archive_scout/database     schema, migrations, recovery, and repository functions
archive_scout/reports      text reports, exports, and scan comparison
archive_scout/projects     backups, diagnostics, import, integrity, merge, migration, and repair
archive_scout/ui           themed Tkinter desktop interface
```

## Multi-backend network transport

Automatic mode creates persistent `httpx` and `urllib3` clients and uses the operating system's `curl` executable when present. The transport:

1. prefers the last backend that successfully contacted Wayback;
2. cools down a failing backend;
3. tries another independent backend;
4. returns HTTP status responses to the centralized Wayback policy;
5. converts complete transport exhaustion into a resumable transient request.

`httpx` honors operating-system proxy and certificate environment variables when enabled. `urllib3` provides an independent Python connection pool. `curl` provides a final OS-level path using HTTP/1.1 and IPv4.

## CDX indexing strategies

Broad wildcard, prefix, host, and domain targets prefer page-based retrieval. Archive Scout asks for the number of pages, then persists each page as work. Narrow and exact targets prefer resume-key retrieval.

If page-count or page retrieval is unavailable for a query, the indexer falls back to resume keys. Both strategies store the complete queue and can subdivide only a failed date interval.

After repeated failure across all remaining work, the operation enters a clean `paused` state. The queue is preserved for Resume instead of producing a fatal traceback or an aggressive endless retry loop.

## HTTP 429 behavior

HTTP 429 responses close one shared host circuit. Every worker waits, one recovery probe runs after the pause, and the complete queue reopens only after recovery. User-selected workers and delays are not silently rewritten.

## Media indexing

Direct media indexing builds one case-insensitive extension regular expression from all selected image and video extensions. One CDX stream is sent per target and time window. Returned URLs are validated locally before insertion. This avoids multiplying CDX requests by the number of extensions.

## Database and filesystem safety

SQLite uses WAL mode and batched writes. Managed backups use SQLite's backup API rather than copying an open database file. Repair operations make a safety backup, reset stuck states, identify missing files, rebuild FTS, remove abandoned partial files, checkpoint WAL, and optimize the database.
