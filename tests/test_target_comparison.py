import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.change_gate import run_change_gate
from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.target_comparison import validate_target_readiness_comparison
from nmrcp.waves import plan_waves


class TargetComparisonTests(unittest.TestCase):
    def test_assessment_contains_redacted_target_comparison_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment = json.loads((out_dir / "assessment.json").read_text(encoding="utf-8"))

            context = assessment["target_comparison_context"]

            self.assertEqual(context["schema_version"], "nmrcp_target_comparison_context_v1")
            self.assertEqual(len(context["workloads"]), 3)
            self.assertNotIn("password", json.dumps(context).lower())

    def test_validate_target_comparison_matches_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_target_readiness_comparison(out_dir / "target-readiness-comparison.csv", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("rows=3", result.summary())

    def test_validate_target_comparison_rejects_tampered_preference(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            comparison = out_dir / "target-readiness-comparison.csv"
            comparison.write_text(
                comparison.read_text(encoding="utf-8").replace(",either,AHV and NC2 readiness are equivalent", ",nc2,AHV and NC2 readiness are equivalent", 1),
                encoding="utf-8",
            )

            result = validate_target_readiness_comparison(comparison, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("preferred_target expected" in error for error in result.errors))

    def test_validate_target_comparison_rejects_stale_context_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["target_comparison_context"]["workloads"][0]["owner"] = "Wrong Owner"
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_target_readiness_comparison(out_dir / "target-readiness-comparison.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("target_comparison_context" in error and "owner expected" in error for error in result.errors))

    def test_validate_target_comparison_rejects_unknown_context_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            extra = dict(assessment["target_comparison_context"]["workloads"][0])
            extra["workload_id"] = "vm-hidden"
            extra["name"] = "hidden-vm"
            assessment["target_comparison_context"]["workloads"].append(extra)
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_target_readiness_comparison(out_dir / "target-readiness-comparison.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("references unknown workload_id 'vm-hidden'" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_target_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            comparison = out_dir / "target-readiness-comparison.csv"
            comparison.write_text(
                comparison.read_text(encoding="utf-8").replace(",either,AHV and NC2 readiness are equivalent", ",nc2,AHV and NC2 readiness are equivalent", 1),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "target-readiness-comparison" and check["status"] == "fail" for check in result.checks))

    def test_cli_validate_target_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                result = main(
                    [
                        "validate-target-comparison",
                        "--comparison",
                        str(out_dir / "target-readiness-comparison.csv"),
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
