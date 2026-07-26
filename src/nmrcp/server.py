from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .operations_console import write_operations_console
from .scoring import assess_inventory
from .waves import plan_waves


SERVER_SCHEMA_VERSION = "nmrcp_console_server_v1"


def prepare_console_site(
    site_dir: Path,
    *,
    inventory_path: Path = Path("examples/sample_inventory.json"),
) -> dict[str, Any]:
    site_dir.mkdir(parents=True, exist_ok=True)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    write_operations_console(inventory, assessments, waves, site_dir / "operations-console.html")
    write_index(site_dir / "index.html")
    payload = {
        "schema_version": SERVER_SCHEMA_VERSION,
        "status": "ready",
        "site_dir": str(site_dir.resolve()),
        "inventory_path": str(inventory_path),
        "entrypoint": "operations-console.html",
        "workloads": len(assessments),
        "waves": len(waves),
    }
    (site_dir / "site-manifest.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return payload


def serve_console(
    site_dir: Path,
    *,
    host: str = "127.0.0.1",
    port: int = 8080,
    inventory_path: Path = Path("examples/sample_inventory.json"),
) -> None:
    manifest = prepare_console_site(site_dir, inventory_path=inventory_path)
    handler = partial(ConsoleRequestHandler, directory=str(site_dir.resolve()), manifest=manifest)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"NMRCP console listening on http://{host}:{port}/")
    print(f"Serving {site_dir.resolve()}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopping NMRCP console")
    finally:
        server.server_close()


class ConsoleRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, manifest: dict[str, Any], **kwargs: Any) -> None:
        self.manifest = manifest
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:  # noqa: N802 - stdlib hook name.
        if self.path in {"/healthz", "/health"}:
            body = json.dumps({**self.manifest, "status": "ok"}, indent=2).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")


def write_index(path: Path) -> None:
    path.write_text(
        """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta http-equiv="refresh" content="0; url=operations-console.html">
  <title>NMRCP Console</title>
</head>
<body>
  <p><a href="operations-console.html">Open the NMRCP operations console</a></p>
</body>
</html>
""",
        encoding="utf-8",
    )
