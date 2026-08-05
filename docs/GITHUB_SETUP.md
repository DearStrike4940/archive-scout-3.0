# GitHub setup

## Create the repository

Create a new repository named:

```text
Archive Scout 3.0
```

The URL-safe repository slug may appear as `Archive-Scout-3.0` or another GitHub-selected variation.

## Repository upload

Upload the contents of the extracted repository folder, not the enclosing folder itself. The repository root must directly contain:

```text
.github/
archive_scout/
docs/
examples/
packaging/
scripts/
tests/
README.md
pyproject.toml
requirements-build.txt
requirements-runtime.txt
run_app.py
```

On macOS, press `Command + Shift + .` in Finder to reveal `.github`.

## Test workflow

Open **Actions → Tests**. The matrix tests Windows, Linux, and Intel macOS with Python 3.11 and 3.12.

## Build workflow

Open **Actions → Build All Platforms → Run workflow**. A successful manual run creates three workflow artifacts.

A manual build does not create a GitHub Release because it is not running from a tag.

## Release

Publish the tag:

```text
v3.0.0-beta.1.5
```

The tagged build uploads:

```text
ArchiveScout-Windows-x64.zip
ArchiveScout-Windows-x64.zip.sha256
ArchiveScout-Linux-x64.tar.gz
ArchiveScout-Linux-x64.tar.gz.sha256
ArchiveScout-macOS-Universal.zip
ArchiveScout-macOS-Universal.zip.sha256
```

The release workflow creates or updates the tagged GitHub Release and attaches all six files.

Do not use workflow-artifact URLs as public download links. The README points to permanent GitHub Release asset names through `/releases/latest/download/`.
