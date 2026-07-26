import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.move_lab_evidence_request import validate_move_lab_evidence_request, write_move_lab_evidence_request
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class MoveLabEvidenceRequestTests(unittest.TestCase):
    def test_generated_request_validates_lab_scope_and_closeout(self):
        inventory = sample_inventory()
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "move-lab-evidence-request.md"

            write_move_lab_evidence_request(assessments, waves, path)
            result = validate_move_lab_evidence_request(path)

            self.assertTrue(result.ok, result.errors)
            text = path.read_text(encoding="utf-8")
            self.assertIn("non-production Nutanix Move appliance", text)
            self.assertIn("generate-approved-move-lab-proof", text)
            self.assertIn("validate-move-lab-proof", text)
            self.assertIn("validate-move-lab-evidence-intake", text)
            self.assertIn("started_migrations=0", text)

    def test_validator_rejects_missing_intake_closeout(self):
        inventory = sample_inventory()
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "move-lab-evidence-request.md"
            write_move_lab_evidence_request(assessments, waves, path)
            text = path.read_text(encoding="utf-8").replace("validate-move-lab-evidence-intake", "validate-move-lab-transcript")
            path.write_text(text, encoding="utf-8")

            result = validate_move_lab_evidence_request(path)

            self.assertFalse(result.ok)
            self.assertTrue(any("validate-move-lab-evidence-intake" in error for error in result.errors))

    def test_validator_rejects_missing_proof_generator(self):
        inventory = sample_inventory()
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "move-lab-evidence-request.md"
            write_move_lab_evidence_request(assessments, waves, path)
            text = path.read_text(encoding="utf-8").replace("generate-approved-move-lab-proof", "validate-move-lab-proof")
            path.write_text(text, encoding="utf-8")

            result = validate_move_lab_evidence_request(path)

            self.assertFalse(result.ok)
            self.assertTrue(any("generate-approved-move-lab-proof" in error for error in result.errors))

    def test_assessment_writes_request_and_cli_validates_it(self):
        inventory = sample_inventory()
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            write_assessment(inventory, assessments, waves, out_dir)

            request = out_dir / "move-lab-evidence-request.md"
            with patch("sys.stdout"):
                code = main(["validate-move-lab-evidence-request", "--request", str(request)])

            self.assertEqual(code, 0)
            self.assertTrue(request.exists())


if __name__ == "__main__":
    unittest.main()


def sample_inventory():
    return json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
