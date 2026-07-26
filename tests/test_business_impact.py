import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.business_impact import validate_business_impact_summary
from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class BusinessImpactTests(unittest.TestCase):
    def test_validate_business_impact_matches_assessment_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_business_impact_summary(out_dir / "business-impact-summary.csv", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("rows=", result.summary())

    def test_validate_business_impact_rejects_tampered_tier_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            summary = out_dir / "business-impact-summary.csv"
            summary.write_text(
                summary.read_text(encoding="utf-8").replace("critical,2,", "critical,99,"),
                encoding="utf-8",
            )

            result = validate_business_impact_summary(summary, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("total_workloads expected '2'" in error for error in result.errors))

    def test_validate_business_impact_rejects_stale_business_context_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["business_context"]["workloads"][0]["owner"] = "Wrong Owner"
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_business_impact_summary(out_dir / "business-impact-summary.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("business_context" in error and "owner expected" in error for error in result.errors))

    def test_validate_business_impact_rejects_unknown_wave_membership(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][0]["workload_ids"].append("vm-hidden")
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_business_impact_summary(out_dir / "business-impact-summary.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("references unknown workload_id 'vm-hidden'" in error for error in result.errors))

    def test_cli_validate_business_impact(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                result = main(
                    [
                        "validate-business-impact",
                        "--summary",
                        str(out_dir / "business-impact-summary.csv"),
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
