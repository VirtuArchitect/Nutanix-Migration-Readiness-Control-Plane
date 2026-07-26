import json
import tempfile
import unittest
import urllib.request
from pathlib import Path
from threading import Thread
from unittest.mock import patch
from http.server import ThreadingHTTPServer

from nmrcp.server import ConsoleRequestHandler

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


if __name__ == "__main__":
    unittest.main()
