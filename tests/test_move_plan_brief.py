import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.change_gate import run_change_gate
from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.move_plan_brief import validate_move_plan_brief
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class MovePlanBriefTests(unittest.TestCase):
    def test_generated_move_plan_brief_validates_against_plan_and_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            brief = out_dir / "move-plan-brief.md"

            result = validate_move_plan_brief(brief, out_dir / "nutanix-move-plan.csv", out_dir / "assessment.json")
            text = brief.read_text(encoding="utf-8")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("# Nutanix Move Plan Brief", text)
            self.assertIn("nmrcp_move_plan_brief_v1", text)
            self.assertIn("Move plan schema: `nmrcp_move_plan_v1`", text)
            self.assertIn("Include `pilot-web-01` (`vm-1001`)", text)
            self.assertIn("Hold `payments-edge-01` (`vm-3030`)", text)
            self.assertIn("Do not submit this plan to Nutanix Move", text)
            self.assertNotIn("vcenter01.corp.local", text)

    def test_validator_rejects_tampered_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            brief = out_dir / "move-plan-brief.md"
            brief.write_text(
                brief.read_text(encoding="utf-8").replace("hold blocked or remediation-required workloads", "submit all workloads", 1),
                encoding="utf-8",
            )

            result = validate_move_plan_brief(brief, out_dir / "nutanix-move-plan.csv", out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("does not match" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_move_plan_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            brief = out_dir / "move-plan-brief.md"
            brief.write_text(
                brief.read_text(encoding="utf-8").replace("nmrcp_move_plan_brief_v1", "nmrcp_softened_move_plan_brief_v1"),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "move-plan-brief" and check["status"] == "fail" for check in result.checks))

    def test_cli_generates_and_validates_move_plan_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            regenerated = Path(tmp) / "regenerated-move-plan-brief.md"

            with patch("sys.stdout"):
                generate_code = main(
                    [
                        "move-plan-brief",
                        "--plan",
                        str(out_dir / "nutanix-move-plan.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                        "--out",
                        str(regenerated),
                    ]
                )
                validate_code = main(
                    [
                        "validate-move-plan-brief",
                        "--brief",
                        str(regenerated),
                        "--plan",
                        str(out_dir / "nutanix-move-plan.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(generate_code, 0)
            self.assertEqual(validate_code, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
