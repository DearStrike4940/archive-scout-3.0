from __future__ import annotations

import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from ..events import Stopped
from ..runtime import ensure_frozen_bundle_available
from .transports import BackendUnavailable, TransportResponse


class CurlBackend:
    name = "curl"

    def __init__(self, connect_timeout: float, read_timeout: float) -> None:
        executable = shutil.which("curl")
        if not executable:
            raise BackendUnavailable("curl executable was not found")
        self.executable = executable
        self.connect_timeout = max(1.0, float(connect_timeout))
        self.read_timeout = max(1.0, float(read_timeout))

    def close(self) -> None:
        return

    @staticmethod
    def _parse_headers(raw: str) -> dict[str, str]:
        blocks = [block for block in raw.replace("\r\n", "\n").split("\n\n") if block.strip()]
        block = blocks[-1] if blocks else raw
        headers: dict[str, str] = {}
        for line in block.splitlines()[1:]:
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            headers[key.strip()] = value.strip()
        return headers

    def request(
        self,
        url: str,
        headers: dict[str, str],
        max_bytes: int,
        stop_event: threading.Event,
    ) -> TransportResponse:
        ensure_frozen_bundle_available()
        started = time.monotonic()
        with tempfile.TemporaryDirectory(prefix="archive-scout-curl-") as temp_dir:
            header_path = Path(temp_dir) / "headers.txt"
            body_path = Path(temp_dir) / "body.bin"
            command = [
                self.executable,
                "--location",
                "--compressed",
                "--http1.1",
                "--ipv4",
                "--silent",
                "--show-error",
                "--connect-timeout",
                str(int(self.connect_timeout)),
                "--max-time",
                str(int(self.connect_timeout + self.read_timeout)),
                "--max-filesize",
                str(int(max_bytes)),
                "--dump-header",
                str(header_path),
                "--output",
                str(body_path),
                "--write-out",
                "%{http_code}\n%{url_effective}",
            ]
            for key, value in headers.items():
                command.extend(["--header", f"{key}: {value}"])
            command.extend(["--", url])
            proc = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            while proc.poll() is None:
                if stop_event.wait(0.2):
                    proc.kill()
                    proc.wait(timeout=5)
                    raise Stopped
            stdout, stderr = proc.communicate()
            if proc.returncode != 0:
                message = (stderr or stdout or f"curl exited {proc.returncode}").strip()
                if proc.returncode == 28:
                    raise TimeoutError(message)
                raise OSError(message)
            lines = stdout.splitlines()
            status = int(lines[-2]) if len(lines) >= 2 and lines[-2].isdigit() else 0
            final_url = lines[-1] if lines else url
            data = body_path.read_bytes() if body_path.exists() else b""
            if len(data) > max_bytes:
                raise RuntimeError(f"response exceeds {max_bytes:,} bytes")
            raw_headers = header_path.read_text(encoding="iso-8859-1", errors="replace") if header_path.exists() else ""
            return TransportResponse(
                status=status,
                headers=self._parse_headers(raw_headers),
                final_url=final_url,
                data=data,
                backend=self.name,
                elapsed=time.monotonic() - started,
            )
