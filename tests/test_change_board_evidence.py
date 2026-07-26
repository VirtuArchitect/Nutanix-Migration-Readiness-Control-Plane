import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.change_board_evidence import validate_change_board_evidence
from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class ChangeBoardEvidenceTests(unittest.TestCase):
    def test_generated_change_board_evidence_passes_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_change_board_evidence(out_dir / "change-board-evidence.md", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("PASS", result.summary())

    def test_change_board_evidence_rejects_tampered_summary_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            evidence = out_dir / "change-board-evidence.md"
            evidence.write_text(
                evidence.read_text(encoding="utf-8").replace("- Blocked: 2", "- Blocked: 0"),
                encoding="utf-8",
            )

            result = validate_change_board_evidence(evidence, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("Blocked: 2" in error for error in result.errors))

    def test_change_board_evidence_rejects_missing_mutating_call_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            evidence = out_dir / "change-board-evidence.md"
            evidence.write_text(
                evidence.read_text(encoding="utf-8").replace("- Mutating calls: `0`", ""),
                encoding="utf-8",
            )

            result = validate_change_board_evidence(evidence, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("Mutating calls" in error for error in result.errors))

    def test_cli_validate_change_board_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-change-board-evidence",
                        "--evidence",
                        str(out_dir / "change-board-evidence.md"),
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
