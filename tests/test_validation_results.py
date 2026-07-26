import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.validation_results import validate_validation_results, write_validation_template
from nmrcp.waves import plan_waves


class ValidationResultsTests(unittest.TestCase):
    def test_template_generation_uses_included_move_plan_workloads(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            template = Path(tmp) / "validation-template.csv"
            write_assessment(inventory, assessments, waves, out_dir)
            write_validation_template(out_dir / "nutanix-move-plan.csv", template)

            with template.open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 11)
            self.assertEqual({row["source_vm_id"] for row in rows}, {"vm-1001"})
            self.assertEqual({row["status"] for row in rows}, {"not_checked"})

    def test_validation_results_pass_when_all_checks_pass(self):
        result = validate_validation_results(Path("examples/sample_validation_results.csv"))

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.row_count, 11)
        self.assertEqual(result.pass_count, 11)
        self.assertEqual(result.open_count, 0)

    def test_validation_results_fail_closed_on_open_checks(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            template = Path(tmp) / "validation-template.csv"
            write_assessment(inventory, assessments, waves, out_dir)
            write_validation_template(out_dir / "nutanix-move-plan.csv", template)

            result = validate_validation_results(template)
            draft_result = validate_validation_results(template, allow_open=True)

            self.assertFalse(result.ok)
            self.assertTrue(any("not_checked blocks" in error for error in result.errors))
            self.assertTrue(draft_result.ok, draft_result.errors)

    def test_cli_generates_and_validates_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            template = Path(tmp) / "validation-template.csv"
            with patch("sys.stdout"):
                assess_code = main(["assess", "--inventory", "examples/sample_inventory.json", "--out", str(out_dir)])
                template_code = main(
                    [
                        "generate-validation-template",
                        "--plan",
                        str(out_dir / "nutanix-move-plan.csv"),
                        "--out",
                        str(template),
                    ]
                )
                draft_code = main(["validate-validation-results", "--results", str(template), "--allow-open"])
                final_code = main(["validate-validation-results", "--results", "examples/sample_validation_results.csv"])

            self.assertEqual(assess_code, 0)
            self.assertEqual(template_code, 0)
            self.assertEqual(draft_code, 0)
            self.assertEqual(final_code, 0)


if __name__ == "__main__":
    unittest.main()
