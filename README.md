# Archive Scout 3.0

Archive Scout is a cross-platform desktop research application for indexing public Wayback Machine captures, downloading archived pages and media, searching saved material, reconstructing forums, recovering legacy embeds, comparing snapshots, and reviewing large archive projects.

Archive Scout 3.0 Beta 1.2 is the indexing-performance release. It preserves the complete Alpha 4/Beta 1 feature set, the Beta 1.1 CDX/media fixes, and database schema version 5 while replacing the slow serial broad-index path with bounded parallel CDX page retrieval.

One repository produces builds for Windows x64, Linux x64, and universal macOS for Intel and Apple Silicon.

## Downloads

- [Download for Windows x64](https://github.com/DearStrike4940/archive-scout-3.0/releases/download/archive-scout-3.0-beta-1.5/ArchiveScout-Windows-x64.1.zip)
- [Download for Linux x64](https://github.com/DearStrike4940/archive-scout-3.0/releases/download/archive-scout-3.0-beta-1.5/ArchiveScout-Linux-x64.zip)
- [Download for macOS Intel and Apple Silicon](https://github.com/DearStrike4940/archive-scout-3.0/releases/download/archive-scout-3.0-beta-1.5/ArchiveScout-macOS-Universal.zip)

### macOS installation

Extract the ZIP, drag `Archive Scout.app` into `/Applications`, and launch the installed copy. Quit Archive Scout completely before replacing it with a newer release. Do not move, rename, delete, or overwrite the `.app` while it is running.

## Beta 1.2 indexing-performance patch

Beta 1.2 was rebuilt after reviewing the supplied Wayback Machine Downloader archive engine rather than only its interface wrapper. The useful speed principles were retained and adapted to Archive Scout's resumable project database:

- Broad paged targets use one yearly CDX page queue instead of twelve serial month queues and twelve page-count requests.
- Up to six independent CDX pages are kept in flight while one shared fixed limiter caps starts at the default 80 requests per minute.
- Each page requests six CDX blocks by default, reducing the number of round trips without creating unbounded responses.
- Bulk pages request line-oriented text first. This avoids constructing and decoding very large JSON arrays and retains the Beta 1.1 malformed-response fallback.
- Successful pages are committed together in one SQLite transaction; a slow page is requeued without repeating successful sibling pages.
- If one page remains slow twice, successful page data is retained and only that saved range is converted to smaller resume-key windows instead of holding the yearly queue hostage.
- Page number, failed-page queue, failure count, and completed work are persisted for exact Resume behavior.
- A read timeout no longer repeats the same long wait through every HTTP backend and every CDX endpoint.
- CDX page requests are attempted once before returning to the persistent saved queue; recovery no longer waits through a duplicate full-timeout retry of the same expensive request.
- If a page-count request itself cannot complete, Archive Scout switches that window to resume-key retrieval and smaller saved intervals instead of looping forever.
- Media indexing uses the same parallel page engine. When the normal site index is already complete, media rows are filtered from SQLite locally and no second CDX traversal is made.

New projects use 25,000-row resume pages, six CDX page blocks, six page workers, and 0.75-second request spacing. Existing Beta 1 projects using the original defaults are migrated automatically, and compatible completed index states are adopted rather than discarded solely because the transport page size changed.

## What changed in Archive Scout 3.0 Beta 1

### Rebuilt Wayback connection layer

Archive Scout no longer depends on one Python HTTP path succeeding forever. In Automatic mode, it can use three independent connection methods:

1. `httpx`, with persistent connections and operating-system proxy support;
2. `urllib3`, as an independent pooled Python fallback;
3. the operating system's `curl`, when available, using HTTP/1.1 and IPv4 as a final fallback.

The last successful method is preferred on later requests. A failed method is temporarily cooled down while Archive Scout tries another one. This is intended to overcome Windows-specific proxy, TLS, DNS, connection-pool, and read-timeout failures without turning them into fatal application tracebacks.

Archive Scout also rotates between the standard CDX endpoint and the Wayback CDX timemap endpoint in Automatic mode. Broad wildcard and prefix searches can use page-based CDX retrieval, while narrow searches can use resume-key retrieval. If paging is unavailable for a query, Archive Scout falls back to resume keys.

### No endless fatal timeout loop

Temporary CDX failures are stored as resumable work. Archive Scout can:

- retry through another network backend;
- try the alternate CDX endpoint;
- divide only the failed date interval;
- reduce the page size for a difficult interval;
- persist the exact pending queue in SQLite;
- continue other pending windows when possible;
- pause cleanly after repeated complete-connection failures instead of crashing or rapidly looping forever.

A graceful network pause is not data loss. The exact queue remains available through **Resume interrupted work**. Permanent local problems, such as database corruption, missing permissions, invalid regular expressions, or a damaged application installation, are still reported rather than retried forever.

### Coordinated HTTP 429 recovery

Worker count and user-selected delays remain fixed. When Wayback returns HTTP 429, every worker waits behind one shared host gate. `Retry-After` is honored, simultaneous rate-limit responses are combined, and one recovery probe must succeed before the complete queue resumes.

### Combined media indexing

Direct image and video indexing performs one combined CDX request stream for all selected extensions per target and date window. It does not run a separate site index for `.jpg`, `.png`, `.gif`, `.mp4`, `.wmv`, and every other extension. Returned URLs are still validated locally against the included extensions, excluded extensions, MIME type, media category, and snapshot strategy.

### New visual interface

Beta 1 introduces:

- a left navigation sidebar;
- Dashboard, Sites, Keywords, Results, Activity, and advanced research pages;
- Simple and Advanced modes;
- System, Light, and Dark themes;
- adjustable interface font scaling;
- consistent spacing, cards, buttons, tables, progress displays, and status messages;
- review-status coloring;
- paginated result tables for large projects;
- a first-run guide;
- keyboard shortcuts;
- remembered window, theme, mode, and font settings.

### Project reliability and repair

Schema version 5 adds:

- operation-run history;
- structured network-event history;
- project-backup records;
- repair-action history;
- crash recovery for records left in `downloading` or `running` states;
- automatic safety backups before migration, import, repair, restore, and project merge;
- manual backup and restore controls;
- project repair and full-text-index rebuilding;
- sanitized diagnostic ZIP exports;
- per-target date, CDX, worker, and pacing settings.

## Main operations

### Index, download, scan, and report

Indexes public Wayback captures, downloads pending text pages, evaluates every selected keyword set, and writes separate reports for each set. Media can optionally run afterward.

### Index, download, scan, then download external embedded media

Completes the normal text index, download, and keyword scan first. It then reads the extracted links from every saved text page, indexes matching media hosted on external domains, and downloads that media only after the external-link discovery pass finishes. This does not run a broad crawl against each external host.

### Index URLs only

Stores capture metadata without downloading the pages.

### Download and scan pending URLs

Downloads records already indexed in the project and scans them with the selected keyword sets.

### Resume interrupted work

Continues the saved CDX window queue and restores interrupted downloads to pending. Completed windows and valid local files are not repeated.

### Rescan existing downloads

Reads saved files locally with new keyword sets. It makes no CDX requests and downloads nothing.

### Retry only errored URLs

Retries selected or unresolved text-page and media errors. Valid local text files are rescanned before a new download is attempted.

### Index and download selected media

Indexes all selected image and video extensions through one combined query stream, records matching captures, and downloads the requested snapshots.

### Run archive recovery and analysis

Processes saved documents without redownloading them. It can reconstruct forum threads, extract identifiers, recover embedded assets, cluster duplicates, compare snapshots, track provenance, and write analysis reports.

### Rebuild forum threads only

Rebuilds forum threads and posts from saved pages without rerunning the remaining archive-analysis stages.

### Merge another Archive Scout project

Creates a safety backup, then merges captures, documents, media, keyword sets, scan history, ranked matches, reviews, notes, tags, and extractions. Imported files remain separated under `captures/merged/` and `media/merged/`.

### Project maintenance

The Dashboard provides:

- Create project backup
- Restore project backup
- Check project integrity
- Repair project and rebuild indexes
- Export diagnostic package
- Import an existing archive folder

## Date formats

Start and end dates accept `YYYY`, `YYYYMM`, `YYYYMMDD`, `YYYYMMDDhhmmss`, `MM/DD/YYYY`, `MM-DD-YYYY`, `YYYY-MM-DD`, and `YYYY/MM/DD`. Human-readable dates are normalized before an operation starts, so invalid calendar dates produce a readable validation message instead of a worker traceback.

## Network settings

The Settings page provides:

```text
Network backend: Automatic, httpx, urllib3, or curl
CDX endpoint: Automatic, standard CDX, or timemap
Index strategy: Automatic, paged, or resume key
Parallel CDX page requests
CDX page blocks
Use operating-system proxy and certificate environment
Persistent recovery
Retry base delay
Maximum retry delay
Failures before graceful pause
```

Recommended defaults:

```text
Network backend: Automatic
CDX endpoint: Automatic
Index strategy: Automatic
Workers: 4
CDX request delay: 0.75 second
Download request delay: 0.5 seconds
Persistent recovery: Enabled
Failures before graceful pause: 8
```

For a broad target such as `example.com/*`, Automatic mode prefers a yearly paged CDX queue with bounded parallel page requests. For an exact URL, it prefers resume-key retrieval. The shared request-spacing control still limits how quickly requests begin, so raising page concurrency improves latency hiding rather than creating an uncontrolled request burst.

See [Archive Scout 3.0 network architecture](docs/ARCHIVE_SCOUT_3_NETWORK.md), [resilient indexing](docs/RESILIENT_INDEXING.md), and [network performance](docs/NETWORK_PERFORMANCE.md).

## Keyword rule syntax

Enter one rule per line:

```text
World Trade Center
required: WTC
high: jumper
exact: impact footage | weight=4
exclude: base jumping
regex: sky(light|line)\.mov | label=media filename
plaza | whole
Naudet | case
```

Supported prefixes:

```text
required:
optional:
high:
exclude:
exact:
regex:
```

Supported options after a spaced pipe:

```text
| weight=3
| whole
| case
| label=Shared concept
| type=required
```

Required rules must match. Excluded rules remove a page from ranked results. Repeated matches are capped per field so boilerplate cannot dominate a score.

## Full-text search and review

The Results and search page provides offline SQLite full-text search through downloaded documents. Searches can be filtered by scan, review status, score, title, URL, domain, and body text.

Review statuses are:

```text
Unreviewed
Relevant
Possibly relevant
False positive
Duplicate
Dead end
Needs follow-up
```

Notes, tags, and reviewer information remain attached when compatible projects are merged.

## Archive analysis

Archive Scout can:

- canonicalize forum URLs;
- detect generic, vBulletin, phpBB, Invision, Futaba, and 2channel-style forums;
- parse posts and reconstruct threads across snapshots;
- extract Google Video `docid` values and other legacy identifiers;
- recover Flash, Windows Media, RealPlayer, playlist, iframe, and script-config assets;
- run custom field-aware regular-expression extractors;
- search explicitly allowed external domains in Wayback;
- group exact and near-duplicate documents;
- compare adjacent snapshots;
- report first and last appearances;
- infer possible source-to-mirror relationships;
- merge compatible Archive Scout projects.

Provenance and first-capture results are research leads, not proof of authorship or original publication.

## Media settings

The Media page can download images, videos, or both. It supports:

- normal site targets or separate media targets;
- included extensions;
- excluded extensions;
- direct CDX discovery;
- media links found inside saved pages;
- optional external embedded media;
- earliest, latest, or every snapshot;
- maximum file size;
- original path preservation;
- resumable downloads and error-only retries.

Inclusion is applied first, then exclusions:

```text
Include: jpg, jpeg, png, gif, mp4, mov
Exclude: gif, mov
```

This downloads JPG, JPEG, PNG, and MP4 files.

## Project layout

```text
project.json
archive_scout.sqlite3
backups/
captures/
media/
reports/
```

Archive-analysis reports are stored in:

```text
reports/analysis/
```

Common reports include:

```text
analysis_summary.txt
forum_threads.tsv
extractions.tsv
legacy_assets.tsv
duplicate_groups.tsv
provenance.tsv
snapshot_diffs.tsv
first_appearances.tsv
```

## Upgrading from Archive Scout 2.0

1. Make an external copy of the complete project folder.
2. Open the copied `project.json` in Archive Scout 3.0.
3. The database is backed up and migrated to schema version 5.
4. Run **Check project integrity**.
5. Inspect `reports/integrity.txt` before deleting the old copy.

Schema versions 2, 3, and 4 are supported migration sources. Legacy Archive Scout 1.x projects are imported through the existing legacy migration path.

See [Migration](docs/MIGRATION.md) and [Project recovery](docs/PROJECT_RECOVERY.md).

## Interface shortcuts

```text
Ctrl/Cmd+S        Save project
Ctrl/Cmd+O        Open project
Ctrl/Cmd+Enter    Start operation
Escape            Pause and save
F5                Refresh dashboard
Ctrl/Cmd+F        Open results search
```

## Building from source

Requirements:

- Python 3.11 or newer
- Tkinter
- the packages in `requirements-runtime.txt`

```bash
python -m pip install -r requirements-runtime.txt
python run_app.py
```

Run tests:

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Compile-check:

```bash
python -m compileall -q archive_scout tests
```

GitHub workflows create:

```text
ArchiveScout-Windows-x64.zip
ArchiveScout-Linux-x64.tar.gz
ArchiveScout-macOS-Universal.zip
```

Each package has a corresponding `.sha256` file.

## Current limitations

- A network, DNS, proxy, firewall, or Wayback outage can still make progress impossible. Archive Scout now pauses and preserves the exact queue instead of treating repeated contact failure as successful work or looping aggressively.
- The supplied downloader engine was reviewed in full for this patch. Archive Scout intentionally does not copy its very large task batches or optional machine-learning dependency stack; it keeps bounded queues and cross-platform packaging safeguards.
- Forum parsing is heuristic and may need site-specific improvements.
- External embedded-asset recovery is disabled by default and requires an explicit allowlist.
- The applications are not commercially signed or notarized, so Windows and macOS may display first-launch security warnings.

## Release status

`3.0.0-beta.1.4` is a beta release. The core project format and major workflows are now intended to remain stable, but important projects should still be backed up before migration or large-scale testing.

See [CHANGELOG.md](CHANGELOG.md), [ROADMAP.md](ROADMAP.md), and [SOURCE_VALIDATION.txt](SOURCE_VALIDATION.txt).
