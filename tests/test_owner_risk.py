import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.owner_risk import validate_owner_risk_summary
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class OwnerRiskTests(unittest.TestCase):
    def test_validate_owner_risk_matches_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_owner_risk_summary(out_dir / "owner-risk-summary.csv", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("rows=", result.summary())

    def test_validate_owner_risk_rejects_tampered_owner_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            summary = out_dir / "owner-risk-summary.csv"
            summary.write_text(
                summary.read_text(encoding="utf-8").replace("Business Apps,1,", "Business Apps,99,"),
                encoding="utf-8",
            )

            result = validate_owner_risk_summary(summary, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("Business Apps: total_workloads expected '1'" in error for error in result.errors))

    def test_validate_owner_risk_rejects_unknown_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][0]["workload_ids"].append("vm-shadow")
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_owner_risk_summary(out_dir / "owner-risk-summary.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("references unknown workload_id 'vm-shadow'" in error for error in result.errors))

    def test_validate_owner_risk_rejects_duplicate_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][1]["workload_ids"].append(assessment["waves"][0]["workload_ids"][0])
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_owner_risk_summary(out_dir / "owner-risk-summary.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("appears in multiple waves" in error for error in result.errors))

    def test_cli_validate_owner_risk_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                result = main(
                    [
                        "validate-owner-risk-summary",
                        "--summary",
                        str(out_dir / "owner-risk-summary.csv"),
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
