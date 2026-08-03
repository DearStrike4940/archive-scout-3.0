# Comparison with the supplied Wayback Machine Downloader scripts

The visible entry points of the supplied downloader demonstrated useful design ideas:

- a reusable HTTP client;
- connection pooling;
- separate connection and read timeouts;
- asynchronous/concurrent support libraries;
- extension and keyword filtering;
- single-timestamp deduplication;
- optional search tools.

Its actual archive engine was imported from `libs.archive_downloader`, which was not included in the supplied files. Archive Scout therefore does not claim exact parity with unseen pagination, scheduling, storage, or retry behavior.

## What Archive Scout 3.0 uses

- persistent `httpx` connections with operating-system proxy support;
- a separate `urllib3` connection pool;
- operating-system `curl` fallback;
- split connection and read timeouts;
- fixed request-start spacing shared by workers;
- bounded in-flight queues;
- page-based CDX retrieval for broad targets;
- resume-key CDX retrieval for narrow targets;
- alternate CDX endpoint fallback;
- batched SQLite writes;
- resumable page/window queues;
- compiled literal prefiltering for large keyword sets;
- normalized page fields shared by multiple keyword sets;
- one combined direct-media CDX filter.

## Additional safeguards

- host-wide HTTP 429 circuit breaker;
- exact `Retry-After` handling;
- one recovery probe before reopening the queue;
- persisted queue state and graceful connectivity pause;
- automatic project backups and repair tools;
- structured network-event and operation history;
- streamed response-size enforcement;
- forum reconstruction, extraction, legacy-media recovery, duplicate analysis, snapshot comparison, provenance, and project merging.

## Deliberate differences

Archive Scout uses a transparent project user agent instead of browser impersonation. It does not add Torch, Transformers, or a CLIP model to the download core because those packages support image-similarity analysis rather than faster CDX retrieval and would significantly increase package size and platform risk.

The runtime remains focused on `truststore`, `httpx`, and `urllib3`, with OS `curl` used when available.
