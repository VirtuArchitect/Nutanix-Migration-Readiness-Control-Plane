import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.move_lab_capture_kit import validate_move_lab_capture_kit, validate_move_lab_capture_kit_validation_file, write_move_lab_capture_kit
from nmrcp.move_lab_transcript import validate_move_lab_transcript


class MoveLabTranscriptTests(unittest.TestCase):
    def test_move_lab_transcript_passes_for_redacted_approved_lab_round_trip(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
            root = Path(tmp)
            payload = write_payload(root)
            transcript = write_transcript(root, payload)

            result = validate_move_lab_transcript(transcript, payload, Path("examples/sample_move_submit_review.json"))

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.status, "warn")
        self.assertTrue(any("request_sha256 not supplied" in warning for warning in result.warnings))
        payload_hash_check = next(check for check in result.checks if check["name"] == "move-lab-transcript-payload-hash")
        self.assertEqual(payload_hash_check["status"], "pass")

    def test_move_lab_transcript_rejects_raw_url_and_body_fields(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
            root = Path(tmp)
            payload = write_payload(root)
            transcript = write_transcript(root, payload)
            data = json.loads(transcript.read_text(encoding="utf-8"))
            data["interactions"][0]["url"] = "https://move-lab.invalid/api/session"
            data["interactions"][0]["request_body"] = {"username": "operator"}
            transcript.write_text(json.dumps(data, indent=2), encoding="utf-8")

            result = validate_move_lab_transcript(transcript, payload, Path("examples/sample_move_submit_review.json"))

        self.assertFalse(result.ok)
        self.assertTrue(any("forbidden raw or secret-bearing fields" in error for error in result.errors))
        self.assertTrue(any("potential url leak" in error for error in result.errors))

    def test_move_lab_transcript_accepts_utf8_bom_json(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
            root = Path(tmp)
            payload = write_payload(root)
            transcript = write_transcript(root, payload)
            transcript.write_text(transcript.read_text(encoding="utf-8"), encoding="utf-8-sig")

            result = validate_move_lab_transcript(transcript, payload, Path("examples/sample_move_submit_review.json"))

        self.assertTrue(result.ok, result.errors)

    def test_cli_validate_move_lab_transcript_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root)
            transcript = write_transcript(root, payload)
            out = root / "move-lab-transcript-validation.json"

            with patch("sys.stdout"), patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
                code = main(
                    [
                        "validate-move-lab-transcript",
                        "--transcript",
                        str(transcript),
                        "--payload",
                        str(payload),
                        "--review",
                        "examples/sample_move_submit_review.json",
                        "--out",
                        str(out),
                        "--json",
                    ]
                )

            data = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(data["schema_version"], "nmrcp_move_lab_transcript_validation_v1")
        self.assertEqual(data["status"], "warn")

    def test_capture_kit_generates_template_and_checklist(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
            root = Path(tmp)
            payload = write_payload(root)
            out_dir = root / "capture-kit"

            kit = write_move_lab_capture_kit(payload, Path("examples/sample_move_submit_review.json"), out_dir)
            template = json.loads(kit.transcript_template_path.read_text(encoding="utf-8"))
            checklist = kit.checklist_path.read_text(encoding="utf-8")
            payload_sha256 = hashlib.sha256(payload.read_bytes()).hexdigest()

        self.assertEqual(template["schema_version"], "nmrcp_move_lab_transcript_v1")
        self.assertEqual(template["evidence_state"], "template_only_replace_after_lab_capture")
        self.assertEqual(template["payload_sha256"], payload_sha256)
        self.assertIn("Move Lab Capture Checklist", checklist)
        self.assertIn("validate-move-lab-transcript", checklist)
        self.assertIn("validate-move-lab-evidence-intake", checklist)

    def test_capture_template_does_not_validate_as_real_evidence(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
            root = Path(tmp)
            payload = write_payload(root)
            kit = write_move_lab_capture_kit(payload, Path("examples/sample_move_submit_review.json"), root / "capture-kit")

            result = validate_move_lab_transcript(kit.transcript_template_path, payload, Path("examples/sample_move_submit_review.json"))

        self.assertFalse(result.ok)
        self.assertTrue(any("template must be copied" in error for error in result.errors))

    def test_cli_generate_move_lab_capture_kit_writes_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root)
            out_dir = root / "capture-kit"

            with patch("sys.stdout"), patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
                code = main(
                    [
                        "generate-move-lab-capture-kit",
                        "--payload",
                        str(payload),
                        "--review",
                        "examples/sample_move_submit_review.json",
                        "--out-dir",
                        str(out_dir),
                        "--json",
                    ]
                )
            transcript_exists = (out_dir / "move-lab-transcript.template.json").exists()
            checklist_exists = (out_dir / "move-lab-capture-checklist.md").exists()

        self.assertEqual(code, 0)
        self.assertTrue(transcript_exists)
        self.assertTrue(checklist_exists)

    def test_capture_kit_validation_passes_for_generated_kit(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
            root = Path(tmp)
            payload = write_payload(root)
            kit = write_move_lab_capture_kit(payload, Path("examples/sample_move_submit_review.json"), root / "capture-kit")

            result = validate_move_lab_capture_kit(kit.out_dir, payload)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.status, "pass")
        self.assertTrue(any(check["name"] == "move-lab-capture-template-payload-hash" and check["status"] == "pass" for check in result.checks))

    def test_capture_kit_validation_rejects_mismatched_payload_hash(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
            root = Path(tmp)
            payload = write_payload(root)
            kit = write_move_lab_capture_kit(payload, Path("examples/sample_move_submit_review.json"), root / "capture-kit")
            template = json.loads(kit.transcript_template_path.read_text(encoding="utf-8"))
            template["payload_sha256"] = "0" * 64
            kit.transcript_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")

            result = validate_move_lab_capture_kit(kit.out_dir, payload)

        self.assertFalse(result.ok)
        self.assertTrue(any("payload_sha256 must match" in error for error in result.errors))

    def test_cli_validate_move_lab_capture_kit_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root)
            out_dir = root / "capture-kit"
            out = root / "capture-kit-validation.json"
            with patch("sys.stdout"), patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
                main(
                    [
                        "generate-move-lab-capture-kit",
                        "--payload",
                        str(payload),
                        "--review",
                        "examples/sample_move_submit_review.json",
                        "--out-dir",
                        str(out_dir),
                    ]
                )
                code = main(
                    [
                        "validate-move-lab-capture-kit",
                        "--kit-dir",
                        str(out_dir),
                        "--payload",
                        str(payload),
                        "--out",
                        str(out),
                        "--json",
                    ]
                )
            data = json.loads(out.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertEqual(data["schema_version"], "nmrcp_move_lab_capture_kit_validation_v1")
        self.assertEqual(data["status"], "pass")

    def test_capture_kit_validation_file_rejects_failed_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            proof = Path(tmp) / "move-lab-capture-kit-validation.json"
            proof.write_text(
                json.dumps(
                    {
                        "schema_version": "nmrcp_move_lab_capture_kit_validation_v1",
                        "status": "fail",
                        "checks": [],
                        "errors": ["capture kit failed"],
                        "warnings": [],
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

            result = validate_move_lab_capture_kit_validation_file(proof)

        self.assertFalse(result.ok)
        self.assertTrue(any("status must be pass" in error for error in result.errors))


def write_payload(root: Path) -> Path:
    path = root / "move-api-payload.lab.dry-run.json"
    path.write_text(
        json.dumps(
            {
                "contract": "nmrcp_move_api_payload_dry_run_v1",
                "dry_run_only": True,
                "mutation_allowed": False,
                "source_provider": {"uuid": "source-provider-lab"},
                "target_provider": {"uuid": "target-provider-lab"},
                "target_cluster": {"uuid": "cluster-lab"},
                "target_container": {"uuid": "container-lab"},
                "network_mappings": [{"source": "vlan-120", "target": "ahv-vlan-120"}],
                "schedule": {"start_immediately": False},
                "workloads": [{"source_vm_id": "vm-1", "source_vm_name": "web-01"}],
                "validation": {"network_mapping": "PASS: checked=1, mapped=1, errors=0, warnings=0"},
                "operator_notes": ["test fixture"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_transcript(root: Path, payload: Path) -> Path:
    path = root / "move-lab-transcript.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_transcript_v1",
                "proof_scope": "approved_lab_move_appliance",
                "environment": "lab",
                "lab_move_appliance": "move-lab-01",
                "payload_sha256": hashlib.sha256(payload.read_bytes()).hexdigest(),
                "dry_run_only": True,
                "mutation_performed": False,
                "production_targets": False,
                "interactions": [
                    {
                        "name": "create-reviewed-dry-run-plan",
                        "method": "POST",
                        "path": "/api/move/lab/dry-run-plans",
                        "status_code": 202,
                        "dry_run": True,
                        "mutating": False,
                        "redacted": True,
                    }
                ],
                "results": {
                    "accepted_payloads": 1,
                    "created_plans": 1,
                    "started_migrations": 0,
                },
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
