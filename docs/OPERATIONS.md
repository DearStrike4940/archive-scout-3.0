# Operations

## Text workflows

### Full run

Indexes text captures, downloads pending pages, evaluates every selected keyword set, and creates reports.

### Index only

Stores CDX capture metadata without downloading pages.

### Download pending

Downloads pending records already stored in the database and scans them with the selected keyword sets.

### Resume interrupted work

Continues the saved CDX page or resume-key queue and restores interrupted downloads to pending. Completed work is skipped.

### Offline rescan

Reads every valid local document once and evaluates all selected keyword sets. No network requests occur.

### Retry errors

Retries selected or unresolved errors. Scan and parse failures use valid local documents. Download failures are requested again only when necessary.

### Regenerate reports

Recreates the latest text reports from the database without downloading or scanning.

## Project maintenance

### Check project integrity

Reports missing files, empty files, size mismatches, invalid references, and unresolved errors.

### Repair project and rebuild indexes

Creates a safety backup, resets stuck states, identifies missing files, queues appropriate redownloads, rebuilds FTS, removes abandoned `.part` files, checkpoints WAL, and optimizes SQLite.

### Create project backup

Uses SQLite's backup API to create a consistent database copy in the project's backup directory.

### Restore project backup

Creates a safety copy of the current database, restores the selected managed backup, and verifies it before the project is reopened.

### Export diagnostic package

Creates a ZIP containing sanitized configuration, system information, database counts, integrity results, operation history, network events, and recent errors. Downloaded page contents are not included.

### Import an existing archive folder

Creates a safety backup and imports local HTML and text files as project documents.

## Media workflows

### Index and download selected media

Builds one combined CDX extension filter for all selected image/video types, indexes matching captures, applies the selected snapshot strategy, and downloads pending records.

### Index media only

Stores media captures without downloading binary files.

### Download pending media

Downloads media captures whose state is `pending`.

### Retry media errors

Retries selected or unresolved media failures. Existing successful files are not downloaded again.

## Archive-analysis workflows

### Run archive recovery and analysis

Uses saved documents to:

1. Canonicalize forum URLs.
2. Parse posts and reconstruct threads.
3. Run built-in and custom extractors.
4. Recover legacy player and embed URLs.
5. Optionally search allowed external hosts in Wayback.
6. Build exact and near-duplicate groups.
7. Compare adjacent snapshots.
8. Search for first and last appearances of extracted values.
9. Infer source-to-mirror provenance edges.
10. Write analysis reports.

### Rebuild forum threads only

Recreates only `forum_threads` and `forum_posts`.

### Merge another Archive Scout project

Creates a safety backup, then merges another project's stored research. Captures and media retain their identities; copied local files are placed under `captures/merged/` and `media/merged/`. Scan history, review status, notes, tags, and extraction results are preserved. FTS is rebuilt afterward.

## Media selection order

1. Build the included extension set.
2. Remove explicitly excluded extensions.
3. Remove image types when Images is disabled.
4. Remove video types when Videos is disabled.
5. Build one combined CDX extension filter.
6. Validate returned URL extensions and MIME types locally.
7. Apply earliest, latest, or all snapshot selection.

## Keyword scoring

The score combines field location, rule weight, exact-phrase bonuses, distinct matched concepts, same-sentence matches, same-paragraph matches, and nearby terms. URL and title matches are weighted above body matches. Repeated matches are capped per field. Required and excluded terms act as gates.
