import json
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.live_proof import validate_live_proof


class LiveProofTests(unittest.TestCase):
    def test_validate_live_proof_accepts_read_only_redacted_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live, summary = write_valid_proof(root)

            result = validate_live_proof(live, collection_summary_path=summary, source_dir=root)

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.status, "pass")
            self.assertTrue(any(check["name"] == "live-readiness-tls-verification" for check in result.checks))
            self.assertTrue(any(check["name"] == "collection-summary-tls-verification" for check in result.checks))
            self.assertTrue(any(check["name"] == "vcenter_inventory-audit" for check in result.checks))
            self.assertTrue(any(check["name"] == "collection-proof-manifest-artifacts" for check in result.checks))

    def test_validate_live_proof_rejects_failed_live_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live, summary = write_valid_proof(root)
            payload = json.loads(live.read_text(encoding="utf-8"))
            payload["status"] = "fail"
            payload["checks"][0]["status"] = "fail"
            live.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = validate_live_proof(live, collection_summary_path=summary, source_dir=root)

            self.assertFalse(result.ok)
            self.assertTrue(any("live readiness status must be pass" in error for error in result.errors))

    def test_validate_live_proof_rejects_mutating_collection_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live, summary = write_valid_proof(root)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            payload["checks"][0]["mutating_calls"] = 1
            summary.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = validate_live_proof(live, collection_summary_path=summary, source_dir=root)

            self.assertFalse(result.ok)
            self.assertTrue(any("mutating_calls=0" in error for error in result.errors))

    def test_validate_live_proof_rejects_missing_assessment_intake_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live, summary = write_valid_proof(root)
            payload = json.loads(summary.read_text(encoding="utf-8"))
            payload.pop("governance")
            summary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            write_collection_proof_manifest(root)

            result = validate_live_proof(live, collection_summary_path=summary, source_dir=root)

            self.assertFalse(result.ok)
            self.assertTrue(any("collection-summary-assessment-intake" in error for error in result.errors))

    def test_validate_live_proof_rejects_manifest_assessment_intake_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live, summary = write_valid_proof(root)
            manifest = root / "collection-proof-manifest.json"
            payload = json.loads(manifest.read_text(encoding="utf-8"))
            payload["security"]["assessment_intake"]["source_sha256"] = "0" * 64
            manifest.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = validate_live_proof(live, collection_summary_path=summary, source_dir=root)

            self.assertFalse(result.ok)
            self.assertTrue(any("assessment intake proof must match" in error for error in result.errors))

    def test_validate_live_proof_rejects_missing_tls_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live, summary = write_valid_proof(root)
            payload = json.loads(live.read_text(encoding="utf-8"))
            payload["security"].pop("tls_verification")
            live.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = validate_live_proof(live, collection_summary_path=summary, source_dir=root)

        self.assertFalse(result.ok)
        self.assertTrue(any("TLS verification state" in error for error in result.errors))

    def test_validate_live_proof_warns_on_disabled_tls_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live, summary = write_valid_proof(root, tls_state="disabled")

            result = validate_live_proof(live, collection_summary_path=summary, source_dir=root)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.status, "warn")
        self.assertTrue(any("TLS certificate verification was disabled" in warning for warning in result.warnings))

    def test_validate_live_proof_rejects_secret_like_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live, summary = write_valid_proof(root)
            payload = json.loads(live.read_text(encoding="utf-8"))
            payload["debug"] = "password=not-for-proof"
            live.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = validate_live_proof(live, collection_summary_path=summary, source_dir=root)

            self.assertFalse(result.ok)
            self.assertTrue(any("potential secret-assignment leak" in error for error in result.errors))

    def test_validate_live_proof_rejects_tampered_manifested_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live, summary = write_valid_proof(root)
            (root / "vcenter-inventory.json").write_text(
                json.dumps(vcenter_inventory_payload() | {"tampered": True}, indent=2),
                encoding="utf-8",
            )

            result = validate_live_proof(live, collection_summary_path=summary, source_dir=root)

            self.assertFalse(result.ok)
            self.assertTrue(any("collection proof artifact checksum mismatch: vcenter-inventory.json" in error for error in result.errors))

    def test_cli_validate_live_proof_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            live, summary = write_valid_proof(root)
            out = root / "live-proof-validation.json"

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-live-proof",
                        "--live-readiness",
                        str(live),
                        "--collection-summary",
                        str(summary),
                        "--source-dir",
                        str(root),
                        "--out",
                        str(out),
                        "--json",
                    ]
                )

            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(payload["schema_version"], "nmrcp_live_endpoint_proof_v1")
            self.assertEqual(payload["status"], "pass")


def write_valid_proof(root: Path, tls_state: str = "enabled") -> tuple[Path, Path]:
    live = root / "live-readiness.json"
    summary = root / "collection-summary.json"
    vcenter_inventory = root / "vcenter-inventory.json"
    vcenter_networks = root / "vcenter-networks.json"
    prism_inventory = root / "prism-inventory.json"
    live.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_live_readiness_v1",
                "generated_at": "2026-07-24T12:00:00+00:00",
                "status": "pass",
                "checks": [
                    {
                        "name": "vcenter",
                        "status": "pass",
                        "configured": True,
                        "authenticated": True,
                        "tls_verification": tls_state,
                        "read_only_calls": ["/api/session", "/api/vcenter/vm"],
                        "counts": {"vms": 2},
                    },
                    {
                        "name": "prism-central",
                        "status": "pass",
                        "configured": True,
                        "authenticated": True,
                        "tls_verification": tls_state,
                        "read_only_calls": ["/api/nutanix/v3/clusters/list", "/api/nutanix/v3/vms/list"],
                        "counts": {"clusters": 1, "vms": 1},
                    },
                ],
                "security": {
                    "mode": "read-only",
                    "credentials_serialized": False,
                    "endpoint_values_serialized": False,
                    "mutation_allowed": False,
                    "tls_verification": {
                        "vcenter": tls_state,
                        "prism-central": tls_state,
                    },
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    summary.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_collection_summary_v1",
                "generated_at": "2026-07-24T12:00:00+00:00",
                "status": "pass",
                "artifacts": {
                    "vcenter_inventory": "vcenter-inventory.json",
                    "vcenter_networks": "vcenter-networks.json",
                    "prism_inventory": "prism-inventory.json",
                    "prism_capacity": "prism-capacity.json",
                    "collection_summary": "collection-summary.json",
                    "collection_proof_manifest": "collection-proof-manifest.json",
                },
                "checks": [
                    {
                        "name": "vcenter-read-only-collection",
                        "status": "pass",
                        "workloads": 2,
                        "api_paths": ["/api/session", "/api/vcenter/vm", "/api/vcenter/vm/{vm}", "/api/vcenter/network"],
                        "mutating_calls": 0,
                        "tls_verification": tls_state,
                    },
                    {
                        "name": "vcenter-network-read-only-collection",
                        "status": "pass",
                        "networks": 2,
                        "api_paths": ["/api/session", "/api/vcenter/network"],
                        "mutating_calls": 0,
                        "tls_verification": tls_state,
                    },
                    {
                        "name": "prism-read-only-collection",
                        "status": "pass",
                        "workloads": 1,
                        "api_paths": ["/api/nutanix/v3/vms/list"],
                        "mutating_calls": 0,
                        "tls_verification": tls_state,
                    },
                    {
                        "name": "prism-capacity-read-only-collection",
                        "status": "pass",
                        "targets": 1,
                        "api_paths": ["/api/nutanix/v3/clusters/list"],
                        "mutating_calls": 0,
                        "tls_verification": tls_state,
                    },
                ],
                "privacy": {
                    "credentials_serialized": False,
                    "endpoint_values_serialized": False,
                    "summary_redacted": True,
                    "tls_verification": {
                        "vcenter": tls_state,
                        "prism-central": tls_state,
                    },
                },
                "governance": {
                    "assessment_intake": assessment_intake_proof(),
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    vcenter_inventory.write_text(json.dumps(vcenter_inventory_payload(), indent=2), encoding="utf-8")
    vcenter_networks.write_text(json.dumps({"networks": [{"network": "network-1"}]}, indent=2), encoding="utf-8")
    prism_inventory.write_text(json.dumps(prism_inventory_payload(), indent=2), encoding="utf-8")
    (root / "prism-capacity.json").write_text(json.dumps({"targets": [{}]}, indent=2), encoding="utf-8")
    write_collection_proof_manifest(root)
    return live, summary


def write_collection_proof_manifest(root: Path) -> None:
    artifact_names = [
        "collection-summary.json",
        "prism-capacity.json",
        "prism-inventory.json",
        "vcenter-inventory.json",
        "vcenter-networks.json",
    ]
    (root / "collection-proof-manifest.json").write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_collection_proof_manifest_v1",
                "generated_at": "2026-07-24T12:00:00+00:00",
                "security": {
                    "mode": "read-only",
                    "credentials_serialized": False,
                    "endpoint_values_serialized": False,
                    "mutation_allowed": False,
                    "manifest_self_name": "collection-proof-manifest.json",
                    "read_only_api_allowlist": [
                        "/api/nutanix/v3/clusters/list",
                        "/api/nutanix/v3/vms/list",
                        "/api/session",
                        "/api/vcenter/network",
                        "/api/vcenter/vm",
                        "/api/vcenter/vm/{vm}",
                    ],
                    "assessment_intake": assessment_intake_proof(),
                },
                "artifacts": [
                    {
                        "name": name,
                        "size_bytes": (root / name).stat().st_size,
                        "sha256": sha256_file(root / name),
                        "contains_workload_data": name
                        in {"vcenter-inventory.json", "vcenter-networks.json", "prism-inventory.json", "prism-capacity.json"},
                    }
                    for name in artifact_names
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def assessment_intake_proof() -> dict:
    return {
        "status": "pass",
        "schema_version": "nmrcp_assessment_intake_validation_v1",
        "source_sha256": "a" * 64,
        "rows": 3,
        "warnings": [],
        "values_serialized": False,
    }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def vcenter_inventory_payload() -> dict:
    return {
        "source": {
            "system": "vcenter-rest",
            "endpoint": "https://redacted.local",
            "collection_audit": {
                "schema": "nmrcp_collection_audit_v1",
                "mode": "read-only",
                "endpoint_configured": True,
                "credential_storage": "not_persisted",
                "api_paths": ["/api/session", "/api/vcenter/vm", "/api/vcenter/vm/{vm}", "/api/vcenter/network"],
                "mutating_calls": 0,
                "summary_count": 2,
                "details_limit": 2,
                "details_count": 2,
                "network_count": 2,
            },
        },
        "workloads": [{"id": "vm-1"}, {"id": "vm-2"}],
    }


def prism_inventory_payload() -> dict:
    return {
        "source": {
            "system": "prism-central-v3",
            "endpoint": "https://redacted.local:9440",
            "collection_audit": {
                "schema": "nmrcp_collection_audit_v1",
                "mode": "read-only",
                "endpoint_configured": True,
                "credential_storage": "not_persisted",
                "api_paths": ["/api/nutanix/v3/vms/list"],
                "post_paths_allowlisted": True,
                "mutating_calls": 0,
                "entities_count": 1,
                "page_size": 100,
                "max_pages": 1,
            },
        },
        "workloads": [{"id": "vm-1"}],
    }


if __name__ == "__main__":
    unittest.main()
