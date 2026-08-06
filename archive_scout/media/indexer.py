from __future__ import annotations

import hashlib
import json
import random
import re
import sqlite3
import threading
import time
from dataclasses import replace
from typing import Callable
from urllib.parse import urlsplit

from ..cdx.client import CDXRow, HttpClient, RateLimitDeferred, TransientRequestError, request_cdx_rows
from ..cdx.indexer import (
    PendingWindow,
    PagedBatch,
    _select_page_batch,
    decode_plan,
    encode_plan,
    index_windows,
    split_window,
    window_label,
)
from ..cdx.parallel import PageFetchResult, effective_page_workers, iter_cdx_pages
from ..cdx.parameters import (
    cdx_endpoints,
    cdx_query_signature,
    cdx_query_signatures,
    cdx_target_value,
    cdx_year_window,
    parse_num_pages,
    preferred_index_strategy,
)
from ..config import ProjectConfig
from ..database.repositories import (
    cdx_row_to_dict,
    get_or_create_media_target,
    record_error,
    upsert_media_capture,
    upsert_media_captures,
)
from ..downloads.rate_limit import FixedRateLimiter, SharedHostGate
from ..events import ConnectivityPaused, ProgressEvent, Stopped
from ..utils import json_value, parse_cdx_parameter_lines, utc_now
from .extensions import allowed_media_url, selected_extensions

ALL_EXTENSIONS_STATE = "__all__"


def media_query_signature(config: ProjectConfig, page_size: int | None = None) -> str:
    media = config.media.normalized()
    payload = {
        "from": config.from_date,
        "to": config.to_date,
        "filters": config.cdx_filters,
        "collapses": config.cdx_collapses,
        "extra": config.cdx_extra_params,
        "page_size": int(config.page_size if page_size is None else page_size),
        "targets": media.targets or config.targets,
        "extensions": selected_extensions(media),
        "strategy": media.snapshot_strategy,
        "embedded": media.discover_embedded,
        "external": media.allow_external_embeds,
        "single_query_per_target": True,
        "network_strategy": config.network.normalized().index_strategy,
    }
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def media_query_signatures(config: ProjectConfig) -> tuple[str, ...]:
    sizes = [config.page_size, 5000, 25000, 1000, 10000, 50000]
    return tuple(dict.fromkeys(media_query_signature(config, size) for size in sizes))


def media_index_state_signature(config: ProjectConfig, *, page_size: int | None = None, revision: int = 3) -> str:
    payload = {"media_query_signature": media_query_signature(config, page_size), "index_revision": int(revision)}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def media_signature_candidates(config: ProjectConfig) -> tuple[tuple[str, str], ...]:
    values: list[tuple[str, str]] = []
    for size in [config.page_size, 5000, 25000, 1000, 10000, 50000]:
        media_signature = media_query_signature(config, size)
        for revision in (3, 2):
            item = (media_signature, media_index_state_signature(config, page_size=size, revision=revision))
            if item not in values:
                values.append(item)
    return tuple(values)


def media_target_pattern(target: str, extension: str = "") -> str:
    return target if not extension else target.rstrip("*") + "*" + extension


def extension_filter_regex(extensions: list[str]) -> str:
    values = sorted({value.casefold().lstrip(".") for value in extensions if value.strip(".")})
    if not values:
        return r"(?!)"
    escaped = "|".join(re.escape(value) for value in values)
    # Historical sites frequently append broken tracking fragments such as
    # image.jpg&ref=thumb without a question mark. Accept those separators too.
    return rf"(?i).*\.(?:{escaped})(?:$|[?&#;].*)"


def build_media_params(
    config: ProjectConfig,
    pattern: str,
    start: str,
    end: str,
    resume: str | None = None,
    exact: bool = False,
    page_size: int | None = None,
    extensions: list[str] | None = None,
):
    query_target = pattern if exact else cdx_target_value(pattern, config.cdx_match_type)
    params = [
        ("url", query_target),
        ("from", start),
        ("to", end),
        ("output", "json"),
        ("fl", "timestamp,original,mimetype,statuscode,digest,length"),
    ]
    if exact:
        params.append(("matchType", "exact"))
    elif config.cdx_match_type:
        params.append(("matchType", config.cdx_match_type))
    params.extend(("filter", value) for value in config.cdx_filters)
    params.extend(("collapse", value) for value in config.cdx_collapses)
    if not exact and extensions:
        # One regex filter covers every selected extension. Archive Scout never
        # performs an extension-by-extension CDX index.
        params.append(("filter", "original:" + extension_filter_regex(extensions)))
    params.extend(parse_cdx_parameter_lines(config.cdx_extra_params))
    params.extend([("limit", str(page_size or config.page_size)), ("showResumeKey", "true")])
    if resume:
        params.append(("resumeKey", resume))
    return params


def build_media_num_pages_params(
    config: ProjectConfig,
    pattern: str,
    start: str,
    end: str,
    extensions: list[str],
    page_blocks: int,
):
    params = build_media_params(config, pattern, start, end, extensions=extensions)
    params = [(key, value) for key, value in params if key not in {"limit", "showResumeKey", "resumeKey"}]
    params.extend([("showNumPages", "true"), ("pageSize", str(max(1, page_blocks)))])
    return params


def build_media_paged_params(
    config: ProjectConfig,
    pattern: str,
    start: str,
    end: str,
    extensions: list[str],
    page: int,
    page_blocks: int,
):
    params = build_media_params(config, pattern, start, end, extensions=extensions)
    params = [(key, value) for key, value in params if key not in {"limit", "showResumeKey", "resumeKey"}]
    params.extend([("page", str(max(0, page))), ("pageSize", str(max(1, page_blocks)))])
    return params


def _apply_snapshot_strategy(database: sqlite3.Connection, signature: str, strategy: str) -> None:
    if strategy == "all":
        return
    direction = "ASC" if strategy == "earliest" else "DESC"
    now = utc_now()
    with database:
        database.execute("DROP TABLE IF EXISTS temp.archive_scout_media_keep")
        database.execute(
            "CREATE TEMP TABLE archive_scout_media_keep(id INTEGER PRIMARY KEY) WITHOUT ROWID"
        )
        database.execute(
            f"""
            INSERT INTO archive_scout_media_keep(id)
            SELECT id FROM (
                SELECT id,ROW_NUMBER() OVER(
                    PARTITION BY original_url ORDER BY timestamp {direction},id {direction}
                ) AS position
                FROM media_captures WHERE query_signature=?
            ) WHERE position=1
            """,
            (signature,),
        )
        database.execute(
            """
            UPDATE media_captures SET state='pending',updated_at=?
            WHERE query_signature=? AND state='skipped_strategy'
              AND id IN (SELECT id FROM archive_scout_media_keep)
            """,
            (now, signature),
        )
        database.execute(
            """
            UPDATE media_captures SET state='skipped_strategy',updated_at=?
            WHERE query_signature=? AND state!='downloaded'
              AND id NOT IN (SELECT id FROM archive_scout_media_keep)
            """,
            (now, signature),
        )
        database.execute("DROP TABLE archive_scout_media_keep")


def _save_media_state(
    database: sqlite3.Connection,
    target_id: int,
    year: int,
    signature: str,
    resume_key: str | None,
    complete: bool,
    seen: int,
    error_id: int | None,
) -> None:
    database.execute(
        """
        INSERT INTO media_index_state(
            target_id,extension,year,query_signature,resume_key,complete,seen,error_id,updated_at
        ) VALUES(?,?,?,?,?,?,?,?,?)
        ON CONFLICT(target_id,extension,year,query_signature) DO UPDATE SET
            resume_key=excluded.resume_key,
            complete=excluded.complete,
            seen=excluded.seen,
            error_id=excluded.error_id,
            updated_at=excluded.updated_at
        """,
        (target_id, ALL_EXTENSIONS_STATE, year, signature, resume_key, int(complete), seen, error_id, utc_now()),
    )


def _adopt_compatible_media_state(
    database: sqlite3.Connection,
    target_id: int,
    year: int,
    config: ProjectConfig,
    signature: str,
    state_signature: str,
) -> None:
    existing = database.execute(
        "SELECT 1 FROM media_index_state WHERE target_id=? AND extension=? AND year=? AND query_signature=?",
        (target_id, ALL_EXTENSIONS_STATE, year, state_signature),
    ).fetchone()
    if existing:
        return
    start, end = cdx_year_window(config, year) or (f"{year:04d}0101000000", f"{year:04d}1231235959")
    for candidate_signature, candidate_state in media_signature_candidates(config):
        if candidate_state == state_signature:
            continue
        state = database.execute(
            "SELECT resume_key,complete,seen,error_id,updated_at FROM media_index_state "
            "WHERE target_id=? AND extension=? AND year=? AND query_signature=?",
            (target_id, ALL_EXTENSIONS_STATE, year, candidate_state),
        ).fetchone()
        if not state:
            continue
        if candidate_signature != signature:
            database.execute(
                "UPDATE OR IGNORE media_captures SET query_signature=? "
                "WHERE target_id=? AND query_signature=? AND timestamp BETWEEN ? AND ?",
                (signature, target_id, candidate_signature, start, end),
            )
            database.execute(
                "DELETE FROM media_captures WHERE target_id=? AND query_signature=? AND timestamp BETWEEN ? AND ?",
                (target_id, candidate_signature, start, end),
            )
        database.execute(
            "INSERT INTO media_index_state(target_id,extension,year,query_signature,resume_key,complete,seen,error_id,updated_at) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (target_id, ALL_EXTENSIONS_STATE, year, state_signature, state["resume_key"], state["complete"], state["seen"], state["error_id"], state["updated_at"]),
        )
        database.execute(
            "DELETE FROM media_index_state WHERE target_id=? AND extension=? AND year=? AND query_signature=?",
            (target_id, ALL_EXTENSIONS_STATE, year, candidate_state),
        )
        return


def _reuse_completed_main_index(
    config: ProjectConfig,
    database: sqlite3.Connection,
    target: str,
    media_target_id: int,
    year: int,
    media_signature: str,
    state_signature: str,
) -> tuple[bool, int, int]:
    """Populate media rows from a completed normal index without another CDX pass."""
    target_row = database.execute("SELECT id FROM targets WHERE pattern=?", (target,)).fetchone()
    if not target_row:
        return False, 0, 0
    normal_target_id = int(target_row["id"])
    reusable_signature = None
    for candidate in cdx_query_signatures(config):
        row = database.execute(
            "SELECT complete FROM index_state WHERE target_id=? AND year=? AND query_signature=?",
            (normal_target_id, year, candidate),
        ).fetchone()
        if row and row["complete"]:
            reusable_signature = candidate
            break
    if reusable_signature is None:
        return False, 0, 0

    start, end = cdx_year_window(config, year) or (f"{year:04d}0101000000", f"{year:04d}1231235959")
    media = config.media.normalized()
    seen = 0
    changed = 0
    cursor = database.execute(
        "SELECT original_url,timestamp,mimetype,statuscode,digest,length FROM captures "
        "WHERE target_id=? AND query_signature=? AND timestamp BETWEEN ? AND ? ORDER BY id",
        (normal_target_id, reusable_signature, start, end),
    )
    while True:
        batch = cursor.fetchmany(10000)
        if not batch:
            break
        accepted: list[tuple[CDXRow, str, str]] = []
        seen += len(batch)
        for item in batch:
            row: CDXRow = (
                str(item["timestamp"]),
                str(item["original_url"]),
                str(item["mimetype"] or ""),
                str(item["statuscode"] or ""),
                str(item["digest"] or ""),
                str(item["length"] or 0),
            )
            allowed, kind, extension = allowed_media_url(row[1], media, row[2])
            if allowed and kind:
                accepted.append((row, kind, extension))
        changed += upsert_media_captures(
            database, accepted, media_target_id, media_signature, source_type="main_index"
        )
    _save_media_state(database, media_target_id, year, state_signature, None, True, seen, None)
    return True, seen, changed


def _wait_seconds(config: ProjectConfig, failures: int) -> float:
    network = config.network.normalized()
    base = min(network.retry_max_seconds, network.retry_base_seconds * 2 ** min(max(0, failures - 1), 6))
    return base * random.uniform(0.85, 1.15)


def _defer_media_window(
    config: ProjectConfig,
    database: sqlite3.Connection,
    plan,
    current: PendingWindow,
    target_id: int,
    year: int,
    signature: str,
    seen: int,
    error_id: int | None,
    target: str,
    label: str,
    exc: BaseException,
    completed: int,
    total: int,
    stop_event: threading.Event,
    callback: Callable[[ProgressEvent], None] | None,
) -> int:
    current.failures += 1
    current.page_size = max(25, (current.page_size or config.page_size) // 2)
    if current.strategy != "paged":
        current.page_blocks = max(1, current.page_blocks // 2)
    with database:
        error_id = record_error(
            database,
            "media_index",
            "transient_media_index_delay",
            f"{target} {label}: {type(exc).__name__}: {exc}",
            retryable=True,
        )
        if len(plan.pending) > 1:
            plan.pending.append(plan.pending.pop(0))
        _save_media_state(database, target_id, year, signature, encode_plan(plan), False, seen, error_id)
    network = config.network.normalized()
    threshold = network.failure_pause_threshold
    if plan.pending and all(item.failures >= threshold for item in plan.pending):
        raise ConnectivityPaused(
            "Wayback could not answer any remaining combined-media index window. "
            "The exact media queue was saved and can be continued with Resume."
        ) from exc
    if len(plan.pending) > 1:
        if callback:
            callback(ProgressEvent("media_index", "Deferred one unresponsive combined-media window behind the remaining queue; it will retry automatically.", completed, total))
        return error_id
    if not network.persistent_retries and current.failures >= max(3, config.retries):
        raise ConnectivityPaused(f"media indexing retry limit reached; progress was saved: {exc}") from exc
    if current.failures >= threshold:
        raise ConnectivityPaused(
            f"Wayback remained unreachable for this media window after {current.failures} recovery cycles. Progress was saved."
        ) from exc
    wait = _wait_seconds(config, current.failures)
    if callback:
        callback(ProgressEvent("media_index", f"Wayback is temporarily unavailable. Media indexing remains active and retries in {wait:.1f}s.", completed, total))
    stop_event.wait(wait)
    if stop_event.is_set():
        raise Stopped
    return error_id


def _resolve_media_strategy(current: PendingWindow, config: ProjectConfig, target: str) -> None:
    if current.strategy not in {"paged", "resume"}:
        current.strategy = preferred_index_strategy(config, target)
    if not current.pagination_supported and current.strategy == "paged":
        current.strategy = "resume"
    if current.page_blocks <= 0:
        current.page_blocks = config.network.normalized().page_blocks


def _request_media_paged_batch(
    config: ProjectConfig,
    client: HttpClient,
    target: str,
    current: PendingWindow,
    extensions: list[str],
    stop_event: threading.Event,
    consume_success: Callable[[PageFetchResult], None] | None = None,
) -> PagedBatch:
    endpoints = cdx_endpoints(config)
    network = config.network.normalized()
    if current.page_count < 0:
        payload = client.get_cdx_any(
            endpoints,
            build_media_num_pages_params(config, target, current.start, current.end, extensions, current.page_blocks),
            max_bytes=1024 * 1024,
            prefer_text=True,
        )
        current.page_count = parse_num_pages(payload)
        current.page = min(current.page, current.page_count)
        current.retry_pages = [page for page in current.retry_pages if page < current.page_count]
    if current.page >= current.page_count and not current.retry_pages:
        return PagedBatch([], [], True)

    page_workers = effective_page_workers(network.cdx_workers, current.page_blocks)
    pages, next_page = _select_page_batch(current, page_workers)
    if not pages:
        return PagedBatch([], [], True)
    results: list[PageFetchResult] = []
    for result in iter_cdx_pages(
        client,
        endpoints,
        pages,
        lambda page: build_media_paged_params(
            config, target, current.start, current.end, extensions, page, current.page_blocks
        ),
        stop_event,
        workers=page_workers,
        max_bytes=max(64 * 1024 * 1024, current.page_blocks * 12 * 1024 * 1024),
    ):
        if result.succeeded and consume_success is not None:
            consume_success(result)
        results.append(result)
    current.page = next_page
    retry_set = set(current.retry_pages)
    for result in results:
        if result.succeeded:
            retry_set.discard(result.page)
            current.page_failures.pop(result.page, None)
        else:
            retry_set.add(result.page)
            current.page_failures[result.page] = current.page_failures.get(result.page, 0) + 1
    current.retry_pages = sorted(retry_set)
    return PagedBatch(results, pages, current.page >= current.page_count and not current.retry_pages)


def _request_media_resume(
    config: ProjectConfig,
    client: HttpClient,
    target: str,
    current: PendingWindow,
    extensions: list[str],
) -> tuple[list[dict[str, str]], bool]:
    page_size = current.page_size or config.page_size
    result = request_cdx_rows(
        client,
        cdx_endpoints(config),
        build_media_params(
            config,
            target,
            current.start,
            current.end,
            current.resume_key,
            page_size=page_size,
            extensions=extensions,
        ),
        prefer_text=True,
    )
    rows, next_resume = result.rows, result.resume_key
    if next_resume:
        if next_resume == current.resume_key:
            raise TransientRequestError("CDX returned the same media resume key twice", splittable=True)
        current.resume_key = next_resume
        return rows, False
    return rows, True


def _media_failure_error(failures: list[PageFetchResult]) -> BaseException:
    if not failures:
        return TransientRequestError("unknown paged media CDX failure", splittable=False)
    return failures[0].error or TransientRequestError("unknown paged media CDX failure", splittable=False)


def _pagination_unavailable(exc: BaseException) -> bool:
    message = str(exc)
    return isinstance(exc, RuntimeError) and ("HTTP 400" in message or "page-count" in message)


def _permanent_media_page_error(exc: BaseException) -> bool:
    if isinstance(exc, (TransientRequestError, RateLimitDeferred)):
        return False
    if _pagination_unavailable(exc):
        return False
    return isinstance(exc, RuntimeError)


def _accept_media_rows(
    rows: list[CDXRow] | list[dict[str, str]],
    media,
) -> list[tuple[CDXRow | dict[str, str], str, str]]:
    """Filter media rows without expanding every compact CDX tuple to a dict."""
    accepted: list[tuple[CDXRow | dict[str, str], str, str]] = []
    for row in rows:
        if isinstance(row, dict):
            original = str(row.get("original") or "")
            mimetype = str(row.get("mimetype") or "")
        else:
            original = str(row[1] if len(row) > 1 else "")
            mimetype = str(row[2] if len(row) > 2 else "")
        allowed, kind, actual_extension = allowed_media_url(original, media, mimetype)
        if allowed and kind:
            accepted.append((row, kind, actual_extension))
    return accepted


def index_direct_media(
    config: ProjectConfig,
    database: sqlite3.Connection,
    client: HttpClient,
    stop_event: threading.Event,
    callback: Callable[[ProgressEvent], None] | None,
    signature: str,
    state_signature: str,
) -> None:
    media = config.media.normalized()
    targets = media.targets or config.targets
    extensions = selected_extensions(media)
    tasks: list[tuple[str, ProjectConfig, int, list[tuple[str, str]]]] = []
    for target in targets:
        target_config = config.for_target(target) if target in config.targets else config
        for year in range(target_config.from_year, target_config.to_year + 1):
            windows = index_windows(target_config, target, year)
            if windows:
                tasks.append((target, target_config, year, windows))
    total = sum(len(windows) for _, _, _, windows in tasks)
    completed = 0
    connection_failure_streak = 0

    for target, target_config, year, default_windows in tasks:
        if stop_event.is_set():
            raise Stopped
        target_id = get_or_create_media_target(database, target)
        with database:
            _adopt_compatible_media_state(
                database, target_id, year, target_config, signature, state_signature
            )
        state = database.execute(
            """
            SELECT resume_key,complete,seen,error_id FROM media_index_state
            WHERE target_id=? AND extension=? AND year=? AND query_signature=?
            """,
            (target_id, ALL_EXTENSIONS_STATE, year, state_signature),
        ).fetchone()
        if state and state["complete"]:
            completed += len(default_windows)
            if callback:
                callback(ProgressEvent("media_index", f"Already indexed selected media for {target} in {year}", completed, total))
            continue

        # If the normal site index is already complete, media discovery is a
        # local SQLite filter rather than another network-wide CDX traversal.
        if target in config.targets:
            with database:
                reused, reused_seen, reused_changed = _reuse_completed_main_index(
                    target_config,
                    database,
                    target,
                    target_id,
                    year,
                    signature,
                    state_signature,
                )
            if reused:
                completed += len(default_windows)
                if callback:
                    callback(
                        ProgressEvent(
                            "media_index",
                            f"Reused the completed site index for {target} {year}: checked {reused_seen:,}, stored {reused_changed:,} media captures without another CDX request.",
                            completed,
                            total,
                        )
                    )
                continue

        seen = int(state["seen"] or 0) if state else 0
        error_id = int(state["error_id"]) if state and state["error_id"] else None
        plan = decode_plan(state["resume_key"] if state else None, default_windows)
        completed += plan.completed
        total += max(0, plan.planned - len(default_windows))

        while plan.pending:
            if stop_event.is_set():
                with database:
                    _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                raise Stopped
            current = plan.pending[0]
            _resolve_media_strategy(current, target_config, target)
            label = window_label(current.start, current.end)
            detail = (
                f"pages {current.page:,}/{current.page_count:,}; {len(current.retry_pages)} retry"
                if current.strategy == "paged" and current.page_count >= 0
                else current.strategy
            )
            if callback:
                callback(ProgressEvent("media_index", f"Indexing all selected media for {target} during {label} ({detail})", completed, total))
            request_started = time.monotonic()
            try:
                if current.strategy == "paged":
                    received = 0
                    accepted_count = 0
                    changed = 0
                    write_seconds = 0.0

                    def store_completed_media_page(result: PageFetchResult) -> None:
                        nonlocal received, accepted_count, changed, write_seconds
                        page_received = len(result.rows)
                        accepted = _accept_media_rows(result.rows, media)
                        write_started = time.monotonic()
                        with database:
                            changed += upsert_media_captures(database, accepted, target_id, signature)
                        write_seconds += time.monotonic() - write_started
                        received += page_received
                        accepted_count += len(accepted)
                        result.rows.clear()
                        accepted.clear()

                    batch = _request_media_paged_batch(
                        target_config, client, target, current, extensions, stop_event,
                        store_completed_media_page,
                    )
                    request_seconds = max(0.0, time.monotonic() - request_started - write_seconds)
                    successes = batch.successful
                    failures = batch.failed
                    with database:
                        seen += received
                        if successes:
                            current.failures = 0
                            connection_failure_streak = 0
                            transient_failure_streak = 0
                        if batch.finished:
                            plan.pending.pop(0)
                            plan.completed += 1
                            completed += 1
                        complete = not plan.pending
                        _save_media_state(
                            database,
                            target_id,
                            year,
                            state_signature,
                            encode_plan(plan),
                            complete,
                            seen,
                            None if complete else error_id,
                        )
                        if error_id and not failures:
                            database.execute("UPDATE errors SET resolved=1,last_seen=? WHERE id=?", (utc_now(), error_id))
                            error_id = None
                    if callback:
                        callback(
                            ProgressEvent(
                                "media_index",
                                f"{target} {label}: {len(successes)}/{len(batch.requested_pages)} pages, received {received:,}, accepted {accepted_count:,}, stored {changed:,} — network {request_seconds:.1f}s, database {write_seconds:.2f}s",
                                completed,
                                total,
                            )
                        )
                    if not failures:
                        continue

                    failure_exc = _media_failure_error(failures)
                    if not successes and all(
                        isinstance(item.error, TransientRequestError) and item.error.connection_failed
                        for item in failures
                    ):
                        raise failure_exc
                    if max(current.page_failures.values(), default=0) >= 2:
                        current.strategy = "resume"
                        current.pagination_supported = False
                        current.page = 0
                        current.page_count = -1
                        current.resume_key = None
                        current.retry_pages.clear()
                        current.page_failures.clear()
                        current.failures = 0
                        current.page_size = max(100, target_config.page_size // 2)
                        parts = split_window(current)
                        if parts:
                            for part in parts:
                                part.strategy = "resume"
                                part.pagination_supported = False
                            plan.pending[0:1] = parts
                            added = len(parts) - 1
                            plan.planned += added
                            total += added
                        with database:
                            error_id = record_error(
                                database,
                                "media_index",
                                "slow_media_page_fallback",
                                f"{target} {label}: one combined-media CDX page failed repeatedly; switching the saved window to smaller resume-key work.",
                                retryable=True,
                            )
                            _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                        if callback:
                            callback(ProgressEvent("media_index", f"One combined-media CDX page remained slow for {target} {label}; successful pages were kept and the remaining range was converted to smaller resumable windows.", completed, total))
                        continue
                    if not successes and _pagination_unavailable(failure_exc):
                        current.pagination_supported = False
                        current.strategy = "resume"
                        current.page = 0
                        current.page_count = -1
                        current.retry_pages.clear()
                        current.page_failures.clear()
                        with database:
                            _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                        continue
                    permanent = next(
                        (item.error for item in failures if item.error and _permanent_media_page_error(item.error)),
                        None,
                    )
                    if permanent is not None:
                        raise permanent
                    with database:
                        error_id = record_error(
                            database,
                            "media_index",
                            "transient_media_page_retry",
                            f"{target} {label}: {len(failures)} media CDX page(s) requeued: {failure_exc}",
                            retryable=True,
                        )
                        _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                    if successes:
                        if callback:
                            callback(ProgressEvent("media_index", f"Requeued {len(failures)} slow media page(s) while continuing with untouched pages.", completed, total))
                        continue
                    error_id = _defer_media_window(
                        target_config, database, plan, current, target_id, year, state_signature,
                        seen, error_id, target, label, failure_exc, completed, total,
                        stop_event, callback,
                    )
                    continue

                rows, finished = _request_media_resume(
                    target_config, client, target, current, extensions
                )
                connection_failure_streak = 0
                transient_failure_streak = 0
                request_seconds = time.monotonic() - request_started
                received = len(rows)
                accepted = _accept_media_rows(rows, media)
                accepted_count = len(accepted)
                write_started = time.monotonic()
                with database:
                    changed = upsert_media_captures(database, accepted, target_id, signature)
                    seen += received
                    current.failures = 0
                    if finished:
                        plan.pending.pop(0)
                        plan.completed += 1
                        completed += 1
                    complete = not plan.pending
                    _save_media_state(database, target_id, year, state_signature, encode_plan(plan), complete, seen, None if complete else error_id)
                    if error_id:
                        database.execute("UPDATE errors SET resolved=1,last_seen=? WHERE id=?", (utc_now(), error_id))
                        error_id = None
                write_seconds = time.monotonic() - write_started
                if callback:
                    callback(
                        ProgressEvent(
                            "media_index",
                            f"{target} {label}: received {received:,}, accepted {accepted_count:,}, stored {changed:,} — network {request_seconds:.1f}s, database {write_seconds:.2f}s",
                            completed,
                            total,
                        )
                    )
                accepted.clear()
                rows.clear()
            except Stopped:
                with database:
                    _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                raise
            except (RateLimitDeferred, TransientRequestError) as exc:
                if isinstance(exc, TransientRequestError) and exc.connection_failed:
                    connection_failure_streak += 1
                    current.failures += 1
                    network = target_config.network.normalized()
                    with database:
                        error_id = record_error(
                            database,
                            "media_index",
                            "wayback_connection_unavailable",
                            f"{target} {label}: {exc}",
                            retryable=True,
                        )
                        _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                    if connection_failure_streak >= network.connection_failure_pause_threshold:
                        raise ConnectivityPaused(
                            f"Archive Scout could not establish a Wayback connection for media indexing after "
                            f"{connection_failure_streak} complete multi-backend attempts. The exact queue was saved."
                        ) from exc
                    wait = min(15.0, network.connection_retry_seconds * 2 ** max(0, connection_failure_streak - 1))
                    if callback:
                        callback(
                            ProgressEvent(
                                "network",
                                f"Wayback connection setup failed. Retrying the same saved media request in {wait:.1f}s "
                                f"({connection_failure_streak}/{network.connection_failure_pause_threshold})…",
                                completed,
                                total,
                            )
                        )
                    stop_event.wait(wait)
                    if stop_event.is_set():
                        raise Stopped
                    continue
                if isinstance(exc, TransientRequestError):
                    transient_failure_streak += 1
                    network = target_config.network.normalized()
                    no_progress_limit = min(
                        network.failure_pause_threshold,
                        4 if exc.timed_out else 6,
                    )
                    if transient_failure_streak >= no_progress_limit:
                        current.failures += 1
                        with database:
                            error_id = record_error(
                                database,
                                "media_index",
                                "transient_media_index_delay",
                                f"{target} {label}: {transient_failure_streak} consecutive transient CDX failures without a successful response: {exc}",
                                retryable=True,
                            )
                            _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                        raise ConnectivityPaused(
                            f"Wayback returned no usable media CDX response after {transient_failure_streak} consecutive recovery attempts. "
                            "The exact media queue was saved instead of looping indefinitely."
                        ) from exc
                if current.strategy == "paged" and current.page_count < 0:
                    current.strategy = "resume"
                    current.pagination_supported = False
                    current.page = 0
                    current.page_count = -1
                    current.retry_pages.clear()
                    current.page_failures.clear()
                    parts = split_window(current) if getattr(exc, "splittable", False) else []
                    if parts:
                        for part in parts:
                            part.strategy = "resume"
                            part.pagination_supported = False
                        plan.pending[0:1] = parts
                        added = len(parts) - 1
                        plan.planned += added
                        total += added
                    with database:
                        _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                    if callback:
                        callback(ProgressEvent("media_index", f"Paged CDX could not count media for {target} {label}; continuing with resumable smaller windows.", completed, total))
                    continue
                if current.strategy != "paged" and current.pagination_supported:
                    parts = split_window(current) if getattr(exc, "splittable", False) else []
                    if parts:
                        plan.pending[0:1] = parts
                        added = len(parts) - 1
                        plan.planned += added
                        total += added
                        with database:
                            _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                        if callback:
                            callback(ProgressEvent("media_index", f"Combined media CDX timed out for {target} {label}; split into {len(parts)} smaller windows.", completed, total))
                        continue
                    current.strategy = "paged"
                    current.page = 0
                    current.page_count = -1
                    current.resume_key = None
                    current.retry_pages.clear()
                    current.page_failures.clear()
                    with database:
                        _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                    if callback:
                        callback(ProgressEvent("media_index", f"Switching the combined media window to paged CDX indexing for {target} {label}.", completed, total))
                    continue
                error_id = _defer_media_window(
                    target_config, database, plan, current, target_id, year, state_signature,
                    seen, error_id, target, label, exc, completed, total, stop_event, callback,
                )
            except RuntimeError as exc:
                if current.strategy == "paged" and _pagination_unavailable(exc):
                    current.pagination_supported = False
                    current.strategy = "resume"
                    current.page = 0
                    current.page_count = -1
                    current.retry_pages.clear()
                    current.page_failures.clear()
                    with database:
                        _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                    continue
                with database:
                    error_id = record_error(database, "media_index", "index_failure", f"{target} {label}: {type(exc).__name__}: {exc}", retryable=False)
                    _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                raise
            except Exception as exc:
                with database:
                    error_id = record_error(
                        database,
                        "media_index",
                        "unexpected_media_index_error",
                        f"{target} {label}: {type(exc).__name__}: {exc}",
                        retryable=False,
                    )
                    _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                raise


def index_embedded_media(
    config: ProjectConfig,
    database: sqlite3.Connection,
    client: HttpClient,
    stop_event: threading.Event,
    callback: Callable[[ProgressEvent], None] | None,
    signature: str,
    *,
    external_only: bool = False,
) -> None:
    media = config.media.normalized()
    if not media.discover_embedded:
        return
    target_hosts = {
        urlsplit("http://" + target.split("/", 1)[0]).hostname or ""
        for target in (media.targets or config.targets)
    }
    candidates: dict[str, int] = {}
    for row in database.execute("SELECT id,links_json FROM documents ORDER BY id"):
        for link in json_value(row["links_json"], []):
            allowed, _, _ = allowed_media_url(link, media)
            if not allowed:
                continue
            host = (urlsplit(link).hostname or "").casefold()
            is_external = bool(host and host not in target_hosts)
            if external_only and not is_external:
                continue
            if not media.allow_external_embeds and is_external:
                continue
            candidates.setdefault(link, int(row["id"]))
    total = len(candidates)
    for index, (link, document_id) in enumerate(candidates.items(), 1):
        if stop_event.is_set():
            raise Stopped
        existing = database.execute("SELECT 1 FROM media_captures WHERE original_url=? AND query_signature=? LIMIT 1", (link, signature)).fetchone()
        if existing:
            continue
        if callback:
            callback(ProgressEvent("media_embed", f"Looking up embedded media {index:,}/{total:,}", index, total))
        try:
            result = request_cdx_rows(
                client,
                cdx_endpoints(config),
                build_media_params(config, link, config.from_date, config.to_date, exact=True),
                prefer_text=True,
            )
        except (TransientRequestError, RateLimitDeferred) as exc:
            with database:
                record_error(database, "media_embed", "transient_embed_lookup", f"{link}: {exc}", document_id=document_id, retryable=True)
            continue
        rows = result.rows
        if not rows:
            continue
        if media.snapshot_strategy == "earliest":
            chosen = [min(rows, key=lambda row: row[0])]
        elif media.snapshot_strategy == "latest":
            chosen = [max(rows, key=lambda row: row[0])]
        else:
            chosen = rows
        for compact in chosen:
            row = cdx_row_to_dict(compact)
            allowed, kind, extension = allowed_media_url(row["original"], media, row.get("mimetype", ""))
            if allowed and kind:
                with database:
                    source_type = "external_embedded" if (urlsplit(link).hostname or "").casefold() not in target_hosts else "embedded"
                    upsert_media_capture(database, row, None, signature, kind, extension, document_id, source_type)


def index_external_embedded_media(
    config: ProjectConfig,
    database: sqlite3.Connection,
    stop_event: threading.Event,
    callback: Callable[[ProgressEvent], None] | None = None,
) -> str:
    """Index only external media URLs found after saved text pages have been scanned."""
    config = config.normalized()
    config.media = replace(
        config.media.normalized(),
        enabled=True,
        discover_embedded=True,
        allow_external_embeds=True,
    )
    if not selected_extensions(config.media):
        raise ValueError("no image or video extensions remain after include/exclude filtering")
    signature = media_query_signature(config)
    limiter = FixedRateLimiter(config.cdx_delay)
    host_gate = SharedHostGate(config.rate_limit_base_pause, config.rate_limit_max_pause)

    def on_retry(attempt: int, total: int, reason: str, wait_seconds: float) -> None:
        if callback:
            stage = "rate_limit" if "all Wayback requests paused" in reason else "media_embed"
            if wait_seconds > 0:
                message = f"{reason}. Retry {attempt}/{total} in {wait_seconds:.1f}s…"
            else:
                message = reason
            callback(ProgressEvent(stage, message))

    client = HttpClient(
        limiter,
        1,
        min(max(config.read_timeout, 30.0), 120.0),
        config.user_agent,
        stop_event,
        retry_callback=on_retry,
        connect_timeout=min(max(config.connect_timeout, 5.0), 15.0),
        read_timeout=min(max(config.read_timeout, 30.0), 120.0),
        pool_size=config.network.normalized().cdx_workers,
        host_gate=host_gate,
        rate_limit_attempts=0,
        rate_limit_max_wait=0,
        network_backend=config.network.normalized().backend,
        trust_environment=config.network.normalized().trust_environment,
        network_callback=(lambda message: callback(ProgressEvent("network", message)) if callback else None),
    )
    try:
        index_embedded_media(
            config, database, client, stop_event, callback, signature, external_only=True
        )
        _apply_snapshot_strategy(database, signature, config.media.snapshot_strategy)
        return signature
    finally:
        client.close()


def index_media(
    config: ProjectConfig,
    database: sqlite3.Connection,
    stop_event: threading.Event,
    callback: Callable[[ProgressEvent], None] | None = None,
) -> str:
    config = config.normalized()
    media = config.media.normalized()
    if not (media.targets or config.targets):
        raise ValueError("add at least one media target or site target")
    if not selected_extensions(media):
        raise ValueError("no image or video extensions remain after include/exclude filtering")
    signature = media_query_signature(config)
    state_signature = media_index_state_signature(config)
    limiter = FixedRateLimiter(config.cdx_delay)
    host_gate = SharedHostGate(config.rate_limit_base_pause, config.rate_limit_max_pause)

    def on_retry(attempt: int, total: int, reason: str, wait_seconds: float) -> None:
        if callback:
            if "all Wayback requests paused" in reason:
                limit = f"/{total}" if total else ""
                message = f"{reason}. Shared pause {attempt}{limit} for {wait_seconds:.1f}s; one recovery probe will run next…"
                stage = "rate_limit"
            elif wait_seconds <= 0:
                message = reason
                stage = "network"
            else:
                message = f"CDX media request failed ({reason}). Retrying attempt {attempt}/{total} in {wait_seconds:.1f}s…"
                stage = "media_index"
            callback(ProgressEvent(stage, message))

    client = HttpClient(
        limiter,
        1,
        min(max(config.read_timeout, 30.0), 120.0),
        config.user_agent,
        stop_event,
        retry_callback=on_retry,
        connect_timeout=min(max(config.connect_timeout, 5.0), 15.0),
        read_timeout=min(max(config.read_timeout, 30.0), 120.0),
        pool_size=config.network.normalized().cdx_workers,
        host_gate=host_gate,
        rate_limit_attempts=0,
        rate_limit_max_wait=0,
        network_backend=config.network.normalized().backend,
        trust_environment=config.network.normalized().trust_environment,
        network_callback=(lambda message: callback(ProgressEvent("network", message)) if callback else None),
    )
    try:
        index_direct_media(config, database, client, stop_event, callback, signature, state_signature)
        index_embedded_media(config, database, client, stop_event, callback, signature)
        _apply_snapshot_strategy(database, signature, media.snapshot_strategy)
        return signature
    finally:
        client.close()
