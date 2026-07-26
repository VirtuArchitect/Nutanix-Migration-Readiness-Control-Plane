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
from nmrcp.partner_handoff_matrix import read_rows, validate_partner_handoff_matrix
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class PartnerHandoffMatrixTests(unittest.TestCase):
    def test_generated_matrix_assigns_partner_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment = json.loads((out_dir / "assessment.json").read_text(encoding="utf-8"))

            result = validate_partner_handoff_matrix(out_dir / "partner-handoff-matrix.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "partner-handoff-matrix.csv", [])
            by_role = {row["role"]: row for row in rows}

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(assessment["partner_handoff_context"]["schema_version"], "nmrcp_partner_handoff_matrix_v1")
            self.assertEqual(result.rows, 7)
            self.assertEqual(by_role["migration_lead"]["handoff_status"], "blocked")
            self.assertIn("wave-execution-calendar.csv", by_role["migration_lead"]["owned_artifacts"])
            self.assertIn("what-will-break-report.csv", by_role["application_owner"]["owned_artifacts"])
            self.assertEqual(by_role["move_operator"]["handoff_status"], "blocked")
            self.assertIn("Approved non-production Move appliance proof", by_role["move_operator"]["blocking_condition"])

    def test_validator_rejects_tampered_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "partner-handoff-matrix.csv"
            rows = read_rows(path, [])
            rows[0]["handoff_status"] = "ready"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_partner_handoff_matrix(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("handoff_status expected 'blocked'" in error for error in result.errors))

    def test_validator_rejects_tampered_embedded_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            for row in assessment["partner_handoff_context"]["roles"]:
                if row["role"] == "migration_lead":
                    row["handoff_status"] = "ready"
                    row["blocking_condition"] = ""
                    row["next_action"] = "Package evidence and schedule review."
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_partner_handoff_matrix(out_dir / "partner-handoff-matrix.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("partner_handoff_context does not match assessments and waves" in error for error in result.errors))

    def test_validator_rejects_unknown_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][0]["workload_ids"].append("vm-invented")
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_partner_handoff_matrix(out_dir / "partner-handoff-matrix.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("references unknown workload_id 'vm-invented'" in error for error in result.errors))

    def test_validator_rejects_duplicate_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][1]["workload_ids"].append(assessment["waves"][0]["workload_ids"][0])
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_partner_handoff_matrix(out_dir / "partner-handoff-matrix.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("appears in multiple waves" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "partner-handoff-matrix.csv"
            path.write_text(
                path.read_text(encoding="utf-8").replace("move-api-payload.dry-run.json", "move-api-payload.live.json", 1),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "partner-handoff-matrix" and check["status"] == "fail" for check in result.checks))

    def test_cli_validates_partner_handoff_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-partner-handoff",
                        "--matrix",
                        str(out_dir / "partner-handoff-matrix.csv"),
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
