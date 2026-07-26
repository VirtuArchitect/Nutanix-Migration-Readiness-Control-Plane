import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.target_reconciliation import (
    reconcile_target_inventory,
    validate_target_reconciliation_csv,
    write_target_reconciliation_csv,
)
from nmrcp.waves import plan_waves
from nmrcp.cli import main


class TargetReconciliationTests(unittest.TestCase):
    def test_reconciliation_warns_for_held_workload_name_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            result = reconcile_target_inventory(
                Path("examples/sample_inventory.json"),
                Path("examples/sample_prism_inventory.json"),
                out_dir / "nutanix-move-plan.csv",
            )

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.matched, 1)
            self.assertTrue(any("held workload name already exists" in warning for warning in result.warnings))
            matched = next(row for row in result.rows if row["source_vm_name"] == "erp-app-01")
            self.assertEqual(matched["status"], "warn")

    def test_reconciliation_fails_when_included_workload_name_exists_in_prism(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_assessment(tmp_path)
            target = json.loads(Path("examples/sample_prism_inventory.json").read_text(encoding="utf-8"))
            target["workloads"].append({"id": "uuid-collision", "name": "pilot-web-01"})
            target_path = tmp_path / "target.json"
            target_path.write_text(json.dumps(target), encoding="utf-8")

            result = reconcile_target_inventory(
                Path("examples/sample_inventory.json"),
                target_path,
                out_dir / "nutanix-move-plan.csv",
            )

            self.assertFalse(result.ok)
            self.assertTrue(any("included workload name already exists" in error for error in result.errors))

    def test_write_and_validate_reconciliation_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_assessment(tmp_path)
            result = reconcile_target_inventory(
                Path("examples/sample_inventory.json"),
                Path("examples/sample_prism_inventory.json"),
                out_dir / "nutanix-move-plan.csv",
            )
            output = tmp_path / "target-reconciliation.csv"

            write_target_reconciliation_csv(result, output)
            validation = validate_target_reconciliation_csv(output)

            self.assertTrue(validation.ok, validation.errors)
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["schema_version"], "nmrcp_target_reconciliation_v1")

    def test_cli_reconcile_and_validate_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            output = Path(tmp) / "target-reconciliation.csv"
            with patch("sys.stdout"):
                reconcile_code = main(
                    [
                        "reconcile-target",
                        "--inventory",
                        "examples/sample_inventory.json",
                        "--target-inventory",
                        "examples/sample_prism_inventory.json",
                        "--plan",
                        str(out_dir / "nutanix-move-plan.csv"),
                        "--out",
                        str(output),
                    ]
                )
                validate_code = main(["validate-target-reconciliation", "--reconciliation", str(output)])

            self.assertEqual(reconcile_code, 0)
            self.assertEqual(validate_code, 0)


def build_assessment(tmp_path: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    out_dir = tmp_path / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
