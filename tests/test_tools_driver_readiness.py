import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.tools_driver_readiness import (
    TOOLS_DRIVER_SCHEMA_VERSION,
    validate_tools_driver_readiness,
)
from nmrcp.waves import plan_waves


class ToolsDriverReadinessTests(unittest.TestCase):
    def test_write_assessment_generates_tools_driver_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_tools_driver_readiness(out_dir / "tools-driver-readiness.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "tools-driver-readiness.csv")

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.rows, 3)
        pilot = next(row for row in rows if row["workload_id"] == "vm-1001")
        erp = next(row for row in rows if row["workload_id"] == "vm-2020")
        self.assertEqual(pilot["schema_version"], TOOLS_DRIVER_SCHEMA_VERSION)
        self.assertEqual(pilot["driver_status"], "ready")
        self.assertEqual(erp["driver_status"], "remediate")
        self.assertIn("virtio_not_ready", erp["blocking_findings"])
        self.assertIn("Install or validate Nutanix VirtIO drivers", erp["required_action"])

    def test_tools_driver_readiness_validator_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "tools-driver-readiness.csv"
            rows = read_rows(path)
            for row in rows:
                if row["workload_id"] == "vm-2020":
                    row["driver_status"] = "ready"
            write_rows(path, rows)

            result = validate_tools_driver_readiness(path, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("vm-2020: driver_status expected 'remediate'" in error for error in result.errors))

    def test_cli_validate_tools_driver_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-tools-driver-readiness",
                        "--readiness",
                        str(out_dir / "tools-driver-readiness.csv"),
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
