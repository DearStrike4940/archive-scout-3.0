# Archive Scout 3.0 Roadmap

Archive Scout 3.0 begins with one combined milestone: the planned final Alpha 4 reliability pass and the planned Beta 1 visual redesign are delivered together as `3.0.0-beta.1` in the new Archive Scout 3.0 repository.

## Completed foundation

### Archive Scout 2.0 Alpha 1 — Project foundation

- resumable SQLite projects
- separate documents and scan results
- offline rescanning
- error-only retries
- migration from the original Archive Scout project format

### Archive Scout 2.0 Alpha 2 — Search, scoring, review, and media

- advanced keyword rules and scoring
- multiple keyword sets
- full-text search
- review labels, notes, and tags
- scan history
- direct image and video downloading
- combined extension selection

### Archive Scout 2.0 Alpha 3 — Archive recovery and analysis

- forum parsing and thread reconstruction
- identifier extraction
- legacy media recovery
- duplicate clustering
- snapshot comparison
- provenance research
- project merging

## Archive Scout 3.0 Beta 1 — Integration, reliability, and interface redesign

Completed:

- multi-backend Wayback transport using httpx, urllib3, and curl fallback
- system proxy and certificate-environment support
- standard CDX and timemap endpoint rotation
- paged CDX retrieval for broad queries
- resume-key retrieval for narrow queries
- automatic paging-to-resume fallback
- resumable date-window subdivision
- graceful network pause with exact queue preservation
- coordinated HTTP 429 recovery
- combined media indexing across all selected extensions
- schema version 5
- operation and network-event history
- automatic crash-state recovery
- project backups, restore, repair, and diagnostics
- automatic safety backup before destructive or large merge/import actions
- per-target settings
- dashboard and left navigation
- Simple and Advanced modes
- System, Light, and Dark themes
- font scaling and persistent interface state
- paginated results and review-status coloring
- first-run guide and keyboard shortcuts
- database/project-format feature freeze target

## Beta 2 — Public testing and optimization

Planned focus:

- results from long-running Windows, Linux, Intel Mac, and Apple Silicon testing
- network diagnostics gathered from real proxy, DNS, TLS, and firewall environments
- performance profiling on very large projects
- memory and database-size optimization
- clearer error explanations and recovery choices
- parser accuracy improvements
- accessibility review
- installer and first-launch improvements
- documentation based on common user workflows

No major database redesign is planned for Beta 2 unless Beta 1 testing identifies a data-loss or migration problem.

## Beta 3 — Stabilization

Planned focus:

- no major new feature category
- final migration testing
- project-format validation
- release-package verification
- security and dependency review
- performance benchmarks
- final default-setting review
- removal or disabling of features that remain unreliable

## Release candidates

```text
3.0.0-rc.1
3.0.0-rc.2, if required
```

Release candidates should contain only release-blocking fixes, documentation corrections, packaging fixes, and migration fixes.

## Stable release

```text
Archive Scout 3.0.0
```

Stable release criteria:

- all three platform packages build and launch consistently
- schema versions 2, 3, and 4 migrate to schema version 5 without data loss
- persistent Wayback contact failures pause cleanly instead of crashing or spinning indefinitely
- backup, restore, repair, diagnostics, resume, media, analysis, and merge workflows are tested on real projects
- the core database schema and project.json format are frozen
