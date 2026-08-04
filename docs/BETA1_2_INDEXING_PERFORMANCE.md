# Beta 1.2 indexing-performance design

## What was learned from the supplied downloader

The reviewed downloader uses two complementary index paths:

- a page-count query followed by independent timemap page requests;
- 50,000-row resume-key pages as a fallback.

Its timemap implementation allows ten requests in flight, limits starts to 80 per minute, records completed page numbers in SQLite, filters rows locally, and writes each returned page with `executemany`. Its downloader also uses pooled HTTP connections and large database batches.

Archive Scout adopts those useful ideas while retaining its project model, exact resume queue, multi-backend Windows recovery, coordinated 429 gate, analysis features, and bounded memory.

## Beta 1.2 architecture

### Broad targets

A broad target is indexed as one yearly page queue. A page-count request determines the number of pages for that year. Up to six page requests are then active concurrently.

The fixed limiter is shared by every page worker. With the default 0.75-second spacing, request starts remain capped at 80 per minute. Page workers improve utilization while a previous response is still being generated; they do not bypass the start-rate limit.

### Narrow targets

Exact and narrow targets continue using resume keys. The default resume page contains up to 25,000 rows. A repeated or malformed resume key remains a resumable transient failure.

### Failed pages

Each page is independent. Successful pages are committed and never placed back in the queue. Failed page numbers and their failure counts are serialized into the index plan. New pages continue while isolated failed pages wait, and failed pages are retried after untouched work.

### Page-count failure

A page-count request should be cheaper than a data page. When it repeatedly cannot complete, Archive Scout does not keep counting forever. It changes that yearly window to resume-key retrieval and divides it into approximately monthly windows when subdivision is required.

### Response format

Bulk CDX work requests line-oriented text first. The original URL is placed last so literal spaces in historical URLs remain parseable. JSON remains available as a same-endpoint fallback.

### Media

All selected extensions remain represented by one server-side `original:` regular expression. Media page requests run in parallel. When an equivalent normal site index has completed, media discovery runs as a local SQLite filter and marks the media index complete without contacting Wayback again.

### Database

The project database uses WAL mode, synchronous NORMAL, memory temporary tables, a 64 MiB page cache, 256 MiB memory mapping, a larger WAL auto-checkpoint interval, and batched `executemany` writes.

## Defaults

```text
Parallel CDX page requests: 6
CDX page blocks: 6
Resume page size: 25,000
CDX request spacing: 0.75 seconds
```

These defaults are intended to balance speed and public-service load. Increasing workers does not increase the fixed request-start rate unless spacing is also reduced.

## Validation limits

The automated suite verifies concurrency, bounded workers, failed-page requeueing, page-count fallback, text-first requests, endpoint timeout behavior, state migration, and local media reuse. It does not reproduce Internet Archive production load or guarantee a particular wall-clock speed on every site.

CDX indexing uses one immediate network attempt per page. Retry ownership lives in the persistent page/window queue, so one expensive timeout is not repeated in place before Archive Scout can requeue, split, or change strategy.
