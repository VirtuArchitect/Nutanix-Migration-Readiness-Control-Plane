import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.migration_runbook import validate_migration_runbook
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class MigrationRunbookTests(unittest.TestCase):
    def test_generated_migration_runbook_passes_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_migration_runbook(out_dir / "migration-runbook.md", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("PASS", result.summary())

    def test_migration_runbook_rejects_missing_hold_instruction(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            runbook = out_dir / "migration-runbook.md"
            runbook.write_text(
                runbook.read_text(encoding="utf-8").replace(
                    "- Do not stage this workload in Nutanix Move until all required actions are cleared.",
                    "",
                ),
                encoding="utf-8",
            )

            result = validate_migration_runbook(runbook, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("hold instruction" in error for error in result.errors))

    def test_cli_validate_migration_runbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-migration-runbook",
                        "--runbook",
                        str(out_dir / "migration-runbook.md"),
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
