# Archive Scout 3.0 network architecture

This document explains the connection redesign created for users who were stuck in repeated CDX timeouts and contact failures, particularly on Windows.

## Problem addressed

A single HTTP implementation can fail repeatedly because of:

- proxy auto-configuration;
- antivirus TLS interception;
- certificate-store differences;
- DNS behavior;
- IPv6 or HTTP/2 problems;
- stale pooled connections;
- firewall policy;
- temporary Wayback endpoint failure;
- a CDX query that is too expensive for one response.

Retrying the same request through the same stack can create an unproductive loop. Archive Scout 3.0 separates connection fallback, server-rate limiting, CDX pagination, date-window splitting, and project resume state.

## Automatic transport chain

### 1. httpx

The first path uses a persistent `httpx.Client` with:

- system trust through `truststore`;
- optional proxy and certificate environment support;
- split connect/read/write/pool timeouts;
- bounded keep-alive connections;
- redirects and streamed reads.

### 2. urllib3

The second path uses an independent `urllib3.PoolManager` with:

- a separate connection pool;
- split connection/read timeouts;
- manual redirect limits;
- safe draining and release of response connections.

### 3. curl

When available, the final path invokes the operating system's `curl` with:

- HTTP/1.1;
- IPv4;
- compressed response support;
- connect and total limits;
- redirect handling;
- streamed output to a temporary file.

A deterministic local failure, such as an oversized response or excessive redirects, is not retried through every backend.

## Backend memory and cooldown

The last successful backend is tried first on later requests. A failed backend is cooled down for a short period while another method is tried. If all methods are cooling down, Archive Scout still makes one controlled attempt rather than blocking indefinitely inside the transport layer.

## CDX endpoint rotation

Automatic mode can try both the standard CDX endpoint and the CDX timemap endpoint. Endpoint failure is separate from transport failure: each endpoint can be attempted through the available transport chain.

## Paged and resume-key strategies

Broad targets prefer page-based retrieval. Narrow targets prefer resume keys. Both strategies persist progress.

Page-based retrieval avoids one unbounded stream for a complete wildcard domain. Resume keys remain useful for exact URLs and as a fallback when paging is unsupported or rejected for a query.

## Failure boundaries

Archive Scout has three different recovery boundaries:

1. **Request boundary:** try another backend and endpoint.
2. **Window boundary:** split only the failed date range or reduce its page size.
3. **Operation boundary:** after repeated failure across all remaining work, save the queue and pause.

This prevents a raw timeout traceback, data loss, and a never-ending rapid loop.

## Proxy and certificate environment

When enabled, `httpx` honors the operating system or shell environment for values such as proxy and certificate configuration. Users behind a managed network can also select a specific backend in Advanced settings for diagnosis.

## Diagnostics

The diagnostic package records sanitized information about:

- selected network mode;
- available backends;
- operation history;
- recent network events;
- error categories;
- project integrity;
- Python, platform, and application versions.

It does not include downloaded page bodies.
