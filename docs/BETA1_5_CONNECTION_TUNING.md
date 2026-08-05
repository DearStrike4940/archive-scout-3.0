# Beta 1.5 Wayback connection tuning

Beta 1.5 intentionally changes only CDX transport utilization.

The comparison downloader uses a reusable client with ten idle pooled connections, a ten-request concurrency limiter, a strict 80-request-per-minute start limiter, nine CDX blocks per numbered page, and 50,000-row resume-key requests. Archive Scout already had the same fixed 0.75-second request-start interval and resumable failure handling, but used only six page workers, six blocks, and 25,000-row resume pages.

Beta 1.5 adopts the comparison downloader's conservative upper envelope without increasing request frequency:

- CDX workers: 6 -> 10
- numbered-page blocks: 6 -> 9
- resume-key rows: 25,000 -> 50,000
- request-start spacing: remains 0.75 seconds
- maximum request starts: remains 80 per minute
- HTTPX keep-alive expiry: 45 -> 90 seconds
- resume response budget: scales to at least 2 KiB per requested row

Why this should be faster:

- More workers keep the fixed request-start schedule fully utilized when Wayback responses take several seconds.
- Nine blocks reduce numbered-page round trips by roughly one third compared with six blocks for the same archive.
- 50,000-row resume requests can halve resume-key round trips compared with 25,000 rows.
- Longer keep-alive retention reduces avoidable TLS and TCP reconnections during long responses and brief pauses.
- A larger response budget prevents the 50,000-row optimization from being rejected by the older 64 MiB ceiling on archives with unusually long URLs.

What did not change:

- no adaptive rate increase
- no reduction in the 0.75-second spacing
- no new retry loop
- no timeout-policy change
- no endpoint-policy change
- no database-schema change
- no media, scanning, analysis, UI-workflow, packaging, or download behavior change

Older projects are upgraded only when all four old defaults are still present. Any custom page size, block count, worker count, or delay is preserved.
