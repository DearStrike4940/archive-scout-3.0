from __future__ import annotations

import os
import ssl
import threading
import time
import urllib.parse
from dataclasses import dataclass
from typing import Callable, Iterable

import httpx
import urllib3

from ..events import Stopped
from ..runtime import ensure_frozen_bundle_available

try:
    import truststore
except ImportError:  # pragma: no cover - exercised in minimal source installs
    truststore = None


class BackendUnavailable(RuntimeError):
    pass


class TransportExhaustedError(RuntimeError):
    def __init__(self, url: str, failures: list[tuple[str, BaseException]]) -> None:
        self.url = url
        self.failures = failures
        self.timed_out = any(is_transport_timeout(exc) for _, exc in failures)
        summary = "; ".join(f"{name}: {type(exc).__name__}: {exc}" for name, exc in failures)
        super().__init__(f"all network backends failed for {url}: {summary}")


@dataclass(slots=True)
class TransportResponse:
    status: int
    headers: dict[str, str]
    final_url: str
    data: bytes
    backend: str
    elapsed: float


def is_transport_timeout(exc: BaseException) -> bool:
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




def is_transport_read_timeout(exc: BaseException) -> bool:
    current: BaseException | None = exc
    visited: set[int] = set()
    read_types = (
        httpx.ReadTimeout,
        urllib3.exceptions.ReadTimeoutError,
    )
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        if isinstance(current, read_types):
            return True
        reason = getattr(current, "reason", None)
        if isinstance(reason, BaseException) and reason is not current:
            current = reason
            continue
        current = current.__cause__ or current.__context__
    return False

def _ssl_context() -> ssl.SSLContext:
    return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT) if truststore else ssl.create_default_context()


def _read_limited(chunks: Iterable[bytes], max_bytes: int, stop_event: threading.Event) -> bytes:
    data = bytearray()
    for chunk in chunks:
        if stop_event.is_set():
            raise Stopped
        if not chunk:
            continue
        data.extend(chunk)
        if len(data) > max_bytes:
            raise RuntimeError(f"response exceeds {max_bytes:,} bytes")
    return bytes(data)


class HttpxBackend:
    name = "httpx"

    def __init__(self, pool_size: int, connect_timeout: float, read_timeout: float, trust_env: bool = True) -> None:
        self.connect_timeout = max(1.0, float(connect_timeout))
        self.read_timeout = max(1.0, float(read_timeout))
        self.client = httpx.Client(
            verify=_ssl_context(),
            follow_redirects=True,
            max_redirects=10,
            trust_env=bool(trust_env),
            http2=False,
            limits=httpx.Limits(
                max_connections=max(2, int(pool_size)),
                max_keepalive_connections=max(1, int(pool_size)),
                keepalive_expiry=45.0,
            ),
            timeout=httpx.Timeout(
                connect=self.connect_timeout,
                read=self.read_timeout,
                write=self.connect_timeout,
                pool=max(5.0, self.connect_timeout),
            ),
        )

    def close(self) -> None:
        self.client.close()

    def request(
        self,
        url: str,
        headers: dict[str, str],
        max_bytes: int,
        stop_event: threading.Event,
    ) -> TransportResponse:
        ensure_frozen_bundle_available()
        started = time.monotonic()
        with self.client.stream("GET", url, headers=headers) as response:
            announced = response.headers.get("Content-Length")
            if announced and announced.isdigit() and int(announced) > max_bytes:
                raise RuntimeError(f"response exceeds {max_bytes:,} bytes")
            data = _read_limited(response.iter_bytes(1024 * 1024), max_bytes, stop_event)
            return TransportResponse(
                status=int(response.status_code),
                headers={str(k): str(v) for k, v in response.headers.items()},
                final_url=str(response.url),
                data=data,
                backend=self.name,
                elapsed=time.monotonic() - started,
            )


class Urllib3Backend:
    name = "urllib3"

    def __init__(self, pool_size: int, connect_timeout: float, read_timeout: float) -> None:
        self.timeout = urllib3.Timeout(connect=max(1.0, connect_timeout), read=max(1.0, read_timeout))
        self.pool = urllib3.PoolManager(
            num_pools=4,
            maxsize=max(2, int(pool_size)),
            block=True,
            ssl_context=_ssl_context(),
            retries=False,
        )

    def close(self) -> None:
        self.pool.clear()

    @staticmethod
    def _discard(response) -> None:
        if response is None:
            return
        try:
            response.drain_conn()
            response.release_conn()
        except Exception:
            try:
                response.close()
            except Exception:
                pass

    def request(
        self,
        url: str,
        headers: dict[str, str],
        max_bytes: int,
        stop_event: threading.Event,
    ) -> TransportResponse:
        ensure_frozen_bundle_available()
        started = time.monotonic()
        current_url = url
        response = None
        try:
            for _ in range(11):
                response = self.pool.request(
                    "GET",
                    current_url,
                    headers=headers,
                    preload_content=False,
                    redirect=False,
                    retries=False,
                    timeout=self.timeout,
                )
                if int(response.status) not in {301, 302, 303, 307, 308}:
                    break
                location = response.headers.get("Location")
                if not location:
                    break
                self._discard(response)
                response = None
                current_url = urllib.parse.urljoin(current_url, location)
            else:
                raise RuntimeError(f"too many redirects: {url}")

            assert response is not None
            announced = response.headers.get("Content-Length")
            if announced and str(announced).isdigit() and int(announced) > max_bytes:
                raise RuntimeError(f"response exceeds {max_bytes:,} bytes")
            data = _read_limited(response.stream(amt=1024 * 1024, decode_content=True), max_bytes, stop_event)
            result = TransportResponse(
                status=int(response.status),
                headers={str(k): str(v) for k, v in response.headers.items()},
                final_url=current_url,
                data=data,
                backend=self.name,
                elapsed=time.monotonic() - started,
            )
            self._discard(response)
            response = None
            return result
        finally:
            if response is not None:
                self._discard(response)



class ResilientTransport:
    """Persistent multi-backend HTTP transport.

    Auto mode prefers httpx because it honors operating-system proxy settings
    and falls back to urllib3 for a second independent Python stack. On Linux and
    macOS, the operating system's curl can remain an optional final fallback. The
    Windows build deliberately contains no external curl launcher. Network failures
    temporarily cool down only the failing backend; HTTP status responses are
    returned to the caller so Wayback-specific retry policy remains centralized.
    """

    def __init__(
        self,
        *,
        pool_size: int,
        connect_timeout: float,
        read_timeout: float,
        mode: str = "auto",
        trust_env: bool = True,
        callback: Callable[[str], None] | None = None,
    ) -> None:
        requested = mode.strip().casefold() or "auto"
        if requested not in {"auto", "httpx", "urllib3", "curl"}:
            raise ValueError("network backend must be auto, httpx, urllib3, or curl")
        self.callback = callback
        self.lock = threading.Lock()
        self.cooldown_until: dict[str, float] = {}
        self.last_success: str | None = None
        available: dict[str, object] = {
            "httpx": HttpxBackend(pool_size, connect_timeout, read_timeout, trust_env=trust_env),
            "urllib3": Urllib3Backend(pool_size, connect_timeout, read_timeout),
        }
        if os.name != "nt":
            try:
                import importlib

                curl_module = importlib.import_module("archive_scout.network.curl_backend")
                available["curl"] = curl_module.CurlBackend(connect_timeout, read_timeout)
            except (BackendUnavailable, ImportError):
                pass
        if requested == "auto":
            self.backends = available
            self.order = [name for name in ("httpx", "urllib3", "curl") if name in available]
        else:
            if requested not in available:
                raise BackendUnavailable(f"requested network backend is unavailable: {requested}")
            self.backends = {requested: available[requested]}
            self.order = [requested]
            for name, backend in available.items():
                if name != requested:
                    backend.close()

    @property
    def backend_names(self) -> tuple[str, ...]:
        return tuple(self.order)

    def close(self) -> None:
        for backend in self.backends.values():
            backend.close()

    def _ordered_names(self) -> list[str]:
        now = time.monotonic()
        with self.lock:
            preferred = self.last_success
            available = [name for name in self.order if self.cooldown_until.get(name, 0.0) <= now]
        if not available:
            # All backends are cooling down. Try all of them instead of blocking
            # forever; the caller owns retry/backoff and can save progress.
            available = list(self.order)
        if preferred in available:
            available.remove(preferred)
            available.insert(0, preferred)
        return available

    def request(
        self,
        url: str,
        headers: dict[str, str],
        max_bytes: int,
        stop_event: threading.Event,
    ) -> TransportResponse:
        failures: list[tuple[str, BaseException]] = []
        for name in self._ordered_names():
            if stop_event.is_set():
                raise Stopped
            backend = self.backends[name]
            try:
                response = backend.request(url, headers, max_bytes, stop_event)
                with self.lock:
                    changed = self.last_success != name
                    self.last_success = name
                    self.cooldown_until.pop(name, None)
                if changed and self.callback:
                    self.callback(f"Network backend: {name}")
                return response
            except Stopped:
                raise
            except RuntimeError as exc:
                # Size limits and other deterministic local validation failures
                # must not be retried using another backend.
                if str(exc).startswith("response exceeds") or "too many redirects" in str(exc):
                    raise
                failures.append((name, exc))
            except BaseException as exc:
                failures.append((name, exc))
            with self.lock:
                self.cooldown_until[name] = time.monotonic() + 30.0
            last_error = failures[-1][1]
            if is_transport_read_timeout(last_error):
                # Once a server has accepted the connection and stalled while
                # returning a CDX body, changing Python HTTP stacks normally
                # repeats the same long wait. Let the indexer retry or requeue
                # the page instead of multiplying one timeout by every backend.
                if self.callback:
                    self.callback(f"Network backend {name} reached Wayback but the response timed out; requeueing without repeating the full timeout on every backend…")
                break
            if self.callback:
                self.callback(f"Network backend {name} failed during connection setup; trying another connection method…")
        raise TransportExhaustedError(url, failures)
