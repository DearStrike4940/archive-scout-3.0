from __future__ import annotations

import json
import random
import threading
import time
import urllib.parse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Callable, Iterable

import httpx
import urllib3

from ..constants import RETRYABLE_STATUS
from ..downloads.rate_limit import FixedRateLimiter, SharedHostGate
from ..events import Stopped
from ..network.transports import ResilientTransport, TransportExhaustedError, is_transport_timeout
from ..runtime import ensure_frozen_bundle_available, frozen_bundle_error_from_exception, is_missing_frozen_bundle_error
from ..utils import clean_space


class TransientRequestError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        status: int | None = None,
        timed_out: bool = False,
        splittable: bool = False,
        endpoint: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.timed_out = timed_out
        self.splittable = splittable
        self.endpoint = endpoint


class RateLimitDeferred(TransientRequestError):
    """Raised only after an optional server-directed wait budget is exhausted."""

    def __init__(self, message: str, *, status: int = 429, waited: float = 0.0) -> None:
        super().__init__(message, status=status, splittable=False)
        self.waited = float(waited)


def is_timeout_error(exc: BaseException) -> bool:
    if isinstance(exc, TransportExhaustedError):
        return exc.timed_out
    current: BaseException | None = exc
    visited: set[int] = set()
    timeout_types = (
        TimeoutError,
        httpx.TimeoutException,
        urllib3.exceptions.TimeoutError,
        urllib3.exceptions.ReadTimeoutError,
        urllib3.exceptions.ConnectTimeoutError,
    )
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, timeout_types):
            return True
        reason = getattr(current, "reason", None)
        if isinstance(reason, BaseException) and reason is not current:
            current = reason
            continue
        current = current.__cause__ or current.__context__
    return False


class HttpClient:
    """Wayback-aware HTTP client with independent connection fallbacks.

    The retry policy, shared 429 circuit, and fixed user-selected pacing remain in
    this class. Actual I/O is delegated to a persistent transport that can switch
    between httpx, urllib3, and the operating system's curl stack after genuine
    connection failures. An HTTP response never causes a backend switch; it is
    handled here so all workers follow the same Wayback policy.
    """

    def __init__(
        self,
        limiter: FixedRateLimiter,
        retries: int,
        timeout: float,
        user_agent: str,
        stop_event: threading.Event,
        retry_callback: Callable[[int, int, str, float], None] | None = None,
        *,
        connect_timeout: float | None = None,
        read_timeout: float | None = None,
        pool_size: int = 4,
        host_gate: SharedHostGate | None = None,
        rate_limit_attempts: int = 0,
        rate_limit_max_wait: float = 0.0,
        network_backend: str = "auto",
        trust_environment: bool = True,
        network_callback: Callable[[str], None] | None = None,
        transport: ResilientTransport | None = None,
    ) -> None:
        self.limiter = limiter
        self.retries = max(1, int(retries))
        self.timeout = max(1.0, float(timeout))
        self.connect_timeout = max(1.0, float(connect_timeout if connect_timeout is not None else timeout))
        self.read_timeout = max(1.0, float(read_timeout if read_timeout is not None else timeout))
        self.user_agent = user_agent
        self.stop_event = stop_event
        self.retry_callback = retry_callback
        self.host_gate = host_gate or SharedHostGate()
        self.rate_limit_attempts = max(0, int(rate_limit_attempts))
        self.rate_limit_max_wait = max(0.0, float(rate_limit_max_wait))
        self.transport = transport or ResilientTransport(
            pool_size=max(1, int(pool_size)),
            connect_timeout=self.connect_timeout,
            read_timeout=self.read_timeout,
            mode=network_backend,
            trust_env=trust_environment,
            callback=network_callback,
        )

    def close(self) -> None:
        self.transport.close()

    def get(self, url: str, max_bytes: int, accept: str = "*/*") -> dict:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": accept,
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Accept-Language": "en-US,en;q=0.8",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "DNT": "1",
        }
        ensure_frozen_bundle_available()
        generic_attempt = 0
        rate_attempt = 0
        total_rate_wait = 0.0

        while True:
            ensure_frozen_bundle_available()
            permit = self.host_gate.acquire_request(self.stop_event)
            try:
                with self.limiter.slot(self.stop_event):
                    if not self.host_gate.permit_is_current(permit):
                        self.host_gate.finish_request(permit, recovered=False)
                        continue
                    response = self.transport.request(url, headers, max_bytes, self.stop_event)
                status = int(response.status)

                if status == 429 or (status == 503 and response.headers.get("Retry-After")):
                    retry_after = parse_retry_after(response.headers.get("Retry-After"))
                    rate_attempt += 1
                    wait_seconds = self.host_gate.pause_for_rate_limit(retry_after, f"HTTP {status}")
                    total_rate_wait += wait_seconds
                    if self.retry_callback:
                        self.retry_callback(
                            rate_attempt,
                            self.rate_limit_attempts,
                            f"HTTP {status}; all Wayback requests paused",
                            wait_seconds,
                        )
                    attempts_exhausted = self.rate_limit_attempts > 0 and rate_attempt >= self.rate_limit_attempts
                    wait_exhausted = self.rate_limit_max_wait > 0 and total_rate_wait > self.rate_limit_max_wait
                    if attempts_exhausted or wait_exhausted:
                        raise RateLimitDeferred(
                            f"Wayback continued returning HTTP {status} after {rate_attempt} coordinated pauses. Progress was saved for resume.",
                            status=status,
                            waited=total_rate_wait,
                        )
                    continue

                self.host_gate.finish_request(permit, recovered=True)

                if status >= 400:
                    if status not in RETRYABLE_STATUS:
                        raise RuntimeError(f"HTTP {status}: {url}")
                    generic_attempt += 1
                    if generic_attempt >= self.retries:
                        raise TransientRequestError(
                            f"HTTP {status} after {self.retries} attempts: {url}",
                            status=status,
                            splittable=status in {408, 500, 502, 503, 504},
                        )
                    self.retry_wait(generic_attempt - 1, f"HTTP {status}", parse_retry_after(response.headers.get("Retry-After")))
                    continue

                return {
                    "data": response.data,
                    "status": status,
                    "headers": response.headers,
                    "final_url": response.final_url,
                    "backend": response.backend,
                    "elapsed": response.elapsed,
                }
            except (RateLimitDeferred, Stopped):
                self.host_gate.finish_request(permit, recovered=False)
                raise
            except RuntimeError as exc:
                self.host_gate.finish_request(permit, recovered=False)
                if isinstance(exc, TransientRequestError):
                    raise
                if is_missing_frozen_bundle_error(exc):
                    raise frozen_bundle_error_from_exception(exc) from exc
                # TransportExhaustedError subclasses RuntimeError so it must be
                # handled before deterministic local RuntimeError failures.
                if isinstance(exc, TransportExhaustedError):
                    timed_out = is_timeout_error(exc)
                    generic_attempt += 1
                    if generic_attempt >= self.retries:
                        raise TransientRequestError(
                            f"network failure for {url}: {exc}",
                            timed_out=timed_out,
                            splittable=True,
                        ) from exc
                    self.retry_wait(generic_attempt - 1, "read timeout" if timed_out else str(exc))
                    continue
                # Size limits, malformed URLs, and other local validation errors
                # remain permanent and should not enter the network retry queue.
                raise
            except (httpx.HTTPError, urllib3.exceptions.HTTPError, TimeoutError, OSError) as exc:
                self.host_gate.finish_request(permit, recovered=False)
                if is_missing_frozen_bundle_error(exc):
                    raise frozen_bundle_error_from_exception(exc) from exc
                timed_out = is_timeout_error(exc)
                generic_attempt += 1
                if generic_attempt >= self.retries:
                    raise TransientRequestError(
                        f"network failure for {url}: {exc}",
                        timed_out=timed_out,
                        splittable=True,
                    ) from exc
                self.retry_wait(generic_attempt - 1, "read timeout" if timed_out else str(exc))

    def get_json(self, url: str, params: list[tuple[str, str]], max_bytes: int = 64 * 1024 * 1024) -> object:
        return self.get_json_any((url,), params, max_bytes=max_bytes)

    def get_json_any(
        self,
        urls: Iterable[str],
        params: list[tuple[str, str]],
        max_bytes: int = 64 * 1024 * 1024,
    ) -> object:
        endpoints = list(dict.fromkeys(str(url) for url in urls if str(url).strip()))
        if not endpoints:
            raise ValueError("at least one endpoint is required")
        failures: list[tuple[str, TransientRequestError]] = []
        for endpoint in endpoints:
            full_url = endpoint + "?" + urllib.parse.urlencode(params, doseq=True)
            try:
                response = self.get(full_url, max_bytes, "application/json,text/plain,*/*")
                return parse_json_response(response["data"], endpoint)
            except TransientRequestError as exc:
                exc.endpoint = endpoint
                failures.append((endpoint, exc))
                if self.retry_callback and len(endpoints) > 1:
                    self.retry_callback(1, len(endpoints), f"Endpoint unavailable: {endpoint}; trying alternate CDX service", 0.0)
                continue
        timed_out = any(exc.timed_out for _, exc in failures)
        splittable = any(exc.splittable for _, exc in failures)
        summary = "; ".join(f"{endpoint}: {exc}" for endpoint, exc in failures)
        raise TransientRequestError(
            f"all CDX endpoints failed: {summary}",
            timed_out=timed_out,
            splittable=splittable or timed_out,
        ) from (failures[-1][1] if failures else None)

    def retry_wait(self, attempt: int, reason: str, retry_after: float | None = None) -> None:
        base = max(float(retry_after or 0), min(120.0, 2**attempt))
        wait_seconds = base * random.uniform(0.85, 1.2)
        if self.retry_callback:
            self.retry_callback(attempt + 2, self.retries, reason, wait_seconds)
        self.stop_event.wait(wait_seconds)
        if self.stop_event.is_set():
            raise Stopped


def parse_json_response(data: bytes, endpoint: str = "") -> object:
    raw = data.decode("utf-8", "replace").strip()
    if not raw:
        return []
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        preview = clean_space(raw[:500])
        lowered = preview.casefold()
        transient_markers = (
            "gateway",
            "temporarily unavailable",
            "timeout",
            "server error",
            "rate limit",
            "too many requests",
            "<html",
            "upstream",
        )
        if any(marker in lowered for marker in transient_markers):
            raise TransientRequestError(
                f"CDX returned transient non-JSON content from {endpoint}: {preview}",
                splittable=True,
                endpoint=endpoint,
            ) from exc
        raise RuntimeError(f"CDX returned non-JSON content from {endpoint}: {preview}") from exc


def parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        parsed = parsedate_to_datetime(value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (parsed - datetime.now(timezone.utc)).total_seconds())
    except Exception:
        return None
