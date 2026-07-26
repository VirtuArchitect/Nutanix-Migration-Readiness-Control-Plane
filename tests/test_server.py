import json
import tempfile
import unittest
import urllib.request
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from http.server import ThreadingHTTPServer
from urllib.request import Request

from nmrcp.server import ConsoleRequestHandler, api_run_readiness, safe_inventory_path

from nmrcp.cli import main
from nmrcp.server import prepare_console_site


class ConsoleServerTests(unittest.TestCase):
    def test_prepare_console_site_writes_demo_and_health_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp) / "site"

            manifest = prepare_console_site(site_dir)

            self.assertEqual(manifest["status"], "ready")
            self.assertTrue((site_dir / "index.html").exists())
            self.assertTrue((site_dir / "operations-console.html").exists())
            payload = json.loads((site_dir / "site-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "nmrcp_console_server_v1")
            self.assertEqual(payload["entrypoint"], "operations-console.html")

    def test_cli_serve_generate_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp) / "site"

            with patch("sys.stdout"):
                code = main(["serve", "--site-dir", str(site_dir), "--generate-only"])

            self.assertEqual(code, 0)
            self.assertTrue((site_dir / "operations-console.html").exists())

    def test_health_endpoint_reports_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp)
            manifest = {"schema_version": "nmrcp_console_server_v1", "status": "ready"}
            handler = lambda *args, **kwargs: ConsoleRequestHandler(*args, directory=str(site_dir), manifest=manifest, **kwargs)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                port = server.server_address[1]
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/healthz", timeout=3) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()

            self.assertEqual(payload["status"], "ok")

    def test_connection_test_api_returns_redacted_live_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            site_dir = Path(tmp) / "site"
            data_dir = Path(tmp) / "data"
            manifest = {"schema_version": "nmrcp_console_server_v1", "status": "ready", "data_dir": str(data_dir), "site_dir": str(site_dir)}
            handler = lambda *args, **kwargs: ConsoleRequestHandler(*args, directory=str(site_dir), manifest=manifest, **kwargs)
            server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                body = json.dumps(
                    {
                        "vcenter": {
                            "endpoint": "http://127.0.0.1:1",
                            "username": "local-user",
                            "password": "super-secret",
                            "verify_tls": True,
                        }
                    }
                ).encode("utf-8")
                with patch(
                    "nmrcp.server.run_live_readiness",
                    return_value={
                        "schema_version": "nmrcp_live_readiness_v1",
                        "status": "pass",
                        "checks": [{"name": "vcenter", "status": "pass", "counts": {"vms": 2}}],
                        "security": {"credentials_serialized": False, "endpoint_values_serialized": False},
                    },
                ):
                    request = Request(
                        f"http://127.0.0.1:{server.server_address[1]}/api/connection-test",
                        data=body,
                        method="POST",
                        headers={"Content-Type": "application/json"},
                    )
                    with urllib.request.urlopen(request, timeout=3) as response:
                        payload = json.loads(response.read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()

            serialized = json.dumps(payload) + (data_dir / "live-readiness.json").read_text(encoding="utf-8")
            self.assertEqual(payload["status"], "pass")
            self.assertTrue((data_dir / "live-readiness.json").exists())
            self.assertNotIn("super-secret", serialized)
            self.assertNotIn("local-user", serialized)

    def test_run_readiness_api_writes_assessment_and_refreshes_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = root / "data"
            site_dir = root / "site"
            site_dir.mkdir()

            payload = api_run_readiness({}, data_dir, site_dir)

            self.assertEqual(payload["status"], "pass")
            self.assertTrue((data_dir / "assessment" / "assessment.json").exists())
            self.assertTrue((site_dir / "operations-console.html").exists())
            self.assertEqual(payload["summary"]["workloads"], 3)

    def test_inventory_path_is_limited_to_repo_or_console_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            outside = Path(tmp) / "outside.json"
            outside.write_text("{}", encoding="utf-8")

            with self.assertRaises(ValueError) as raised:
                safe_inventory_path(outside, Path("outputs/console-data"))

            self.assertIn("inside the repository", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
