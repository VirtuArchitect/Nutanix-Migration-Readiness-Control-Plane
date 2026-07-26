import csv
import json
import tempfile
import unittest
from pathlib import Path

from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.move_plan import MOVE_PLAN_COLUMNS, validate_move_plan
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class MovePlanValidationTests(unittest.TestCase):
    def test_generated_move_plan_passes_validation(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_assessment(inventory, assessments, waves, out_dir)

            result = validate_move_plan(out_dir / "nutanix-move-plan.csv", out_dir / "assessment.json")
            with (out_dir / "nutanix-move-plan.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.row_count, 3)
            self.assertEqual(result.included_count, 1)
            self.assertEqual(rows[0]["application_owner_approval"], "confirmed")
            self.assertEqual(rows[0]["rollback_owner"], "Platform Team")

    def test_assessment_bound_validation_rejects_tampered_source_fields(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            plan_path = out_dir / "nutanix-move-plan.csv"
            write_assessment(inventory, assessments, waves, out_dir)
            with plan_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            rows[0]["source_vm_name"] = "renamed-outside-assessment"
            with plan_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=MOVE_PLAN_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)

            result = validate_move_plan(plan_path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("source_vm_name expected" in error for error in result.errors))

    def test_assessment_bound_validation_rejects_extra_workload(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            plan_path = out_dir / "nutanix-move-plan.csv"
            write_assessment(inventory, assessments, waves, out_dir)
            with plan_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            extra = dict(rows[0])
            extra["source_vm_id"] = "vm-extra"
            extra["source_vm_name"] = "extra-vm"
            rows.append(extra)
            with plan_path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=MOVE_PLAN_COLUMNS)
                writer.writeheader()
                writer.writerows(rows)

            result = validate_move_plan(plan_path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("workload not present in assessment: vm-extra" in error for error in result.errors))

    def test_blocked_included_workload_fails_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad-plan.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=MOVE_PLAN_COLUMNS,
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "schema_version": "nmrcp_move_plan_v1",
                        "include_in_move_plan": "yes",
                        "wave": "Excluded Until Cleared",
                        "source_vm_id": "vm-1",
                        "source_vm_name": "blocked-vm",
                        "owner": "apps",
                        "target": "ahv",
                        "readiness": "blocked",
                        "risk_score": "80",
                        "target_networks": "120",
                        "dependency_count": "0",
                        "application_owner_approval": "confirmed",
                        "rollback_owner": "apps",
                        "precheck_status": "ready_for_move_staging",
                        "required_actions": "backup_not_confirmed",
                    }
                )

            result = validate_move_plan(path)

            self.assertFalse(result.ok)
            self.assertTrue(any("cannot be included" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
