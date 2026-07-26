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
from nmrcp.wave_execution_calendar import read_rows, validate_wave_execution_calendar
from nmrcp.waves import plan_waves


class WaveExecutionCalendarTests(unittest.TestCase):
    def test_generated_calendar_groups_wave_execution_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment = json.loads((out_dir / "assessment.json").read_text(encoding="utf-8"))

            result = validate_wave_execution_calendar(out_dir / "wave-execution-calendar.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "wave-execution-calendar.csv", [])
            by_wave = {row["wave"]: row for row in rows}

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(assessment["wave_execution_calendar_context"]["schema_version"], "nmrcp_wave_execution_calendar_v1")
            self.assertEqual(result.rows, 3)
            self.assertEqual(by_wave["Wave 0 - Pilot Ready"]["move_staging_status"], "ready")
            self.assertEqual(by_wave["Wave 0 - Pilot Ready"]["window_type"], "pilot_or_standard_move_window")
            self.assertIn("nutanix-move-plan.csv", by_wave["Wave 0 - Pilot Ready"]["evidence_refs"])
            self.assertEqual(by_wave["Wave 2 - Remediation Required"]["move_staging_status"], "hold")
            self.assertIn("remediation_tracker_closed", by_wave["Wave 2 - Remediation Required"]["entry_gate"])
            self.assertEqual(by_wave["Excluded Until Cleared"]["window_type"], "blocked_no_move_window")
            self.assertIn("Do not schedule", by_wave["Excluded Until Cleared"]["operator_actions"])

    def test_validator_rejects_tampered_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "wave-execution-calendar.csv"
            rows = read_rows(path, [])
            rows[0]["move_staging_status"] = "hold"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_wave_execution_calendar(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("move_staging_status expected 'ready'" in error for error in result.errors))

    def test_validator_rejects_tampered_embedded_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            for row in assessment["wave_execution_calendar_context"]["waves"]:
                if row["wave"] == "Excluded Until Cleared":
                    row["window_type"] = "pilot_or_standard_move_window"
                    row["move_staging_status"] = "ready"
                    row["operator_actions"] = "Schedule controlled lab/staging review."
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_wave_execution_calendar(out_dir / "wave-execution-calendar.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("wave_execution_calendar_context does not match assessments and waves" in error for error in result.errors))

    def test_validator_rejects_unknown_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][0]["workload_ids"].append("vm-ghost")
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_wave_execution_calendar(out_dir / "wave-execution-calendar.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("references unknown workload_id 'vm-ghost'" in error for error in result.errors))

    def test_validator_rejects_duplicate_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][1]["workload_ids"].append(assessment["waves"][0]["workload_ids"][0])
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_wave_execution_calendar(out_dir / "wave-execution-calendar.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("appears in multiple waves" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "wave-execution-calendar.csv"
            path.write_text(
                path.read_text(encoding="utf-8").replace("blocked_no_move_window", "standard_move_window", 1),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "wave-execution-calendar" and check["status"] == "fail" for check in result.checks))

    def test_cli_validates_wave_execution_calendar(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-wave-execution-calendar",
                        "--calendar",
                        str(out_dir / "wave-execution-calendar.csv"),
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
