import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.collection_proof_report import validate_collection_proof_report, write_collection_proof_report
from nmrcp.collection_workflow import collect_sources
from nmrcp.connectors import EndpointConfig
from tests.test_collection_workflow import FakePrismClient, FakeVCenterClient, write_completed_intake


class CollectionProofReportTests(unittest.TestCase):
    def test_collect_sources_writes_valid_redacted_proof_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "sources"
            intake = write_completed_intake(root / "assessment-intake.csv")

            with patch("nmrcp.collection_workflow.VCenterClient", FakeVCenterClient), patch(
                "nmrcp.collection_workflow.PrismCentralClient", FakePrismClient
            ):
                collect_sources(
                    EndpointConfig("https://vcenter.private.example", "vc-user", "vc-secret"),
                    EndpointConfig("https://prism.private.example:9440", "pc-user", "pc-secret"),
                    out_dir,
                    assessment_intake_path=intake,
                )

            report = out_dir / "collection-proof-report.md"
            summary = out_dir / "collection-summary.json"
            result = validate_collection_proof_report(report, collection_summary_path=summary)
            text = report.read_text(encoding="utf-8")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("nmrcp_collection_proof_report_v1", text)
            self.assertIn("collection-proof-manifest.json", text)
            self.assertIn("validate-live-proof", text)
            self.assertNotIn("vcenter.private.example", text)
            self.assertNotIn("vc-secret", text)

    def test_validator_rejects_summary_without_read_only_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = write_summary(root)
            report = root / "collection-proof-report.md"
            write_collection_proof_report(summary, report)

            payload = json.loads(summary.read_text(encoding="utf-8"))
            payload["checks"][0]["mutating_calls"] = 1
            summary.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = validate_collection_proof_report(report, collection_summary_path=summary)

            self.assertFalse(result.ok)
            self.assertTrue(any("mutating_calls=0" in error for error in result.errors))

    def test_cli_generates_and_validates_collection_proof_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = write_summary(root)
            report = root / "collection-proof-report.md"

            with patch("sys.stdout"):
                generate_code = main(["collection-proof-report", "--collection-summary", str(summary), "--out", str(report)])
                validate_code = main(
                    [
                        "validate-collection-proof-report",
                        "--report",
                        str(report),
                        "--collection-summary",
                        str(summary),
                    ]
                )

            self.assertEqual(generate_code, 0)
            self.assertEqual(validate_code, 0)
            self.assertTrue(report.exists())


def write_summary(root: Path) -> Path:
    path = root / "collection-summary.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_collection_summary_v1",
                "generated_at": "2026-07-26T12:00:00+00:00",
                "status": "pass",
                "artifacts": {
                    "vcenter_inventory": "vcenter-inventory.json",
                    "vcenter_networks": "vcenter-networks.json",
                    "prism_inventory": "prism-inventory.json",
                    "prism_capacity": "prism-capacity.json",
                    "collection_summary": "collection-summary.json",
                    "collection_proof_manifest": "collection-proof-manifest.json",
                    "collection_proof_report": "collection-proof-report.md",
                },
                "checks": [
                    {
                        "name": "vcenter-read-only-collection",
                        "status": "pass",
                        "workloads": 2,
                        "api_paths": ["/api/session", "/api/vcenter/vm", "/api/vcenter/vm/{vm}", "/api/vcenter/network"],
                        "mutating_calls": 0,
                        "tls_verification": "enabled",
                    },
                    {
                        "name": "prism-read-only-collection",
                        "status": "pass",
                        "workloads": 1,
                        "api_paths": ["/api/nutanix/v3/vms/list"],
                        "mutating_calls": 0,
                        "tls_verification": "enabled",
                    },
                ],
                "privacy": {
                    "credentials_serialized": False,
                    "endpoint_values_serialized": False,
                    "summary_redacted": True,
                    "tls_verification": {"vcenter": "enabled", "prism-central": "enabled"},
                },
                "governance": {
                    "assessment_intake": {
                        "status": "pass",
                        "schema_version": "nmrcp_assessment_intake_validation_v1",
                        "source_sha256": "a" * 64,
                        "rows": 12,
                        "warnings": [],
                        "values_serialized": False,
                    }
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
