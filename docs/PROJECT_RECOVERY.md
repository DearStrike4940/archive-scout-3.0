# Project recovery

## Automatic crash recovery

When a project opens, Archive Scout resets records left in transient states by an interrupted process:

```text
downloading → pending
running scan → interrupted
running operation → interrupted
```

This lets Resume continue without manually editing SQLite.

## Managed backups

The Dashboard can create and restore managed database backups. Backups use SQLite's backup API and are recorded in the project database.

Automatic safety backups are created before:

- database migration;
- archive-folder import;
- project repair;
- backup restoration;
- project merge.

The configured retention count removes older managed backups while leaving external copies untouched.

## Integrity check

The integrity report identifies:

- missing local files;
- empty files;
- size mismatches;
- invalid database references;
- unresolved errors;
- basic SQLite integrity results.

## Repair

Repair creates a safety backup and then can:

- reset stuck states;
- mark missing documents for redownload;
- rebuild full-text search;
- remove abandoned partial files;
- checkpoint WAL;
- optimize SQLite;
- record each repair action.

## Diagnostics

The diagnostic ZIP is intended for troubleshooting. It contains sanitized project configuration, platform/version information, table counts, operation history, network events, recent errors, and integrity results. It does not contain downloaded page bodies or media.

## Recommended recovery order

1. Pause the operation.
2. Create a backup.
3. Export diagnostics.
4. Run integrity check.
5. Run repair only when the report identifies project-state problems.
6. Resume interrupted work.
7. Restore an earlier backup only when repair cannot recover the current state.
