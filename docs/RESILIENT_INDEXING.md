# Resilient CDX indexing

Archive Scout treats temporary Wayback failures as resumable state rather than as a reason to abandon a project.

## Strategy selection

Automatic mode chooses an initial strategy from the target:

- broad wildcard, prefix, host, and domain targets prefer page-based CDX retrieval;
- exact and narrow targets prefer resume-key retrieval.

Page-based retrieval first requests the number of pages, then stores each page as pending work. Resume-key retrieval stores the server-provided continuation key after every successful response.

If page-based retrieval is unavailable for a particular query, Archive Scout falls back to resume keys without discarding completed work.

## Endpoint selection

Automatic endpoint mode can try:

```text
https://web.archive.org/cdx/search/cdx
https://web.archive.org/web/timemap/cdx
```

A temporary failure on one endpoint does not immediately end the operation.

## Transport selection

Automatic network mode can try:

```text
httpx
urllib3
curl
```

The last successful backend is preferred. A failing backend is temporarily cooled down while another connection path is attempted.

## Window subdivision

A timeout, temporary gateway response, or other splittable transient error subdivides only the failed interval:

```text
month
7 days
1 day
6 hours
1 hour
15 minutes
5 minutes
1 minute
15 seconds
5 seconds
1 second
```

The complete queue, strategy, page position, failure count, page size, CDX resume key, and endpoint state are stored in the project database.

## Smallest-window behavior

A one-second interval cannot be divided further. Archive Scout then:

1. lowers the page size for that interval;
2. records a retryable transient delay;
3. moves the interval behind other pending work when possible;
4. saves the updated queue;
5. retries with bounded backoff.

## Graceful connectivity pause

When every remaining interval repeatedly fails and reaches the configured failure threshold, Archive Scout does not continue a rapid endless loop. It:

1. saves the exact queue;
2. leaves unfinished captures pending;
3. records the operation as `paused`;
4. records a network event and retryable error;
5. shows a clean connectivity message.

Use **Resume interrupted work** after the connection, proxy, DNS, firewall, or Wayback service recovers.

## HTTP 429 behavior

HTTP 429 is handled separately from generic contact failure. One host-wide gate pauses all workers, honors `Retry-After`, and permits one recovery probe before the queue reopens.

## What can still stop an operation

Archive Scout does not retry deterministic local failures forever. Examples include:

- malformed CDX parameters;
- invalid user regular expressions;
- unsupported database schema;
- database corruption;
- missing write permission;
- missing or damaged packaged runtime files.

These require correction rather than another HTTP attempt.

## Resume

Use **Resume interrupted work** or rerun the original operation. Completed pages/windows are skipped and the pending queue continues from its saved state.
