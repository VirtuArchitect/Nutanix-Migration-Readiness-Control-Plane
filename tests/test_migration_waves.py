import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.migration_waves import validate_migration_waves
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class MigrationWavesTests(unittest.TestCase):
    def test_validate_migration_waves_matches_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_migration_waves(out_dir / "migration-waves.csv", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("rows=3", result.summary())

    def test_validate_migration_waves_rejects_tampered_wave_assignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            waves = out_dir / "migration-waves.csv"
            waves.write_text(
                waves.read_text(encoding="utf-8").replace("Wave 0 - Pilot Ready,vm-1001", "Excluded Until Cleared,vm-1001"),
                encoding="utf-8",
            )

            result = validate_migration_waves(waves, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("vm-1001: wave expected 'Wave 0 - Pilot Ready'" in error for error in result.errors))

    def test_validate_migration_waves_rejects_unknown_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][0]["workload_ids"].append("vm-missing")
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_migration_waves(out_dir / "migration-waves.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("references unknown workload_id 'vm-missing'" in error for error in result.errors))

    def test_validate_migration_waves_rejects_duplicate_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][1]["workload_ids"].append(assessment["waves"][0]["workload_ids"][0])
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_migration_waves(out_dir / "migration-waves.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("appears in multiple waves" in error for error in result.errors))

    def test_cli_validate_migration_waves(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                result = main(
                    [
                        "validate-migration-waves",
                        "--waves",
                        str(out_dir / "migration-waves.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(result, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
