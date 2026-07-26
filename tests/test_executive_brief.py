import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.executive_brief import validate_executive_brief
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class ExecutiveBriefTests(unittest.TestCase):
    def test_validate_executive_brief_matches_assessment_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_executive_brief(out_dir / "executive-readiness-brief.md", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("checks=", result.summary())

    def test_validate_executive_brief_rejects_tampered_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            brief = out_dir / "executive-readiness-brief.md"
            brief.write_text(
                brief.read_text(encoding="utf-8").replace("- Workloads assessed: 3", "- Workloads assessed: 99"),
                encoding="utf-8",
            )

            result = validate_executive_brief(brief, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("Workloads assessed: 3" in error for error in result.errors))

    def test_validate_executive_brief_rejects_tampered_wave_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            brief = out_dir / "executive-readiness-brief.md"
            brief.write_text(
                brief.read_text(encoding="utf-8").replace(
                    "- Wave 0 - Pilot Ready: 1 workloads, staging `ready`, held `none`.",
                    "- Wave 0 - Pilot Ready: 1 workloads, staging `hold`, held `none`.",
                ),
                encoding="utf-8",
            )

            result = validate_executive_brief(brief, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("Wave 0 - Pilot Ready" in error for error in result.errors))

    def test_cli_validate_executive_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                result = main(
                    [
                        "validate-executive-brief",
                        "--brief",
                        str(out_dir / "executive-readiness-brief.md"),
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
