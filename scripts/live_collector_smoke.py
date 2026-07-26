from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from nmrcp.cli import main


class RecordingServer:
    def __init__(self, mode: str):
        self.mode = mode
        self.requests: list[tuple[str, str, dict[str, Any] | None]] = []
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler_class())
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.server.server_address
        return f"http://{host}:{port}"

    def start(self) -> None:
        self.thread.start()

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def handler_class(self):
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 - stdlib signature.
                return

            def do_GET(self) -> None:
                owner.requests.append(("GET", self.path, None))
                if owner.mode == "vcenter" and self.path == "/api/vcenter/vm":
                    self.respond(
                        {
                            "value": [
                                {
                                    "vm": "vm-local-1",
                                    "name": "local-web-01",
                                    "cpu_count": 2,
                                    "memory_size_MiB": 4096,
                                    "power_state": "POWERED_ON",
                                    "tags": [
                                        "owner:platform",
                                        "tier:noncritical",
                                        "backup:protected",
                                        "backup_last_success_hours:2",
                                        "vendor_support:ahv,nc2",
                                        "virtio_ready:true",
                                    ],
                                }
                            ]
                        }
                    )
                    return
                if owner.mode == "vcenter" and self.path == "/api/vcenter/vm/vm-local-1":
                    self.respond(
                        {
                            "value": {
                                "guest_OS": "UBUNTU_64",
                                "identity": {
                                    "host_name": "local-web-01",
                                    "dns_name": "local-web-01.example.test",
                                    "ip_addresses": ["10.10.120.10"],
                                },
                                "disks": [{"capacity_MiB": 51200}],
                                "nics": [{"network": "Local Distributed Portgroup", "vlan": 120}],
                                "snapshot_count": 1,
                                "snapshots": [{"name": "pre-change", "create_time": "2026-07-01T20:00:00Z"}],
                                "tools": {"run_state": "RUNNING", "version_status": "guestToolsNeedUpgrade"},
                            }
                        }
                    )
                    return
                if owner.mode == "vcenter" and self.path == "/api/vcenter/network":
                    self.respond(
                        {
                            "value": [
                                {
                                    "network": "network-local-1",
                                    "name": "Local Distributed Portgroup",
                                    "type": "DISTRIBUTED_PORTGROUP",
                                    "vlan": 120,
                                }
                            ]
                        }
                    )
                    return
                self.respond({"error": "unexpected GET"}, status=404)

            def do_POST(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length).decode("utf-8") if length else ""
                payload = json.loads(body) if body else {}
                owner.requests.append(("POST", self.path, payload))
                if owner.mode == "vcenter" and self.path == "/api/session":
                    self.respond({"value": "local-session"})
                    return
                if owner.mode == "prism" and self.path == "/api/nutanix/v3/clusters/list":
                    self.respond(
                        {
                            "entities": [
                                {
                                    "metadata": {"uuid": "cluster-local-1"},
                                    "status": {
                                        "name": "local-ahv-cluster",
                                        "resources": {
                                            "num_cpu_cores": 24,
                                            "memory_capacity_mib": 196608,
                                            "storage_capacity_bytes": 2199023255552,
                                        },
                                    },
                                }
                            ],
                            "metadata": {"total_matches": 1},
                        }
                    )
                    return
                if owner.mode == "prism" and self.path == "/api/nutanix/v3/vms/list":
                    offset = int(payload.get("offset") or 0)
                    if offset == 0:
                        self.respond(
                            {
                                "entities": [
                                    {
                                        "metadata": {
                                            "uuid": "uuid-local-1",
                                            "categories": {
                                                "Owner": "platform",
                                                "Backup": "protected",
                                                "BackupLastSuccessHours": "2",
                                            },
                                        },
                                        "spec": {
                                            "name": "local-ahv-01",
                                            "resources": {
                                                "num_sockets": 1,
                                                "num_vcpus_per_socket": 2,
                                                "memory_size_mib": 4096,
                                                "disk_list": [{"disk_size_bytes": 53687091200}],
                                                "nic_list": [{"subnet_reference": {"name": "vlan-120"}}],
                                            },
                                        },
                                        "status": {
                                            "resources": {
                                                "guest_tools": {
                                                    "host_name": "local-ahv-01",
                                                    "dns_name": "local-ahv-01.example.test",
                                                    "ip_addresses": ["10.10.120.12"],
                                                }
                                            }
                                        },
                                    }
                                ],
                                "metadata": {"total_matches": 1},
                            }
                        )
                    else:
                        self.respond({"entities": [], "metadata": {"total_matches": 1}})
                    return
                self.respond({"error": "unexpected POST"}, status=404)

            def respond(self, payload: dict[str, Any], status: int = 200) -> None:
                data = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

        return Handler


def run_smoke() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    out_dir = repo_root / "outputs" / "live-collector-smoke"
    out_dir.mkdir(parents=True, exist_ok=True)
    vcenter_inventory = out_dir / "vcenter-inventory.json"
    vcenter_networks = out_dir / "vcenter-networks.json"
    prism_inventory = out_dir / "prism-inventory.json"
    prism_capacity = out_dir / "prism-capacity.json"
    collection_summary = out_dir / "collection-summary.json"
    collection_proof_report = out_dir / "collection-proof-report.md"
    live_readiness = out_dir / "live-readiness.json"
    assessment_dir = out_dir / "assessment"
    assessment_intake = repo_root / "examples" / "sample_assessment_intake.csv"

    for path in (vcenter_inventory, vcenter_networks, prism_inventory, prism_capacity, collection_summary, collection_proof_report, live_readiness):
        if path.exists():
            path.unlink()
    if assessment_dir.exists():
        for child in assessment_dir.iterdir():
            if child.is_file():
                child.unlink()
        assessment_dir.rmdir()

    vcenter = RecordingServer("vcenter")
    prism = RecordingServer("prism")
    os.environ["NMRCP_SIM_PASSWORD"] = "local-only-secret"
    os.environ["NMRCP_VCENTER_URL"] = vcenter.base_url
    os.environ["NMRCP_VCENTER_USERNAME"] = "local-user"
    os.environ["NMRCP_VCENTER_PASSWORD"] = "local-only-secret"
    os.environ["NMRCP_PRISM_URL"] = prism.base_url
    os.environ["NMRCP_PRISM_USERNAME"] = "local-user"
    os.environ["NMRCP_PRISM_PASSWORD"] = "local-only-secret"
    vcenter.start()
    prism.start()
    try:
        result = main(["live-readiness", "--require-vcenter", "--require-prism", "--out", str(live_readiness)])
        if result != 0:
            raise AssertionError(f"Command failed with {result}: live-readiness")
        vcenter.requests.clear()
        prism.requests.clear()

        commands = [
            [
                "collect-sources",
                "--vcenter-endpoint",
                vcenter.base_url,
                "--vcenter-username",
                "local-user",
                "--vcenter-password-env",
                "NMRCP_SIM_PASSWORD",
                "--vcenter-details-limit",
                "1",
                "--prism-endpoint",
                prism.base_url,
                "--prism-username",
                "local-user",
                "--prism-password-env",
                "NMRCP_SIM_PASSWORD",
                "--prism-page-size",
                "1",
                "--prism-max-pages",
                "2",
                "--prism-capacity-page-size",
                "1",
                "--assessment-intake",
                str(assessment_intake),
                "--out-dir",
                str(out_dir),
            ],
            ["validate-inventory", "--inventory", str(vcenter_inventory)],
            ["validate-inventory", "--inventory", str(prism_inventory)],
            ["assess", "--inventory", str(vcenter_inventory), "--capacity", str(prism_capacity), "--out", str(assessment_dir)],
            [
                "validate-capacity",
                "--inventory",
                str(vcenter_inventory),
                "--plan",
                str(assessment_dir / "nutanix-move-plan.csv"),
                "--capacity",
                str(prism_capacity),
                "--out",
                str(assessment_dir / "target-capacity-fit.csv"),
            ],
            [
                "validate-collection-proof-report",
                "--report",
                str(collection_proof_report),
                "--collection-summary",
                str(collection_summary),
            ],
            ["review-evidence", "--dir", str(assessment_dir)],
        ]
        for command in commands:
            result = main(command)
            if result != 0:
                raise AssertionError(f"Command failed with {result}: {' '.join(command)}")

        assert_requests(
            vcenter.requests,
            [
                ("POST", "/api/session"),
                ("GET", "/api/vcenter/vm"),
                ("GET", "/api/vcenter/vm/vm-local-1"),
                ("GET", "/api/vcenter/network"),
            ],
        )
        assert_requests(
            prism.requests,
            [
                ("POST", "/api/nutanix/v3/vms/list"),
                ("POST", "/api/nutanix/v3/clusters/list"),
            ],
        )
        validate_audit(vcenter_inventory, "vcenter-rest", details_count=1)
        validate_audit(prism_inventory, "prism-central-v3", entities_count=1)
        validate_vcenter_snapshot_age(vcenter_inventory)
        validate_vcenter_tools_status(vcenter_inventory)
        validate_vcenter_networks(vcenter_networks)
        validate_prism_capacity(prism_capacity)
        validate_collection_summary(collection_summary)
        validate_collection_proof_report(collection_proof_report)
        validate_live_readiness(live_readiness)
    finally:
        vcenter.stop()
        prism.stop()
        for key in (
            "NMRCP_SIM_PASSWORD",
            "NMRCP_VCENTER_URL",
            "NMRCP_VCENTER_USERNAME",
            "NMRCP_VCENTER_PASSWORD",
            "NMRCP_PRISM_URL",
            "NMRCP_PRISM_USERNAME",
            "NMRCP_PRISM_PASSWORD",
        ):
            os.environ.pop(key, None)

    print(f"Live collector smoke passed: {out_dir}")
    return 0


def assert_requests(actual: list[tuple[str, str, dict[str, Any] | None]], expected: list[tuple[str, str]]) -> None:
    actual_pairs = [(method, path) for method, path, _payload in actual]
    if actual_pairs != expected:
        raise AssertionError(f"Unexpected requests: expected={expected!r} actual={actual_pairs!r}")


def validate_audit(path: Path, system: str, **expected: int) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    source = payload.get("source", {})
    audit = source.get("collection_audit", {})
    if source.get("system") != system:
        raise AssertionError(f"{path}: expected system {system!r}, got {source.get('system')!r}")
    if audit.get("mutating_calls") != 0:
        raise AssertionError(f"{path}: collection audit did not record mutating_calls=0")
    serialized_audit = json.dumps(audit)
    if "local-only-secret" in serialized_audit or "127.0.0.1" in serialized_audit:
        raise AssertionError(f"{path}: collection audit leaked local endpoint or secret")
    for key, value in expected.items():
        if audit.get(key) != value:
            raise AssertionError(f"{path}: expected audit {key}={value}, got {audit.get(key)!r}")


def validate_vcenter_snapshot_age(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    workload = (payload.get("workloads") or [{}])[0]
    snapshots = workload.get("snapshots") or {}
    if snapshots.get("count") != 1:
        raise AssertionError(f"{path}: expected one simulated snapshot")
    if int(snapshots.get("oldest_days") or 0) < 7:
        raise AssertionError(f"{path}: vCenter snapshot timestamp was not converted to oldest_days")
    if snapshots.get("oldest_created_at") != "2026-07-01T20:00:00+00:00":
        raise AssertionError(f"{path}: vCenter snapshot timestamp was not preserved")


def validate_vcenter_tools_status(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    workload = (payload.get("workloads") or [{}])[0]
    tools = workload.get("tools") or {}
    if tools.get("vmware_tools") is not True:
        raise AssertionError(f"{path}: vCenter tools presence was not preserved")
    if "guestToolsNeedUpgrade" not in str(tools.get("status") or ""):
        raise AssertionError(f"{path}: vCenter tools version status was not preserved")


def validate_vcenter_networks(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "nmrcp_vcenter_network_inventory_v1":
        raise AssertionError(f"{path}: unsupported vCenter network inventory schema")
    source = payload.get("source") or {}
    if source.get("mutating_calls") != 0:
        raise AssertionError(f"{path}: vCenter network inventory did not record mutating_calls=0")
    networks = payload.get("networks") or []
    if len(networks) != 1 or networks[0].get("name") != "Local Distributed Portgroup":
        raise AssertionError(f"{path}: vCenter network inventory did not preserve network names")


def validate_prism_capacity(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    source = payload.get("source", {})
    target = (payload.get("targets") or [{}])[0]
    if source.get("mutating_calls") != 0:
        raise AssertionError(f"{path}: Prism capacity source did not record mutating_calls=0")
    if target.get("usable_cpu_cores") != 24:
        raise AssertionError(f"{path}: Prism capacity did not preserve CPU cores")
    if target.get("usable_memory_gib") != 192:
        raise AssertionError(f"{path}: Prism capacity did not convert memory MiB to GiB")
    if target.get("usable_storage_gib") != 2048:
        raise AssertionError(f"{path}: Prism capacity did not convert storage bytes to GiB")


def validate_collection_summary(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "nmrcp_collection_summary_v1":
        raise AssertionError(f"{path}: unsupported collection summary schema")
    serialized = json.dumps(payload)
    if "local-only-secret" in serialized or "127.0.0.1" in serialized:
        raise AssertionError(f"{path}: collection summary leaked local endpoint or secret")
    checks = payload.get("checks") or []
    if len(checks) != 4:
        raise AssertionError(f"{path}: expected four source collection checks")
    if any(check.get("mutating_calls") != 0 for check in checks):
        raise AssertionError(f"{path}: expected mutating_calls=0 for every collection check")
    intake = (payload.get("governance") or {}).get("assessment_intake") or {}
    if intake.get("status") != "pass" or not intake.get("source_sha256"):
        raise AssertionError(f"{path}: assessment intake proof was not bound to collection summary")
    if intake.get("values_serialized") is not False:
        raise AssertionError(f"{path}: assessment intake values should not be serialized")


def validate_collection_proof_report(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for expected in (
        "nmrcp_collection_proof_report_v1",
        "nmrcp_collection_summary_v1",
        "mutating_calls=0",
        "credentials_serialized=false",
        "endpoint_values_serialized=false",
        "collection-proof-manifest.json",
        "validate-live-proof",
    ):
        if expected not in text:
            raise AssertionError(f"{path}: missing collection proof report text {expected!r}")
    for forbidden in ("local-only-secret", "127.0.0.1", "local-user"):
        if forbidden in text:
            raise AssertionError(f"{path}: collection proof report leaked {forbidden!r}")


def validate_live_readiness(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "nmrcp_live_readiness_v1":
        raise AssertionError(f"{path}: unsupported live readiness schema")
    if payload.get("status") != "pass":
        raise AssertionError(f"{path}: expected live readiness pass")
    serialized = json.dumps(payload)
    if "local-only-secret" in serialized or "127.0.0.1" in serialized or "local-user" in serialized:
        raise AssertionError(f"{path}: live readiness leaked local endpoint, username, or secret")
    checks = payload.get("checks") or []
    if {check.get("name") for check in checks} != {"vcenter", "prism-central"}:
        raise AssertionError(f"{path}: expected vCenter and Prism Central live readiness checks")


if __name__ == "__main__":
    raise SystemExit(run_smoke())
