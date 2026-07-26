import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_validation_checklist
from nmrcp.validation_checklist import validate_validation_checklist


class ValidationChecklistTests(unittest.TestCase):
    def test_generated_validation_checklist_passes_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            checklist = Path(tmp) / "pre-post-validation-checklist.md"
            write_validation_checklist(checklist)

            result = validate_validation_checklist(checklist)

            self.assertTrue(result.ok, result.errors)
            self.assertIn("PASS", result.summary())

    def test_validation_checklist_rejects_missing_stop_condition(self):
        with tempfile.TemporaryDirectory() as tmp:
            checklist = Path(tmp) / "pre-post-validation-checklist.md"
            write_validation_checklist(checklist)
            checklist.write_text(
                checklist.read_text(encoding="utf-8").replace(
                    "- Stop if an excluded or blocked workload appears in the execution list.",
                    "",
                ),
                encoding="utf-8",
            )

            result = validate_validation_checklist(checklist)

            self.assertFalse(result.ok)
            self.assertTrue(any("excluded or blocked workload" in error for error in result.errors))

    def test_cli_validate_validation_checklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            checklist = Path(tmp) / "pre-post-validation-checklist.md"
            write_validation_checklist(checklist)

            with patch("sys.stdout"):
                code = main(["validate-validation-checklist", "--checklist", str(checklist)])

            self.assertEqual(code, 0)
