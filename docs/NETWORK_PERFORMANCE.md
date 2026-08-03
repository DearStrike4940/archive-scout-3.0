# Network performance and HTTP recovery

Archive Scout separates user-selected speed from connection recovery.

1. **Workers** control concurrent replay or media requests.
2. **Request delay** is the fixed minimum interval between request starts.
3. **The shared Wayback circuit** handles HTTP 429 and server-directed pauses.
4. **The multi-backend transport** changes connection method after a transport failure.
5. **CDX endpoint rotation** tries the standard CDX and timemap services in Automatic mode.
6. **CDX strategy recovery** can fall back from page-based retrieval to resume keys.
7. **Window recovery** subdivides only a difficult date range.
8. **Graceful network pause** stops an unproductive all-windows failure cycle while preserving work.

Worker count and request delays remain as selected. Changing network backend is not adaptive rate limiting; it is a fallback between independent HTTP implementations.

## Connection methods

### httpx

- persistent connections
- split connection and read timeouts
- operating-system proxy and certificate environment support
- bounded pool

### urllib3

- independent pooled Python HTTP implementation
- split connection and read timeouts
- manual redirect handling and safe connection draining

### curl

- operating-system executable when present
- HTTP/1.1
- IPv4
- separate connect and total limits
- used only after Python backends fail in Automatic mode

## CDX retrieval

Broad wildcard or prefix targets use page-based CDX retrieval when available. This avoids depending on one very large resume stream. Page work is stored individually and can resume later.

Exact and narrow targets use resume keys. If paging is rejected or unavailable for a broad query, Archive Scout automatically falls back to resume keys.

## Shared HTTP 429 circuit

When a request receives HTTP 429:

- `Retry-After` is honored when present;
- every worker pauses together;
- simultaneous 429 responses are combined;
- stale waiting requests are invalidated;
- one recovery probe runs after the pause;
- the normal queue reopens only after that probe succeeds;
- queued captures remain pending.

The default wait budget is `0`, meaning Archive Scout waits until Wayback recovers or the user presses Pause.

## Persistent contact failure

A DNS, proxy, TLS, firewall, or Wayback outage may cause every backend and endpoint to fail. Archive Scout counts completed failed windows rather than immediately crashing. Once the configured threshold is reached, it:

1. saves the exact queue;
2. resets transient download states;
3. records the operation as paused;
4. displays a recovery message;
5. waits for the user to resume later.

This prevents both a fatal traceback and a never-ending rapid failure loop.

## Bounded queues

Text and media downloaders keep a small bounded number of items in flight rather than submitting a complete archive to the executor. This reduces memory use, prevents a startup burst, and keeps Pause responsive.

## Combined media indexing

Direct media discovery performs one extension-filtered CDX stream per target and time window. It does not perform one stream per extension.

## Balanced starting settings

```text
Network backend: Automatic
CDX endpoint: Automatic
Index strategy: Automatic
Workers: 4
CDX delay: 1.0 seconds
Download delay: 0.5 seconds
Failures before graceful pause: 8
```

More workers and shorter delays are not always faster. They can increase HTTP 429 responses and total idle time.
