# Beta 1 interface

Archive Scout 3.0 Beta 1 reorganizes the application around a left navigation sidebar and a project dashboard.

## Simple mode

Simple mode shows:

```text
Dashboard
Sites and paths
Keyword sets
Results and search
Activity
```

It is intended for the common workflow of choosing a site, choosing keywords, starting a run, and reviewing results.

## Advanced mode

Advanced mode adds:

```text
CDX options
Media
Archive analysis
Settings
Scan history
Errors
```

Advanced controls include network backend, CDX endpoint/strategy, per-target settings, media recovery, custom extractors, project merging, and retry selection.

## Themes and scaling

The interface supports System, Light, and Dark appearance. Font scaling adjusts the main UI fonts without changing project data.

## Dashboard

The Dashboard shows capture, document, match, and unresolved-error counts. It also provides backup, restore, integrity, repair, diagnostics, import, operation selection, and quick-start guidance.

## Results

The results table is paginated in blocks of 500 rows. Review statuses have visual row colors, while filters, notes, tags, and exports remain available.

## Persistent interface state

Archive Scout remembers:

- window geometry;
- selected theme;
- Simple or Advanced mode;
- font scale.

These settings are stored in the user's application-support directory, not in the research project database.
