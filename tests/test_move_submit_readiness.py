import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.move_payload import build_move_payload
from nmrcp.move_submit_readiness import LAB_ACK_VALUE, validate_move_submit_readiness
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class MoveSubmitReadinessTests(unittest.TestCase):
    def test_submit_readiness_passes_for_lab_reviewed_payload(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = build_lab_payload(Path(tmp), Path("examples/sample_move_payload_lab_config.json"))
            with patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": LAB_ACK_VALUE}):
                result = validate_move_submit_readiness(payload, Path("examples/sample_move_submit_review.json"))

            self.assertTrue(result.ok, result.errors)
            self.assertIn("payload-contract", [check["name"] for check in result.checks])
            self.assertIn("lab-acknowledgement", [check["name"] for check in result.checks])

    def test_submit_readiness_fails_on_placeholder_provider_ids(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = build_lab_payload(Path(tmp), Path("examples/sample_move_payload_config.json"))
            with patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": LAB_ACK_VALUE}):
                result = validate_move_submit_readiness(payload, Path("examples/sample_move_submit_review.json"))

            self.assertFalse(result.ok)
            self.assertTrue(any("source_provider" in error for error in result.errors))
            self.assertTrue(any("target_provider" in error for error in result.errors))

    def test_submit_readiness_fails_without_lab_acknowledgement(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = build_lab_payload(Path(tmp), Path("examples/sample_move_payload_lab_config.json"))
            with patch.dict("os.environ", {}, clear=True):
                result = validate_move_submit_readiness(payload, Path("examples/sample_move_submit_review.json"))

            self.assertFalse(result.ok)
            self.assertTrue(any("NMRCP_MOVE_LAB_ACK" in error for error in result.errors))

    def test_submit_readiness_fails_without_review_approvals(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = build_lab_payload(Path(tmp), Path("examples/sample_move_payload_lab_config.json"))
            review = Path(tmp) / "review.json"
            data = json.loads(Path("examples/sample_move_submit_review.json").read_text(encoding="utf-8"))
            data["approvals"]["rollback_reviewed"] = False
            review.write_text(json.dumps(data), encoding="utf-8")

            with patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": LAB_ACK_VALUE}):
                result = validate_move_submit_readiness(payload, review)

            self.assertFalse(result.ok)
            self.assertTrue(any("rollback_reviewed" in error for error in result.errors))


def build_lab_payload(tmp: Path, config_path: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    assessment_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, assessment_dir)
    payload = build_move_payload(assessment_dir / "nutanix-move-plan.csv", config_path)
    payload_path = tmp / "move-api-payload.dry-run.json"
    payload_path.write_text(json.dumps(payload), encoding="utf-8")
    return payload_path


if __name__ == "__main__":
    unittest.main()
