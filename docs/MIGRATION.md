# Migration

Archive Scout 3.0 Beta 1 uses database schema version 5.

## From Archive Scout 2.0 Alpha 3

Schema version 4 databases are backed up and upgraded in place. Schema version 5 adds operation history, network-event history, managed backup records, and repair-action records while preserving captures, documents, media, scans, reviews, notes, tags, errors, forum data, extractions, duplicates, snapshot differences, provenance, and merged-project records.

## From Archive Scout 2.0 Alpha 2

Schema version 3 databases are upgraded through schema version 4 to version 5 in one open operation.

## From Archive Scout 2.0 Alpha 1

Schema version 2 databases are upgraded through schema versions 3 and 4 to version 5.

## From Archive Scout 1.x

The legacy database is copied to:

```text
archive_scout.v1.backup.sqlite3
```

A new database is built, existing documents are imported, and previous matches are retained as a legacy scan run.

## Before migration

1. Quit the old Archive Scout application.
2. Make an external copy of the complete project folder.
3. Open the copied `project.json` in Archive Scout 3.0.
4. Do not interrupt the first database open.

Archive Scout creates an additional pre-migration database backup when possible.

## After migration

Run **Check project integrity** and inspect:

```text
reports/integrity.txt
```

Then create a managed project backup from the Dashboard. Do not delete the old project copy until indexing, rescanning, review data, media, and analysis results have been checked.
