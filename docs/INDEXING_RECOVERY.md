# Indexing recovery

This document is a quick reference. See [RESILIENT_INDEXING.md](RESILIENT_INDEXING.md) and [ARCHIVE_SCOUT_3_NETWORK.md](ARCHIVE_SCOUT_3_NETWORK.md) for the complete design.

Archive Scout 3.0 preserves the complete pending CDX queue. Broad targets can use page-based retrieval; exact targets can use resume keys. A failed request can rotate through independent HTTP backends and CDX endpoints before only the failed date interval is subdivided.

When all remaining work repeatedly fails, Archive Scout enters a graceful network pause. It does not discard the queue, mark the project complete, or rapidly repeat the same failing request forever. Use **Resume interrupted work** after connectivity improves.
