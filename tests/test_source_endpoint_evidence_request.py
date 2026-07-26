import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.source_endpoint_evidence_request import (
    validate_source_endpoint_evidence_request,
    write_source_endpoint_evidence_request,
)
from nmrcp.waves import plan_waves


class SourceEndpointEvidenceRequestTests(unittest.TestCase):
    def test_generated_request_validates_read_only_source_scope(self):
        inventory = sample_inventory()
        assessments = assess_inventory(inventory)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source-endpoint-evidence-request.md"

            write_source_endpoint_evidence_request(assessments, path)
            result = validate_source_endpoint_evidence_request(path)

            self.assertTrue(result.ok, result.errors)
            text = path.read_text(encoding="utf-8")
            self.assertIn("validate-live-proof", text)
            self.assertIn("validate-assessment-intake", text)
            self.assertIn("--assessment-intake outputs\\assessment-intake.csv", text)
            self.assertIn("mutating_calls=0", text)
            self.assertIn("credentials_serialized=false", text)

    def test_validator_rejects_missing_live_proof_closeout(self):
        inventory = sample_inventory()
        assessments = assess_inventory(inventory)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source-endpoint-evidence-request.md"
            write_source_endpoint_evidence_request(assessments, path)
            text = path.read_text(encoding="utf-8").replace("validate-live-proof", "validate-inventory")
            path.write_text(text, encoding="utf-8")

            result = validate_source_endpoint_evidence_request(path)

            self.assertFalse(result.ok)
            self.assertTrue(any("validate-live-proof" in error for error in result.errors))

    def test_validator_rejects_missing_assessment_intake_binding(self):
        inventory = sample_inventory()
        assessments = assess_inventory(inventory)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "source-endpoint-evidence-request.md"
            write_source_endpoint_evidence_request(assessments, path)
            text = path.read_text(encoding="utf-8").replace("--assessment-intake", "--no-intake", 1)
            path.write_text(text, encoding="utf-8")

            result = validate_source_endpoint_evidence_request(path)

            self.assertFalse(result.ok)
            self.assertTrue(any("--assessment-intake" in error for error in result.errors))

    def test_assessment_writes_request_and_cli_validates_it(self):
        inventory = sample_inventory()
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            write_assessment(inventory, assessments, waves, out_dir)

            request = out_dir / "source-endpoint-evidence-request.md"
            with patch("sys.stdout"):
                code = main(["validate-source-endpoint-evidence-request", "--request", str(request)])

            self.assertEqual(code, 0)
            self.assertTrue(request.exists())


def sample_inventory():
    return json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
