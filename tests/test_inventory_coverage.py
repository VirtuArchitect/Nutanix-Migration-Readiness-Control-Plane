import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.inventory_coverage import validate_inventory_coverage_csv


class InventoryCoverageTests(unittest.TestCase):
    def test_inventory_coverage_passes_for_included_workload_without_gaps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            coverage = write_coverage(
                root,
                [
                    {
                        "workload_id": "vm-1",
                        "name": "app-01",
                        "coverage_percent": "100",
                        "present_fields": "owner;guest_os;networking;guest_identity;tools;backup;storage;application_owner_approval;rollback_owner",
                        "partial_fields": "",
                        "missing_fields": "",
                    }
                ],
            )
            move_plan = write_move_plan(root, included_ids=["vm-1"])

            result = validate_inventory_coverage_csv(coverage, move_plan)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.included_gap_count, 0)

    def test_inventory_coverage_warns_on_low_nonincluded_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            coverage = write_coverage(
                Path(tmp),
                [
                    {
                        "workload_id": "vm-2",
                        "name": "hold-01",
                        "coverage_percent": "75",
                        "present_fields": "owner",
                        "partial_fields": "",
                        "missing_fields": "guest_identity;rollback_owner",
                    }
                ],
            )

            result = validate_inventory_coverage_csv(coverage)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.low_coverage_count, 1)
        self.assertTrue(any("below 90%" in warning for warning in result.warnings))

    def test_inventory_coverage_fails_for_included_workload_critical_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            coverage = write_coverage(
                root,
                [
                    {
                        "workload_id": "vm-1",
                        "name": "app-01",
                        "coverage_percent": "88",
                        "present_fields": "owner;guest_os;networking;tools;backup;storage;application_owner_approval",
                        "partial_fields": "",
                        "missing_fields": "guest_identity;rollback_owner",
                    }
                ],
            )
            move_plan = write_move_plan(root, included_ids=["vm-1"])

            result = validate_inventory_coverage_csv(coverage, move_plan)

        self.assertFalse(result.ok)
        self.assertTrue(any("critical inventory coverage gaps" in error for error in result.errors))
        self.assertTrue(any("guest_identity" in error and "rollback_owner" in error for error in result.errors))

    def test_cli_validate_inventory_coverage_uses_move_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            coverage = write_coverage(
                root,
                [
                    {
                        "workload_id": "vm-1",
                        "name": "app-01",
                        "coverage_percent": "100",
                        "present_fields": "owner;guest_os;networking;guest_identity;tools;backup;storage;application_owner_approval;rollback_owner",
                        "partial_fields": "",
                        "missing_fields": "",
                    }
                ],
            )
            move_plan = write_move_plan(root, included_ids=["vm-1"])

            with patch("sys.stdout"):
                code = main(["validate-inventory-coverage", "--coverage", str(coverage), "--move-plan", str(move_plan)])

        self.assertEqual(code, 0)


def write_coverage(root: Path, rows: list[dict[str, str]]) -> Path:
    path = root / "inventory-coverage.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "workload_id",
                "name",
                "coverage_percent",
                "present_fields",
                "partial_fields",
                "missing_fields",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_move_plan(root: Path, included_ids: list[str]) -> Path:
    path = root / "nutanix-move-plan.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "schema_version",
                "include_in_move_plan",
                "wave",
                "source_vm_id",
                "source_vm_name",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        for workload_id in included_ids:
            writer.writerow(
                {
                    "schema_version": "nmrcp_move_plan_v1",
                    "include_in_move_plan": "yes",
                    "wave": "Wave 0 - Pilot Ready",
                    "source_vm_id": workload_id,
                    "source_vm_name": f"{workload_id}-name",
                }
            )
    return path


if __name__ == "__main__":
    unittest.main()
