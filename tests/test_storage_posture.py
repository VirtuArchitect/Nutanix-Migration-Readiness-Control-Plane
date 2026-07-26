import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.storage_posture import STORAGE_POSTURE_SCHEMA_VERSION, validate_storage_posture
from nmrcp.waves import plan_waves


class StoragePostureTests(unittest.TestCase):
    def test_write_assessment_generates_storage_posture(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp), with_storage_risk=True)

            result = validate_storage_posture(out_dir / "storage-posture.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "storage-posture.csv")

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.rows, 3)
        pilot = next(row for row in rows if row["workload_id"] == "vm-1001")
        self.assertEqual(pilot["schema_version"], STORAGE_POSTURE_SCHEMA_VERSION)
        self.assertEqual(pilot["storage_status"], "blocked")
        self.assertEqual(pilot["raw_device_mapping"], "true")
        self.assertIn("storage_rdm_mapping_required", pilot["blocking_findings"])
        self.assertIn("Convert or redesign raw device mappings", pilot["required_action"])

    def test_storage_posture_validator_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp), with_storage_risk=True)
            path = out_dir / "storage-posture.csv"
            rows = read_rows(path)
            for row in rows:
                if row["workload_id"] == "vm-1001":
                    row["storage_status"] = "ready"
            write_rows(path, rows)

            result = validate_storage_posture(path, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("vm-1001: storage_status expected 'blocked'" in error for error in result.errors))

    def test_cli_validate_storage_posture(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp), with_storage_risk=True)

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-storage-posture",
                        "--posture",
                        str(out_dir / "storage-posture.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

        self.assertEqual(code, 0)


def build_assessment(tmp: Path, *, with_storage_risk: bool = False) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    if with_storage_risk:
        storage = inventory["workloads"][0]["storage"]
        storage["raw_device_mapping"] = True
        storage["shared_disk"] = True
        storage["independent_disk"] = True
        storage["encrypted"] = True
        storage["min_datastore_free_percent"] = 8
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
