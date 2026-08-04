from __future__ import annotations

import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Iterable

from ..events import Stopped
from .client import HttpClient
from .parameters import parse_cdx


@dataclass(slots=True)
class PageFetchResult:
    page: int
    rows: list[dict[str, str]]
    elapsed: float
    error: BaseException | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


def fetch_cdx_pages(
    client: HttpClient,
    endpoints: Iterable[str],
    pages: list[int],
    params_for_page: Callable[[int], list[tuple[str, str]]],
    stop_event: threading.Event,
    workers: int,
    max_bytes: int = 64 * 1024 * 1024,
) -> list[PageFetchResult]:
    """Fetch independent CDX pages concurrently with bounded memory and work.

    The caller chooses a small page batch. Results are returned in page order so
    state updates remain deterministic even though network completion is out of
    order. A failed page does not cancel successful siblings.
    """
    if not pages:
        return []
    worker_count = min(max(1, int(workers)), len(pages))
    endpoint_tuple = tuple(endpoints)

    def fetch(page: int) -> PageFetchResult:
        if stop_event.is_set():
            raise Stopped
        started = time.monotonic()
        try:
            payload = client.get_cdx_any(
                endpoint_tuple,
                params_for_page(page),
                max_bytes=max_bytes,
                prefer_text=True,
            )
            rows, _ = parse_cdx(payload)
            return PageFetchResult(page, rows, time.monotonic() - started)
        except Stopped:
            raise
        except BaseException as exc:
            return PageFetchResult(page, [], time.monotonic() - started, exc)

    futures: dict[Future[PageFetchResult], int] = {}
    results: list[PageFetchResult] = []
    executor = ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="archive-scout-cdx")
    try:
        for page in pages:
            futures[executor.submit(fetch, int(page))] = int(page)
        for future in as_completed(futures):
            if stop_event.is_set():
                raise Stopped
            results.append(future.result())
    except BaseException:
        for future in futures:
            future.cancel()
        raise
    finally:
        executor.shutdown(wait=True, cancel_futures=True)
    results.sort(key=lambda item: item.page)
    return results
