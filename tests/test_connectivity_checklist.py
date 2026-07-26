from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.connectivity_checklist import read_rows, validate_connectivity_checklist
from nmrcp.dependencies import merge_dependencies, read_dependency_csv
from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class ConnectivityChecklistTests(unittest.TestCase):
    def test_write_assessment_generates_connectivity_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_connectivity_checklist(out_dir / "connectivity-checklist.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "connectivity-checklist.csv", [])

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.rows, 3)
            by_source = {row["source_workload_id"]: row for row in rows}
            self.assertEqual(by_source["vm-1001"]["protocol"], "tcp")
            self.assertEqual(by_source["vm-1001"]["ports"], "5432")
            self.assertEqual(by_source["vm-1001"]["connectivity_status"], "ready")
            self.assertEqual(by_source["vm-3030"]["dependency_owner"], "not assigned")
            self.assertEqual(by_source["vm-3030"]["connectivity_status"], "blocked")
            self.assertIn("Assign dependency", by_source["vm-3030"]["required_action"])

    def test_connectivity_checklist_validator_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "connectivity-checklist.csv"
            rows = read_rows(path, [])
            rows[0]["ports"] = "443"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_connectivity_checklist(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("Missing connectivity checklist row" in error for error in result.errors))
            self.assertTrue(any("Unexpected connectivity checklist row" in error for error in result.errors))

    def test_cli_validate_connectivity_checklist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-connectivity-checklist",
                        "--checklist",
                        str(out_dir / "connectivity-checklist.csv"),
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
    waves = plan_waves(assessments, inventory)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
