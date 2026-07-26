import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from nmrcp.workflow import run_assessment_workflow


class AssessmentWorkflowTests(unittest.TestCase):
    def test_run_assessment_workflow_creates_operator_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = tmp_path / "assessment"
            capture_kit = write_capture_kit(tmp_path)
            capture_validation = write_capture_validation(tmp_path, status="pass")

            result = run_assessment_workflow(
                Path("examples/sample_inventory.json"),
                out_dir,
                metadata_path=Path("examples/sample_metadata.csv"),
                dependencies_path=Path("examples/sample_dependencies.csv"),
                capacity_path=Path("examples/sample_target_capacity.json"),
                prism_inventory_path=Path("examples/sample_prism_inventory.json"),
                source_networks_path=write_vcenter_network_inventory(tmp_path, ["120"]),
                move_config_path=Path("examples/sample_move_payload_config.json"),
                validation_results_path=Path("examples/sample_validation_results.csv"),
                remediation_tracker_path=Path("examples/sample_remediation_tracker_closed.csv"),
                signoffs_path=Path("examples/sample_owner_signoffs_approved.csv"),
                approval_exceptions_path=Path("examples/sample_approval_exceptions_approved.csv"),
                move_lab_capture_kit_dir=capture_kit,
                move_lab_capture_validation_path=capture_validation,
            )

            self.assertEqual(result["status"], "pass", result)
            self.assertTrue((out_dir / "assessment.json").exists())
            self.assertTrue((out_dir / "target-capacity-fit.csv").exists())
            self.assertTrue((out_dir / "target-reconciliation.csv").exists())
            self.assertTrue((out_dir / "source-network-validation.csv").exists())
            self.assertTrue((out_dir / "target-network-mapping.csv").exists())
            self.assertTrue((out_dir / "validation-results.template.csv").exists())
            self.assertTrue((out_dir / "move-api-payload.dry-run.json").exists())
            self.assertTrue((out_dir / "operator-gate-summary.md").exists())
            self.assertTrue((tmp_path / "assessment-evidence-bundle.zip").exists())
            handoff = tmp_path / "assessment-handoff-package.zip"
            self.assertTrue(handoff.exists())
            with zipfile.ZipFile(handoff, "r") as archive:
                names = set(archive.namelist())
            self.assertIn("assessment/assessment.json", names)
            self.assertIn("signoffs/final-owner-signoffs.csv", names)
            self.assertIn("signoffs/final-approval-exceptions.csv", names)
            self.assertIn("remediation/final-remediation-tracker.csv", names)
            self.assertIn("move/move-api-payload.dry-run.json", names)
            self.assertIn("assessment/target-capacity-fit.csv", names)
            self.assertIn("assessment/target-reconciliation.csv", names)
            self.assertIn("assessment/source-network-validation.csv", names)
            self.assertIn("assessment/target-network-mapping.csv", names)
            self.assertIn("assessment/operator-gate-summary.md", names)
            self.assertIn("move/move-lab-transcript.template.json", names)
            self.assertIn("move/move-lab-capture-checklist.md", names)
            self.assertIn("move/move-lab-capture-kit-validation.json", names)
            summary = (out_dir / "operator-gate-summary.md").read_text(encoding="utf-8")
            self.assertIn("| Move lab capture kit | pass |", summary)
            self.assertIn("| Approval exception closure | pass |", summary)

    def test_run_assessment_workflow_fails_before_artifacts_on_invalid_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            inventory = tmp_path / "invalid.json"
            out_dir = tmp_path / "assessment"
            inventory.write_text(json.dumps({"source": {"system": "test"}}), encoding="utf-8")

            result = run_assessment_workflow(inventory, out_dir)

            self.assertEqual(result["status"], "fail")
            self.assertFalse(out_dir.exists())
            self.assertEqual(result["checks"][0]["name"], "inventory-validation")

    def test_run_assessment_workflow_can_gate_capture_validation_without_archiving_kit(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = tmp_path / "assessment"

            result = run_assessment_workflow(
                Path("examples/sample_inventory.json"),
                out_dir,
                metadata_path=Path("examples/sample_metadata.csv"),
                move_lab_capture_validation_path=write_capture_validation(tmp_path, status="pass"),
            )

            self.assertEqual(result["status"], "pass", result)
            summary = (out_dir / "operator-gate-summary.md").read_text(encoding="utf-8")
            self.assertIn("| Move lab capture kit | pass |", summary)
            with zipfile.ZipFile(tmp_path / "assessment-handoff-package.zip", "r") as archive:
                names = set(archive.namelist())
            self.assertNotIn("move/move-lab-capture-kit-validation.json", names)


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


def write_capture_kit(root: Path) -> Path:
    kit = root / "capture-kit"
    kit.mkdir(parents=True, exist_ok=True)
    (kit / "move-lab-transcript.template.json").write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_transcript_v1",
                "evidence_state": "template_only_replace_after_lab_capture",
                "production_targets": False,
                "mutation_performed": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (kit / "move-lab-capture-checklist.md").write_text("# Move Lab Capture Checklist\n", encoding="utf-8")
    return kit


def write_capture_validation(root: Path, status: str) -> Path:
    path = root / "move-lab-capture-kit-validation.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_capture_kit_validation_v1",
                "status": status,
                "checks": [],
                "errors": [] if status == "pass" else ["capture kit failed"],
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
