import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.risk_register import validate_risk_register
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class RiskRegisterTests(unittest.TestCase):
    def test_validate_risk_register_matches_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_risk_register(out_dir / "migration-risk-register.csv", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("rows=", result.summary())

    def test_validate_risk_register_rejects_tampered_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            register = out_dir / "migration-risk-register.csv"
            register.write_text(
                register.read_text(encoding="utf-8").replace("vds_mapping_required,medium,2,", "vds_mapping_required,medium,99,"),
                encoding="utf-8",
            )

            result = validate_risk_register(register, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("vds_mapping_required: affected_workloads expected '2'" in error for error in result.errors))

    def test_validate_risk_register_rejects_unknown_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][0]["workload_ids"].append("vm-hidden")
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_risk_register(out_dir / "migration-risk-register.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("references unknown workload_id 'vm-hidden'" in error for error in result.errors))

    def test_validate_risk_register_rejects_duplicate_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][1]["workload_ids"].append("vm-1001")
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_risk_register(out_dir / "migration-risk-register.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("appears in multiple waves" in error for error in result.errors))

    def test_cli_validate_risk_register(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                result = main(
                    [
                        "validate-risk-register",
                        "--register",
                        str(out_dir / "migration-risk-register.csv"),
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
