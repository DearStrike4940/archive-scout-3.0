from __future__ import annotations

import json
import os
import platform
import sqlite3
import sys
import zipfile
from pathlib import Path
from typing import Callable

from ..constants import VERSION
from ..events import ProgressEvent
from ..utils import utc_now


def _rows(database: sqlite3.Connection, query: str, params: tuple = ()) -> list[dict]:
    return [dict(row) for row in database.execute(query, params).fetchall()]


def export_diagnostics(
    root: Path,
    database: sqlite3.Connection,
    callback: Callable[[ProgressEvent], None] | None = None,
) -> Path:
    root = Path(root)
    output = root / "reports" / "diagnostics.zip"
    output.parent.mkdir(parents=True, exist_ok=True)
    system = {
        "generated_at": utc_now(),
        "archive_scout_version": VERSION,
        "python": sys.version,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "cpu_count": os.cpu_count(),
        "executable": sys.executable,
        "frozen": bool(getattr(sys, "frozen", False)),
    }
    counts = {}
    for table in (
        "targets", "captures", "documents", "scan_runs", "document_matches", "errors",
        "media_captures", "forum_threads", "forum_posts", "extractions", "network_events",
    ):
        try:
            counts[table] = int(database.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except Exception:
            counts[table] = None
    project = {}
    project_path = root / "project.json"
    if project_path.exists():
        try:
            project = json.loads(project_path.read_text(encoding="utf-8"))
            project.pop("retry_capture_ids", None)
            project.pop("retry_media_capture_ids", None)
        except Exception as exc:
            project = {"error": str(exc)}
    payloads = {
        "system.json": system,
        "counts.json": counts,
        "project-sanitized.json": project,
        "recent-errors.json": _rows(database, "SELECT * FROM errors ORDER BY id DESC LIMIT 500"),
        "recent-network-events.json": _rows(database, "SELECT * FROM network_events ORDER BY id DESC LIMIT 1000"),
        "recent-operations.json": _rows(database, "SELECT * FROM operation_runs ORDER BY id DESC LIMIT 100"),
        "sqlite-integrity.json": {"result": database.execute("PRAGMA integrity_check").fetchone()[0]},
    }
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name, payload in payloads.items():
            archive.writestr(name, json.dumps(payload, indent=2, ensure_ascii=False, default=str) + "\n")
        for name in ("integrity.txt", "repair.txt"):
            path = root / "reports" / name
            if path.exists():
                archive.write(path, f"reports/{name}")
    if callback:
        callback(ProgressEvent("diagnostics", f"Diagnostics written to {output}"))
    return output
