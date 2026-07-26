from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.rollback_plan import read_rows, validate_rollback_plan
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class RollbackPlanTests(unittest.TestCase):
    def test_write_assessment_generates_rollback_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_rollback_plan(out_dir / "rollback-plan.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "rollback-plan.csv", [])

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.rows, 3)
            by_id = {row["workload_id"]: row for row in rows}
            self.assertEqual(by_id["vm-1001"]["rollback_status"], "ready")
            self.assertEqual(by_id["vm-1001"]["rollback_owner"], "Platform Team")
            self.assertEqual(by_id["vm-2020"]["rollback_status"], "hold")
            self.assertEqual(by_id["vm-3030"]["rollback_status"], "hold")
            self.assertIn("recovery-readiness.csv#vm-1001", by_id["vm-1001"]["evidence_refs"])

    def test_rollback_plan_validator_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "rollback-plan.csv"
            rows = read_rows(path, [])
            rows[0]["rollback_status"] = "blocked"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_rollback_plan(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("rollback_status expected 'ready'" in error for error in result.errors))

    def test_rollback_plan_rejects_stale_context_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["rollback_plan_context"]["workloads"][0]["owner"] = "Wrong Owner"
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_rollback_plan(out_dir / "rollback-plan.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("rollback_plan_context" in error and "owner expected" in error for error in result.errors))

    def test_rollback_plan_rejects_stale_context_recovery_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            for row in assessment["rollback_plan_context"]["workloads"]:
                if row["workload_id"] == "vm-3030":
                    row["recovery_status"] = "ready"
                    row["rollback_status"] = "ready"
                    row["rollback_trigger"] = "Rollback if post-cutover validation fails."
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_rollback_plan(out_dir / "rollback-plan.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("recovery_status expected" in error for error in result.errors))
            self.assertTrue(any("rollback_status expected" in error for error in result.errors))

    def test_rollback_plan_rejects_unknown_wave_workload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][0]["workload_ids"].append("vm-ghost")
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_rollback_plan(out_dir / "rollback-plan.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("references unknown workload_id 'vm-ghost'" in error for error in result.errors))

    def test_rollback_plan_rejects_duplicate_wave_workload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][1]["workload_ids"].append(assessment["waves"][0]["workload_ids"][0])
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_rollback_plan(out_dir / "rollback-plan.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("appears in multiple waves" in error for error in result.errors))

    def test_rollback_plan_rejects_unknown_context_workload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            ghost = dict(assessment["rollback_plan_context"]["workloads"][0])
            ghost["workload_id"] = "vm-ghost"
            assessment["rollback_plan_context"]["workloads"].append(ghost)
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_rollback_plan(out_dir / "rollback-plan.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("rollback_plan_context references unknown workload_id 'vm-ghost'" in error for error in result.errors))

    def test_cli_validate_rollback_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-rollback-plan",
                        "--plan",
                        str(out_dir / "rollback-plan.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(code, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
