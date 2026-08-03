from __future__ import annotations

import hashlib
import json
import random
import re
import sqlite3
import threading
from collections import defaultdict
from typing import Callable
from urllib.parse import urlsplit

from ..cdx.client import HttpClient, RateLimitDeferred, TransientRequestError
from ..cdx.indexer import PendingWindow, decode_plan, encode_plan, month_windows, split_window, window_label
from ..cdx.parameters import cdx_endpoints, cdx_target_value, parse_cdx, parse_num_pages, preferred_index_strategy
from ..config import ProjectConfig
from ..database.repositories import get_or_create_media_target, record_error, upsert_media_capture, upsert_media_captures
from ..downloads.rate_limit import FixedRateLimiter, SharedHostGate
from ..events import ConnectivityPaused, ProgressEvent, Stopped
from ..utils import json_value, parse_cdx_parameter_lines, utc_now
from .extensions import allowed_media_url, selected_extensions

ALL_EXTENSIONS_STATE = "__all__"


def media_query_signature(config: ProjectConfig) -> str:
    media = config.media.normalized()
    payload = {
        "from": config.from_date,
        "to": config.to_date,
        "filters": config.cdx_filters,
        "collapses": config.cdx_collapses,
        "extra": config.cdx_extra_params,
        "page_size": config.page_size,
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


def media_index_state_signature(config: ProjectConfig) -> str:
    payload = {"media_query_signature": media_query_signature(config), "index_revision": 2}
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


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
    rows = database.execute(
        "SELECT id,original_url,timestamp,state FROM media_captures WHERE query_signature=? ORDER BY original_url,timestamp",
        (signature,),
    ).fetchall()
    grouped: dict[str, list[sqlite3.Row]] = defaultdict(list)
    for row in rows:
        grouped[row["original_url"]].append(row)
    with database:
        for items in grouped.values():
            keep = items[0] if strategy == "earliest" else items[-1]
            for item in items:
                if item["id"] == keep["id"]:
                    if item["state"] == "skipped_strategy":
                        database.execute("UPDATE media_captures SET state='pending',updated_at=? WHERE id=?", (utc_now(), item["id"]))
                elif item["state"] != "downloaded":
                    database.execute("UPDATE media_captures SET state='skipped_strategy',updated_at=? WHERE id=?", (utc_now(), item["id"]))


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


def _request_media_window(
    config: ProjectConfig,
    client: HttpClient,
    target: str,
    current: PendingWindow,
    extensions: list[str],
) -> tuple[list[dict[str, str]], bool]:
    if current.strategy not in {"paged", "resume"}:
        current.strategy = preferred_index_strategy(config, target)
    endpoints = cdx_endpoints(config)
    if current.strategy == "paged" and current.pagination_supported:
        if current.page_count < 0:
            payload = client.get_json_any(
                endpoints,
                build_media_num_pages_params(config, target, current.start, current.end, extensions, current.page_blocks),
                max_bytes=1024 * 1024,
            )
            current.page_count = parse_num_pages(payload)
        if current.page >= current.page_count:
            return [], True
        payload = client.get_json_any(
            endpoints,
            build_media_paged_params(config, target, current.start, current.end, extensions, current.page, current.page_blocks),
        )
        rows, _ = parse_cdx(payload)
        current.page += 1
        return rows, current.page >= current.page_count

    page_size = current.page_size or config.page_size
    payload = client.get_json_any(
        endpoints,
        build_media_params(config, target, current.start, current.end, current.resume_key, page_size=page_size, extensions=extensions),
    )
    rows, next_resume = parse_cdx(payload)
    if next_resume:
        if next_resume == current.resume_key:
            raise TransientRequestError("CDX returned the same media resume key twice", splittable=True)
        current.resume_key = next_resume
        return rows, False
    return rows, True


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
            windows = month_windows(target_config, year)
            if windows:
                tasks.append((target, target_config, year, windows))
    total = sum(len(windows) for _, _, _, windows in tasks)
    completed = 0

    for target, target_config, year, default_windows in tasks:
        if stop_event.is_set():
            raise Stopped
        target_id = get_or_create_media_target(database, target)
        state = database.execute(
            """
            SELECT resume_key,complete,seen,error_id FROM media_index_state
            WHERE target_id=? AND extension=? AND year=? AND query_signature=?
            """,
            (target_id, ALL_EXTENSIONS_STATE, year, state_signature),
        ).fetchone()
        if state and state["complete"]:
            completed += len(default_windows)
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
            label = window_label(current.start, current.end)
            if callback:
                callback(ProgressEvent("media_index", f"Indexing all selected media for {target} during {label} ({current.strategy})", completed, total))
            try:
                rows, finished = _request_media_window(target_config, client, target, current, extensions)
                accepted: list[tuple[dict[str, str], str, str]] = []
                for row in rows:
                    allowed, kind, actual_extension = allowed_media_url(row["original"], media, row.get("mimetype", ""))
                    if allowed and kind:
                        accepted.append((row, kind, actual_extension))
                with database:
                    changed = upsert_media_captures(database, accepted, target_id, signature)
                    seen += len(rows)
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
                if callback:
                    callback(ProgressEvent("media_index", f"{target} {label}: received {len(rows):,}, accepted {len(accepted):,}, stored {changed:,}", completed, total))
            except Stopped:
                with database:
                    _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                raise
            except (RateLimitDeferred, TransientRequestError) as exc:
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
                    with database:
                        _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                    if callback:
                        callback(ProgressEvent("media_index", f"Switching the combined media window to paged CDX indexing for {target} {label}.", completed, total))
                    continue
                error_id = _defer_media_window(target_config, database, plan, current, target_id, year, state_signature, seen, error_id, target, label, exc, completed, total, stop_event, callback)
            except RuntimeError as exc:
                if current.strategy == "paged" and ("HTTP 400" in str(exc) or "page-count" in str(exc)):
                    current.pagination_supported = False
                    current.strategy = "resume"
                    current.page = 0
                    current.page_count = -1
                    with database:
                        _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                    continue
                with database:
                    error_id = record_error(database, "media_index", "index_failure", f"{target} {label}: {type(exc).__name__}: {exc}", retryable=False)
                    _save_media_state(database, target_id, year, state_signature, encode_plan(plan), False, seen, error_id)
                raise
            except Exception as exc:
                error_id = _defer_media_window(target_config, database, plan, current, target_id, year, state_signature, seen, error_id, target, label, exc, completed, total, stop_event, callback)


def index_embedded_media(
    config: ProjectConfig,
    database: sqlite3.Connection,
    client: HttpClient,
    stop_event: threading.Event,
    callback: Callable[[ProgressEvent], None] | None,
    signature: str,
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
            if not media.allow_external_embeds and host not in target_hosts:
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
            payload = client.get_json_any(cdx_endpoints(config), build_media_params(config, link, config.from_date, config.to_date, exact=True))
        except (TransientRequestError, RateLimitDeferred) as exc:
            with database:
                record_error(database, "media_embed", "transient_embed_lookup", f"{link}: {exc}", document_id=document_id, retryable=True)
            continue
        rows, _ = parse_cdx(payload)
        if not rows:
            continue
        if media.snapshot_strategy == "earliest":
            chosen = [min(rows, key=lambda row: row["timestamp"])]
        elif media.snapshot_strategy == "latest":
            chosen = [max(rows, key=lambda row: row["timestamp"])]
        else:
            chosen = rows
        for row in chosen:
            allowed, kind, extension = allowed_media_url(row["original"], media, row.get("mimetype", ""))
            if allowed and kind:
                with database:
                    upsert_media_capture(database, row, None, signature, kind, extension, document_id, "embedded")


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
        min(config.retries, 2),
        min(max(config.read_timeout, 20.0), 90.0),
        config.user_agent,
        stop_event,
        retry_callback=on_retry,
        connect_timeout=min(max(config.connect_timeout, 5.0), 45.0),
        read_timeout=min(max(config.read_timeout, 20.0), 90.0),
        pool_size=2,
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
