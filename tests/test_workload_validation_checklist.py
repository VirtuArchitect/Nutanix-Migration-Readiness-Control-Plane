from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves
from nmrcp.workload_validation_checklist import read_rows, validate_workload_validation_checklist


class WorkloadValidationChecklistTests(unittest.TestCase):
    def test_write_assessment_generates_workload_validation_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_workload_validation_checklist(out_dir / "workload-validation-checklist.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "workload-validation-checklist.csv", [])

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.rows, 15)
            ready_rows = [row for row in rows if row["workload_id"] == "vm-1001"]
            blocked_rows = [row for row in rows if row["workload_id"] == "vm-3030"]
            self.assertEqual({row["status"] for row in ready_rows}, {"blocked"})
            self.assertEqual({row["status"] for row in blocked_rows}, {"blocked"})
            self.assertTrue(any(row["validation_phase"] == "post_migration" for row in ready_rows))

    def test_workload_validation_checklist_validator_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "workload-validation-checklist.csv"
            rows = read_rows(path, [])
            rows[-1]["status"] = "ready"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_workload_validation_checklist(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("status expected 'blocked'" in error for error in result.errors))

    def test_cli_validate_workload_validation_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-workload-validation-checklist",
                        "--checklist",
                        str(out_dir / "workload-validation-checklist.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(code, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
