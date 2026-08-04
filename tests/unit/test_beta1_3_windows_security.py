from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from archive_scout.network.transports import BackendUnavailable, ResilientTransport
from archive_scout.ui.dashboard import read_dashboard_counts


class DummyBackend:
    def __init__(self, *args, **kwargs):
        pass

    def close(self):
        pass


class Beta13WindowsSecurityTests(unittest.TestCase):
    def test_dashboard_counts_follow_database_changes(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "archive_scout.sqlite3"
            database = sqlite3.connect(path)
            database.executescript(
                """
                CREATE TABLE captures (id INTEGER PRIMARY KEY);
                CREATE TABLE documents (id INTEGER PRIMARY KEY);
                CREATE TABLE document_matches (id INTEGER PRIMARY KEY);
                CREATE TABLE errors (id INTEGER PRIMARY KEY, resolved INTEGER NOT NULL, ignored INTEGER NOT NULL);
                INSERT INTO captures DEFAULT VALUES;
                INSERT INTO documents DEFAULT VALUES;
                INSERT INTO document_matches DEFAULT VALUES;
                INSERT INTO errors(resolved, ignored) VALUES (0, 0);
                INSERT INTO errors(resolved, ignored) VALUES (1, 0);
                """
            )
            database.commit()
            self.assertEqual(read_dashboard_counts(path), {"captures": 1, "documents": 1, "matches": 1, "errors": 1})
            database.execute("INSERT INTO captures DEFAULT VALUES")
            database.execute("INSERT INTO documents DEFAULT VALUES")
            database.commit()
            self.assertEqual(read_dashboard_counts(path)["captures"], 2)
            self.assertEqual(read_dashboard_counts(path)["documents"], 2)
            database.close()

    def test_windows_auto_transport_does_not_load_curl(self):
        with patch("archive_scout.network.transports.os.name", "nt"), patch(
            "archive_scout.network.transports.HttpxBackend", DummyBackend
        ), patch("archive_scout.network.transports.Urllib3Backend", DummyBackend):
            transport = ResilientTransport(pool_size=2, connect_timeout=1, read_timeout=1)
            self.assertEqual(transport.backend_names, ("httpx", "urllib3"))
            transport.close()

    def test_windows_explicit_curl_is_unavailable(self):
        with patch("archive_scout.network.transports.os.name", "nt"), patch(
            "archive_scout.network.transports.HttpxBackend", DummyBackend
        ), patch("archive_scout.network.transports.Urllib3Backend", DummyBackend):
            with self.assertRaises(BackendUnavailable):
                ResilientTransport(pool_size=2, connect_timeout=1, read_timeout=1, mode="curl")

    def test_windows_build_is_hardened_and_release_signing_is_wired(self):
        root = Path(__file__).resolve().parents[2]
        build = (root / "scripts" / "build_windows.ps1").read_text(encoding="utf-8")
        workflow = (root / ".github" / "workflows" / "build-and-release.yml").read_text(encoding="utf-8")
        self.assertIn("--onedir", build)
        self.assertIn("--noupx", build)
        self.assertIn("--version-file", build)
        self.assertNotIn("ExecutionPolicy Bypass", build)
        self.assertIn("azure/artifact-signing-action@v2", workflow)
        self.assertIn("verify_windows_signature.ps1 -RequireSigned", workflow)
        self.assertIn("Require signing for tagged Windows releases", workflow)
        self.assertFalse((root / "packaging" / "windows" / "Install Archive Scout.cmd").exists())
        self.assertFalse((root / "packaging" / "windows" / "install.ps1").exists())
        main_window = (root / "archive_scout" / "ui" / "main_window.py").read_text(encoding="utf-8")
        self.assertIn("dashboard_refresh_loop", main_window)
        self.assertIn("read_dashboard_counts", main_window)

    def test_sbom_generator_writes_spdx_json(self):
        root = Path(__file__).resolve().parents[2]
        script = root / "scripts" / "generate_sbom.py"
        with tempfile.TemporaryDirectory() as temp:
            output = Path(temp) / "sbom.json"
            subprocess.run(
                [sys.executable, str(script), "--output", str(output), "--version", "test", "--root", "urllib3"],
                check=True,
            )
            payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["spdxVersion"], "SPDX-2.3")
        self.assertEqual(payload["packages"][0]["name"], "Archive Scout 3.0")


if __name__ == "__main__":
    unittest.main()
