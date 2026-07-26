import tempfile
import unittest
import csv
from pathlib import Path
from unittest.mock import patch
import io
import json
from contextlib import redirect_stdout

from nmrcp.cli import main
from nmrcp.approval_exceptions import read_rows


class CliTests(unittest.TestCase):
    def test_assess_command_exports_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            code = main(["assess", "--inventory", "examples/sample_inventory.json", "--out", str(out_dir)])

            self.assertEqual(code, 0)
            self.assertTrue((out_dir / "assessment.json").exists())
            self.assertTrue((out_dir / "pre-post-validation-checklist.md").exists())

    def test_assess_command_accepts_readiness_policy(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            code = main(
                [
                    "assess",
                    "--inventory",
                    "examples/sample_inventory.json",
                    "--policy",
                    "examples/sample_readiness_policy.json",
                    "--out",
                    str(out_dir),
                ]
            )

            self.assertEqual(code, 0)
            assessment = (out_dir / "assessment.json").read_text(encoding="utf-8")
            self.assertIn('"snapshot_max_age_days": 7', assessment)

    def test_assess_command_can_write_capacity_fit_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            code = main(
                [
                    "assess",
                    "--inventory",
                    "examples/sample_inventory.json",
                    "--capacity",
                    "examples/sample_target_capacity.json",
                    "--out",
                    str(out_dir),
                ]
            )

            self.assertEqual(code, 0)
            self.assertTrue((out_dir / "target-capacity-fit.csv").exists())
            manifest = (out_dir / "evidence-manifest.json").read_text(encoding="utf-8")
            self.assertIn("target-capacity-fit.csv", manifest)

    def test_collect_prism_command_uses_env_password_and_writes_inventory(self):
        class FakePrism:
            def __init__(self, config):
                self.config = config

            def list_vms(self, page_size=500, max_pages=20):
                return [
                    {
                        "metadata": {"uuid": "uuid-1", "categories": {}},
                        "spec": {"name": "vm", "resources": {"memory_size_mib": 1024}},
                    }
                ]

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "prism.json"
            with patch("nmrcp.cli.PrismCentralClient", FakePrism), patch.dict(
                "os.environ",
                {"NMRCP_PRISM_PASSWORD": "synthetic-password"},
            ):
                code = main(
                    [
                        "collect-prism",
                        "--endpoint",
                        "https://pc.example.test:9440",
                        "--username",
                        "admin",
                        "--out",
                        str(out_path),
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            audit = payload["source"]["collection_audit"]
            self.assertEqual(audit["page_size"], 500)
            self.assertEqual(audit["max_pages"], 20)
            self.assertEqual(audit["entities_count"], 1)

    def test_collect_vcenter_command_writes_inventory(self):
        class FakeVCenter:
            def __init__(self, config):
                self.config = config

            def list_vms(self):
                return [{"vm": "vm-1", "name": "web", "cpu_count": 2, "memory_size_MiB": 4096}]

            def get_vm_details(self, vm_id):
                return {"guest_OS": "UBUNTU_64", "disks": [{"capacity_MiB": 51200}]}

            def list_networks(self):
                return [{"network": "network-1", "name": "VM Network"}]

        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "vcenter.json"
            with patch("nmrcp.cli.VCenterClient", FakeVCenter), patch.dict(
                "os.environ",
                {"NMRCP_VCENTER_PASSWORD": "synthetic-password"},
            ):
                code = main(
                    [
                        "collect-vcenter",
                        "--endpoint",
                        "https://vcsa.example.test",
                        "--username",
                        "administrator@example.test",
                        "--out",
                        str(out_path),
                    ]
                )

            self.assertEqual(code, 0)
            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["workloads"][0]["name"], "web")
            audit = payload["source"]["collection_audit"]
            self.assertEqual(audit["details_limit"], 250)
            self.assertEqual(audit["details_count"], 1)
            self.assertEqual(audit["network_count"], 1)
            self.assertIn("/api/vcenter/network", audit["api_paths"])

    def test_collect_sources_command_writes_summary(self):
        fake_summary = {
            "schema_version": "nmrcp_collection_summary_v1",
            "status": "pass",
            "checks": [
                {"name": "vcenter-read-only-collection", "status": "pass", "workloads": 1, "mutating_calls": 0},
                {"name": "vcenter-network-read-only-collection", "status": "pass", "networks": 1, "mutating_calls": 0},
                {"name": "prism-read-only-collection", "status": "pass", "workloads": 1, "mutating_calls": 0},
                {"name": "prism-capacity-read-only-collection", "status": "pass", "targets": 1, "mutating_calls": 0},
            ],
        }

        with tempfile.TemporaryDirectory() as tmp, patch("nmrcp.cli.collect_sources", return_value=fake_summary) as collector, patch.dict(
            "os.environ",
            {
                "NMRCP_TEST_VCENTER_PASSWORD": "synthetic-vcenter-password",
                "NMRCP_TEST_PRISM_PASSWORD": "synthetic-prism-password",
            },
        ), redirect_stdout(io.StringIO()):
            intake = Path(tmp) / "assessment-intake.csv"
            result = main(
                [
                    "collect-sources",
                    "--vcenter-endpoint",
                    "https://vcenter.example.test",
                    "--vcenter-username",
                    "administrator",
                    "--vcenter-password-env",
                    "NMRCP_TEST_VCENTER_PASSWORD",
                    "--prism-endpoint",
                    "https://prism.example.test:9440",
                    "--prism-username",
                    "admin",
                    "--prism-password-env",
                    "NMRCP_TEST_PRISM_PASSWORD",
                    "--assessment-intake",
                    str(intake),
                    "--out-dir",
                    tmp,
                ]
            )

        self.assertEqual(result, 0)
        self.assertEqual(collector.call_count, 1)
        self.assertEqual(collector.call_args.kwargs["assessment_intake_path"], intake)

    def test_probe_vcenter_redacts_connection_values(self):
        class FakeVCenter:
            def __init__(self, config):
                self.config = config

            def login(self):
                return "session-id"

            def list_vms(self):
                return [{"vm": "vm-1"}]

        stream = io.StringIO()
        with patch("nmrcp.cli.VCenterClient", FakeVCenter), patch.dict(
            "os.environ",
            {"NMRCP_VCENTER_PASSWORD": "synthetic-password"},
        ), redirect_stdout(stream):
            code = main(
                [
                    "probe-vcenter",
                    "--endpoint",
                    "https://vcsa.example.test",
                    "--username",
                    "administrator@example.test",
                ]
            )

        output = stream.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("vm_count=1", output)
        self.assertNotIn("synthetic-password", output)
        self.assertNotIn("administrator@example.test", output)
        self.assertNotIn("vcsa.example.test", output)

    def test_probe_prism_redacts_connection_values(self):
        class FakePrism:
            def __init__(self, config):
                self.config = config

            def list_clusters(self):
                return [{"metadata": {"uuid": "cluster-1"}}]

            def list_vms(self, page_size=500, max_pages=20):
                return [{"metadata": {"uuid": "vm-1"}}]

        stream = io.StringIO()
        with patch("nmrcp.cli.PrismCentralClient", FakePrism), patch.dict(
            "os.environ",
            {"NMRCP_PRISM_PASSWORD": "synthetic-password"},
        ), redirect_stdout(stream):
            code = main(
                [
                    "probe-prism",
                    "--endpoint",
                    "https://pc.example.test:9440",
                    "--username",
                    "admin",
                ]
            )

        output = stream.getvalue()
        self.assertEqual(code, 0)
        self.assertIn("cluster_count=1", output)
        self.assertIn("sample_vm_count=1", output)
        self.assertNotIn("synthetic-password", output)
        self.assertNotIn("pc.example.test", output)
        self.assertNotIn("admin", output)

    def test_assess_command_can_merge_dependency_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            code = main(
                [
                    "assess",
                    "--inventory",
                    "examples/sample_inventory.json",
                    "--metadata",
                    "examples/sample_metadata.csv",
                    "--dependencies",
                    "examples/sample_dependencies.csv",
                    "--out",
                    str(out_dir),
                ]
            )

            self.assertEqual(code, 0)
            evidence = (out_dir / "change-board-evidence.md").read_text(encoding="utf-8")
            self.assertIn("Unmatched dependency records: 1", evidence)
            move_plan = (out_dir / "nutanix-move-plan.csv").read_text(encoding="utf-8")
            self.assertIn("dependency_count", move_plan)

    def test_validate_move_plan_command_passes_generated_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            main(["assess", "--inventory", "examples/sample_inventory.json", "--out", str(out_dir)])

            code = main(["validate-move-plan", "--plan", str(out_dir / "nutanix-move-plan.csv")])

            self.assertEqual(code, 0)

    def test_validate_move_plan_command_accepts_assessment_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            main(["assess", "--inventory", "examples/sample_inventory.json", "--out", str(out_dir)])

            code = main(
                [
                    "validate-move-plan",
                    "--plan",
                    str(out_dir / "nutanix-move-plan.csv"),
                    "--assessment",
                    str(out_dir / "assessment.json"),
                ]
            )

            self.assertEqual(code, 0)

    def test_run_assessment_command_creates_full_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            code = main(
                [
                    "run-assessment",
                    "--inventory",
                    "examples/sample_inventory.json",
                    "--metadata",
                    "examples/sample_metadata.csv",
                    "--dependencies",
                    "examples/sample_dependencies.csv",
                    "--prism-inventory",
                    "examples/sample_prism_inventory.json",
                    "--source-networks",
                    str(write_vcenter_network_inventory(Path(tmp), ["120"])),
                    "--move-config",
                    "examples/sample_move_payload_config.json",
                    "--validation-results",
                    "examples/sample_validation_results.csv",
                    "--remediation-tracker",
                    "examples/sample_remediation_tracker_closed.csv",
                    "--signoffs",
                    "examples/sample_owner_signoffs_approved.csv",
                    "--approval-exceptions",
                    "examples/sample_approval_exceptions_approved.csv",
                    "--out",
                    str(out_dir),
                ]
            )

            self.assertEqual(code, 0)
            self.assertTrue((out_dir / "assessment.json").exists())
            self.assertTrue((out_dir / "target-reconciliation.csv").exists())
            self.assertTrue((out_dir / "source-network-validation.csv").exists())
            self.assertTrue((Path(tmp) / "assessment-handoff-package.zip").exists())

    def test_generate_move_payload_command_writes_dry_run_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            payload_path = Path(tmp) / "payload.json"
            main(["assess", "--inventory", "examples/sample_inventory.json", "--out", str(out_dir)])

            code = main(
                [
                    "generate-move-payload",
                    "--plan",
                    str(out_dir / "nutanix-move-plan.csv"),
                    "--config",
                    "examples/sample_move_payload_config.json",
                    "--out",
                    str(payload_path),
                ]
            )

            payload = payload_path.read_text(encoding="utf-8")
            self.assertEqual(code, 0)
            self.assertIn("dry_run_only", payload)
            self.assertIn("network_mapping", payload)

    def test_validate_move_submit_readiness_command_requires_lab_ack(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            payload_path = Path(tmp) / "payload.json"
            proof_path = Path(tmp) / "move-submit-readiness.json"
            main(
                [
                    "assess",
                    "--inventory",
                    "examples/sample_inventory.json",
                    "--metadata",
                    "examples/sample_metadata.csv",
                    "--out",
                    str(out_dir),
                ]
            )
            main(
                [
                    "generate-move-payload",
                    "--plan",
                    str(out_dir / "nutanix-move-plan.csv"),
                    "--config",
                    "examples/sample_move_payload_lab_config.json",
                    "--out",
                    str(payload_path),
                ]
            )

            with patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}), redirect_stdout(io.StringIO()):
                code = main(
                    [
                        "validate-move-submit-readiness",
                        "--payload",
                        str(payload_path),
                        "--review",
                        "examples/sample_move_submit_review.json",
                        "--out",
                        str(proof_path),
                    ]
                )

            self.assertEqual(code, 0)
            proof = json.loads(proof_path.read_text(encoding="utf-8"))
            self.assertEqual(proof["status"], "pass")

    def test_package_and_verify_evidence_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            bundle = Path(tmp) / "bundle.zip"
            main(["assess", "--inventory", "examples/sample_inventory.json", "--out", str(out_dir)])

            verify_dir_code = main(["verify-evidence", "--dir", str(out_dir)])
            review_code = main(["review-evidence", "--dir", str(out_dir)])
            package_code = main(["package-evidence", "--dir", str(out_dir), "--out", str(bundle)])
            verify_bundle_code = main(["verify-evidence", "--bundle", str(bundle)])

            self.assertEqual(verify_dir_code, 0)
            self.assertEqual(review_code, 0)
            self.assertEqual(package_code, 0)
            self.assertEqual(verify_bundle_code, 0)

    def test_summarize_gates_command_writes_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            main(["assess", "--inventory", "examples/sample_inventory.json", "--out", str(out_dir)])

            code = main(["summarize-gates", "--dir", str(out_dir)])

            self.assertEqual(code, 0)
            self.assertTrue((out_dir / "operator-gate-summary.md").exists())

    def test_summarize_gates_command_accepts_approval_exceptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            main(
                [
                    "assess",
                    "--inventory",
                    "examples/sample_inventory.json",
                    "--metadata",
                    "examples/sample_metadata.csv",
                    "--dependencies",
                    "examples/sample_dependencies.csv",
                    "--out",
                    str(out_dir),
                ]
            )

            code = main(
                [
                    "summarize-gates",
                    "--dir",
                    str(out_dir),
                    "--approval-exceptions",
                    "examples/sample_approval_exceptions_approved.csv",
                ]
            )

            self.assertEqual(code, 0)
            self.assertIn("Approval exception closure", (out_dir / "operator-gate-summary.md").read_text(encoding="utf-8"))

    def test_package_and_verify_handoff_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            bundle = Path(tmp) / "bundle.zip"
            handoff = Path(tmp) / "handoff.zip"
            main(["assess", "--inventory", "examples/sample_inventory.json", "--out", str(out_dir)])
            main(["package-evidence", "--dir", str(out_dir), "--out", str(bundle)])
            approval_exceptions = approved_exceptions_copy(out_dir, Path(tmp) / "approved-approval-exceptions.csv")

            package_code = main(
                [
                    "package-handoff",
                    "--dir",
                    str(out_dir),
                    "--bundle",
                    str(bundle),
                    "--validation-results",
                    "examples/sample_validation_results.csv",
                    "--remediation-tracker",
                    "examples/sample_remediation_tracker_closed.csv",
                    "--signoffs",
                    "examples/sample_owner_signoffs_approved.csv",
                    "--approval-exceptions",
                    str(approval_exceptions),
                    "--out",
                    str(handoff),
                ]
            )
            verify_code = main(["verify-handoff", "--package", str(handoff)])

            self.assertEqual(package_code, 0)
            self.assertEqual(verify_code, 0)


def write_vcenter_network_inventory(tmp: Path, vlans: list[str]) -> Path:
    path = tmp / "vcenter-networks.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_vcenter_network_inventory_v1",
                "source": {"system": "test-vcenter", "mutating_calls": 0},
                "networks": [{"network": f"VLAN{vlan}", "name": f"VLAN{vlan}", "vlan": vlan} for vlan in vlans],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def approved_exceptions_copy(out_dir: Path, path: Path) -> Path:
    rows = read_rows(out_dir / "approval-exceptions.csv", [])
    for index, row in enumerate(rows, start=1):
        row["approval_status"] = "approved"
        row["approval_ref"] = f"CHG-2026-EXC-{index:03d}"
        row["approved_by"] = "Migration Lead"
        row["approved_at"] = "2026-07-25T00:00:00Z"
        row["notes"] = "Approved for lab change-board review."
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


if __name__ == "__main__":
    unittest.main()
