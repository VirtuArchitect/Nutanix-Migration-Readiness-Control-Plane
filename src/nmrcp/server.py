from __future__ import annotations

import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from .collection_workflow import collect_sources
from .connectors import EndpointConfig
from .environment_access import environment_access_options, evaluate_environment_access
from .evidence import write_assessment
from .live_readiness import run_live_readiness
from .operations_console import write_operations_console
from .scoring import assess_inventory
from .tester_report import write_tester_report
from .waves import plan_waves


SERVER_SCHEMA_VERSION = "nmrcp_console_server_v1"


def prepare_console_site(
    site_dir: Path,
    *,
    inventory_path: Path = Path("examples/sample_inventory.json"),
    data_dir: Path | None = None,
) -> dict[str, Any]:
    site_dir.mkdir(parents=True, exist_ok=True)
    data_dir = data_dir or (site_dir / "data")
    data_dir.mkdir(parents=True, exist_ok=True)
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    write_operations_console(inventory, assessments, waves, site_dir / "operations-console.html")
    write_index(site_dir / "index.html")
    payload = {
        "schema_version": SERVER_SCHEMA_VERSION,
        "status": "ready",
        "site_dir": str(site_dir.resolve()),
        "data_dir": str(data_dir.resolve()),
        "inventory_path": str(inventory_path),
        "entrypoint": "operations-console.html",
        "workloads": len(assessments),
        "waves": len(waves),
        "api_endpoints": [
            "/api/connection-test",
            "/api/collect-sources",
            "/api/run-readiness",
            "/api/tester-report",
            "/api/environment-access",
        ],
        "environment_access": environment_access_options(),
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

    def do_POST(self) -> None:  # noqa: N802 - stdlib hook name.
        try:
            payload = self.read_json_body()
            if self.path == "/api/connection-test":
                self.send_json(api_connection_test(payload, self.data_dir()))
                return
            if self.path == "/api/collect-sources":
                self.send_json(api_collect_sources(payload, self.data_dir()))
                return
            if self.path == "/api/run-readiness":
                self.send_json(api_run_readiness(payload, self.data_dir(), self.site_dir()))
                return
            if self.path == "/api/tester-report":
                self.send_json(api_tester_report(self.data_dir()))
                return
            if self.path == "/api/environment-access":
                self.send_json(api_environment_access(payload))
                return
            self.send_json({"status": "fail", "errors": ["Unknown API endpoint"]}, status=404)
        except ValueError as exc:
            self.send_json({"status": "fail", "errors": [str(exc)]}, status=400)
        except Exception as exc:  # noqa: BLE001 - sanitized API boundary
            self.send_json({"status": "fail", "errors": [sanitized_error(exc)]}, status=500)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"{self.address_string()} - {format % args}")

    def read_json_body(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length", "0") or "0")
        if length > 64 * 1024:
            raise ValueError("Request body is too large")
        raw = self.rfile.read(length).decode("utf-8") if length else "{}"
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("Request body must be a JSON object")
        return payload

    def send_json(self, payload: dict[str, Any], status: int = 200) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def data_dir(self) -> Path:
        return Path(str(self.manifest.get("data_dir") or "outputs/console-data"))

    def site_dir(self) -> Path:
        return Path(str(self.manifest.get("site_dir") or "outputs/console-site"))


def api_connection_test(payload: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    vcenter_config = endpoint_config_from_payload(payload.get("vcenter"))
    prism_config = endpoint_config_from_payload(payload.get("prism"))
    result = run_live_readiness(
        vcenter_config=vcenter_config,
        prism_config=prism_config,
        require_vcenter=bool(payload.get("require_vcenter")),
        require_prism=bool(payload.get("require_prism")),
    )
    data_dir.mkdir(parents=True, exist_ok=True)
    proof_path = data_dir / "live-readiness.json"
    proof_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return {
        "schema_version": "nmrcp_console_connection_test_v1",
        "status": result["status"],
        "proof": str(proof_path),
        "result": result,
    }


def api_collect_sources(payload: dict[str, Any], data_dir: Path) -> dict[str, Any]:
    vcenter_config = required_endpoint_config(payload.get("vcenter"), "vCenter")
    prism_config = required_endpoint_config(payload.get("prism"), "Prism Central")
    source_dir = data_dir / "source-collection"
    summary = collect_sources(
        vcenter_config,
        prism_config,
        source_dir,
        vcenter_details_limit=int(payload.get("vcenter_details_limit") or 250),
        prism_page_size=int(payload.get("prism_page_size") or 500),
        prism_max_pages=int(payload.get("prism_max_pages") or 20),
    )
    return {
        "schema_version": "nmrcp_console_collection_v1",
        "status": summary["status"],
        "source_dir": str(source_dir),
        "summary": summary,
    }


def api_run_readiness(payload: dict[str, Any], data_dir: Path, site_dir: Path) -> dict[str, Any]:
    collected_inventory = data_dir / "source-collection" / "vcenter-inventory.json"
    requested_inventory = safe_inventory_path(Path(str(payload.get("inventory_path"))), data_dir) if payload.get("inventory_path") else None
    inventory_path = collected_inventory if bool(payload.get("use_collected")) and collected_inventory.exists() else requested_inventory
    if inventory_path is None:
        inventory_path = Path("examples/sample_inventory.json")
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    assessment_dir = data_dir / "assessment"
    write_assessment(inventory, assessments, waves, assessment_dir)
    write_operations_console(inventory, assessments, waves, site_dir / "operations-console.html")
    return {
        "schema_version": "nmrcp_console_readiness_run_v1",
        "status": "pass",
        "inventory_path": str(inventory_path),
        "assessment_dir": str(assessment_dir),
        "console": "operations-console.html",
        "summary": {
            "workloads": len(assessments),
            "waves": len(waves),
            "ready": sum(1 for item in assessments if item.readiness == "ready"),
            "research": sum(1 for item in assessments if item.readiness == "research"),
            "prepare": sum(1 for item in assessments if item.readiness == "prepare"),
            "blocked": sum(1 for item in assessments if item.readiness == "blocked"),
        },
    }


def api_tester_report(data_dir: Path) -> dict[str, Any]:
    report_path = data_dir / "tester-report.md"
    json_path = data_dir / "tester-report.json"
    report = write_tester_report(data_dir, report_path, json_path)
    return {
        "schema_version": "nmrcp_console_tester_report_v1",
        "status": report["status"],
        "report": str(report_path),
        "json_report": str(json_path),
        "summary": report["summary"],
        "missing_artifacts": report["missing_artifacts"],
    }


def api_environment_access(payload: dict[str, Any]) -> dict[str, Any]:
    result = evaluate_environment_access(
        str(payload.get("environment") or "dev"),
        str(payload.get("target") or "pc"),
        str(payload.get("mode") or "read"),
        payload.get("gates") if isinstance(payload.get("gates"), dict) else {},
    )
    return result.to_dict()


def endpoint_config_from_payload(value: Any) -> EndpointConfig | None:
    if not isinstance(value, dict):
        return None
    endpoint = str(value.get("endpoint") or value.get("base_url") or "").strip()
    username = str(value.get("username") or "").strip()
    password = str(value.get("password") or value.get("credential") or "")
    if not endpoint and not username and not password:
        return None
    if not endpoint or not username or not password:
        raise ValueError("Endpoint, username, and password are required for configured connection tests")
    return EndpointConfig(
        endpoint,
        username,
        password,
        verify_tls=bool(value.get("verify_tls", True)),
        timeout_seconds=int(value.get("timeout_seconds") or 20),
    )


def required_endpoint_config(value: Any, label: str) -> EndpointConfig:
    config = endpoint_config_from_payload(value)
    if config is None:
        raise ValueError(f"{label} connection details are required")
    return config


def safe_inventory_path(path: Path, data_dir: Path) -> Path:
    resolved = path.resolve()
    allowed_roots = (Path.cwd().resolve(), data_dir.resolve())
    if not any(resolved == root or root in resolved.parents for root in allowed_roots):
        raise ValueError("inventory_path must be inside the repository or console data directory")
    return resolved


def sanitized_error(exc: Exception) -> str:
    message = str(exc) or exc.__class__.__name__
    blocked = ("password", "secret", "token", "authorization", "basic ")
    if any(token in message.lower() for token in blocked):
        return exc.__class__.__name__
    return message


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
