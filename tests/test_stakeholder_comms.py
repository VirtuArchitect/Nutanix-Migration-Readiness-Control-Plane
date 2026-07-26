import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.change_gate import run_change_gate
from nmrcp.cli import main
from nmrcp.dependencies import merge_dependencies, read_dependency_csv
from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.scoring import assess_inventory
from nmrcp.stakeholder_comms import read_rows, validate_stakeholder_comms
from nmrcp.waves import plan_waves


class StakeholderCommsTests(unittest.TestCase):
    def test_generated_plan_groups_owner_wave_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment = json.loads((out_dir / "assessment.json").read_text(encoding="utf-8"))

            result = validate_stakeholder_comms(
                out_dir / "stakeholder-communication-plan.csv",
                out_dir / "assessment.json",
            )
            rows = read_rows(out_dir / "stakeholder-communication-plan.csv", [])
            by_owner = {row["owner"]: row for row in rows}

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(assessment["stakeholder_comms_context"]["schema_version"], "nmrcp_stakeholder_communication_plan_v1")
            self.assertEqual(result.rows, 3)
            self.assertEqual(by_owner["Platform Team"]["communication_stage"], "ready_owner_signoff")
            self.assertIn("change_board", by_owner["Platform Team"]["audience"])
            self.assertIn("nutanix-move-plan.csv", by_owner["Platform Team"]["evidence_refs"])
            self.assertEqual(by_owner["Business Apps"]["communication_stage"], "remediation_owner_review")
            self.assertIn("risk_acceptance", by_owner["Business Apps"]["audience"])
            self.assertIn("remediation-tracker.csv", by_owner["Business Apps"]["evidence_refs"])
            self.assertEqual(by_owner["Payments"]["communication_stage"], "blocked_owner_review")

    def test_validator_rejects_tampered_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "stakeholder-communication-plan.csv"
            rows = read_rows(path, [])
            rows[0]["required_action"] = "Schedule immediately without owner response."
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_stakeholder_comms(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("required_action expected" in error for error in result.errors))

    def test_validator_rejects_stale_embedded_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["stakeholder_comms_context"]["communications"][0]["communication_stage"] = "ready_owner_signoff"
            assessment["stakeholder_comms_context"]["communications"][0]["required_action"] = "Capture owner sign-off."
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_stakeholder_comms(out_dir / "stakeholder-communication-plan.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("stakeholder_comms_context does not match assessments and waves" in error for error in result.errors))

    def test_validator_rejects_unknown_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][0]["workload_ids"].append("vm-made-up")
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_stakeholder_comms(out_dir / "stakeholder-communication-plan.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("references unknown workload_id 'vm-made-up'" in error for error in result.errors))

    def test_validator_rejects_duplicate_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][1]["workload_ids"].append(assessment["waves"][0]["workload_ids"][0])
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_stakeholder_comms(out_dir / "stakeholder-communication-plan.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("appears in multiple waves" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_stakeholder_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "stakeholder-communication-plan.csv"
            path.write_text(
                path.read_text(encoding="utf-8").replace("blocked_owner_review", "ready_owner_signoff", 1),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(
                any(check["name"] == "stakeholder-communication-plan" and check["status"] == "fail" for check in result.checks)
            )

    def test_cli_validates_stakeholder_comms(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-stakeholder-comms",
                        "--plan",
                        str(out_dir / "stakeholder-communication-plan.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(code, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
    inventory = merge_dependencies(inventory, read_dependency_csv(Path("examples/sample_dependencies.csv")))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
