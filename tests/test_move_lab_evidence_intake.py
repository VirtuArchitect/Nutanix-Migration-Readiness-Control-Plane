import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.move_lab_evidence_intake import validate_move_lab_evidence_intake, validate_move_lab_evidence_preflight
from nmrcp.move_lab_proof import validate_move_lab_proof
from nmrcp.move_lab_transcript import validate_move_lab_transcript


class MoveLabEvidenceIntakeTests(unittest.TestCase):
    def test_approved_lab_evidence_intake_passes(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "os.environ",
            {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"},
        ):
            paths = write_approved_evidence_set(Path(tmp))

            result = validate_move_lab_evidence_intake(**paths)

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.status, "pass")

    def test_approved_lab_evidence_intake_rejects_simulated_proof(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "os.environ",
            {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"},
        ):
            paths = write_approved_evidence_set(Path(tmp), proof_scope="simulated_contract")

            result = validate_move_lab_evidence_intake(**paths)

            self.assertFalse(result.ok)
            self.assertTrue(any("simulated_contract" in error for error in result.errors))

    def test_cli_writes_intake_json(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "os.environ",
            {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"},
        ):
            root = Path(tmp)
            paths = write_approved_evidence_set(root)
            out = root / "move-lab-evidence-intake.json"

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-move-lab-evidence-intake",
                        "--payload",
                        str(paths["payload_path"]),
                        "--review",
                        str(paths["review_path"]),
                        "--transcript",
                        str(paths["transcript_path"]),
                        "--transcript-validation",
                        str(paths["transcript_validation_path"]),
                        "--proof",
                        str(paths["proof_path"]),
                        "--proof-validation",
                        str(paths["proof_validation_path"]),
                        "--capture-kit-validation",
                        str(paths["capture_kit_validation_path"]),
                        "--out",
                        str(out),
                        "--json",
                    ]
                )

            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(payload["schema_version"], "nmrcp_move_lab_evidence_intake_v1")
            self.assertEqual(payload["status"], "pass")

    def test_move_lab_evidence_preflight_accepts_ready_capture_setup(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "os.environ",
            {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"},
        ):
            root = Path(tmp)
            paths = write_approved_evidence_set(root)
            evidence_intake = root / "move-lab-evidence-intake.json"

            result = validate_move_lab_evidence_preflight(
                paths["payload_path"],
                paths["review_path"],
                paths["capture_kit_validation_path"],
                paths["transcript_path"],
                paths["transcript_validation_path"],
                paths["proof_path"],
                paths["proof_validation_path"],
                evidence_intake,
            )

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.status, "pass")
            self.assertTrue(any(command.startswith("python -m nmrcp.cli validate-move-lab-evidence-intake") for command in result.commands))
            self.assertIn("# Move Lab Evidence Preflight", result.to_markdown())

    def test_move_lab_evidence_preflight_rejects_template_transcript_path(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "os.environ",
            {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"},
        ):
            root = Path(tmp)
            paths = write_approved_evidence_set(root)

            result = validate_move_lab_evidence_preflight(
                paths["payload_path"],
                paths["review_path"],
                paths["capture_kit_validation_path"],
                root / "move-lab-transcript.template.json",
                paths["transcript_validation_path"],
                paths["proof_path"],
                paths["proof_validation_path"],
                root / "move-lab-evidence-intake.json",
            )

            self.assertFalse(result.ok)
            self.assertTrue(any("not the template" in error for error in result.errors))

    def test_cli_move_lab_evidence_preflight_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "os.environ",
            {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"},
        ):
            root = Path(tmp)
            paths = write_approved_evidence_set(root)
            out = root / "move-lab-evidence-preflight.json"
            report = root / "move-lab-evidence-preflight.md"

            with patch("sys.stdout"):
                code = main(
                    [
                        "move-lab-evidence-preflight",
                        "--payload",
                        str(paths["payload_path"]),
                        "--review",
                        str(paths["review_path"]),
                        "--capture-kit-validation",
                        str(paths["capture_kit_validation_path"]),
                        "--transcript",
                        str(paths["transcript_path"]),
                        "--transcript-validation",
                        str(paths["transcript_validation_path"]),
                        "--proof",
                        str(paths["proof_path"]),
                        "--proof-validation",
                        str(paths["proof_validation_path"]),
                        "--evidence-intake",
                        str(root / "move-lab-evidence-intake.json"),
                        "--out",
                        str(out),
                        "--report",
                        str(report),
                    ]
                )

            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(payload["schema_version"], "nmrcp_move_lab_evidence_preflight_v1")
            self.assertEqual(payload["status"], "pass")
            self.assertIn("validate-move-lab-evidence-intake", report.read_text(encoding="utf-8"))


def write_approved_evidence_set(root: Path, *, proof_scope: str = "approved_lab_move_appliance") -> dict[str, Path]:
    payload_path = root / "move-api-payload.lab.dry-run.json"
    review_path = root / "move-submit-review.json"
    transcript_path = root / "move-lab-transcript.approved.json"
    transcript_validation_path = root / "move-lab-transcript-validation.json"
    proof_path = root / "move-lab-proof.approved.json"
    proof_validation_path = root / "move-lab-proof-validation.json"
    capture_kit_validation_path = root / "move-lab-capture-kit-validation.json"

    payload = {
        "contract": "nmrcp_move_api_payload_dry_run_v1",
        "dry_run_only": True,
        "mutation_allowed": False,
        "source_provider": {"type": "vcenter", "id": "source-provider-1"},
        "target_provider": {"type": "prism", "id": "target-provider-1"},
        "target_cluster": {"id": "cluster-1"},
        "target_container": {"id": "container-1"},
        "schedule": {"start_immediately": False},
        "validation": {"network_mapping": "PASS: checked=1, mapped=1, errors=0, warnings=0"},
        "workloads": [{"id": "vm-1001", "name": "app-01"}],
    }
    payload_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    review = {
        "schema_version": "nmrcp_move_submit_review_v1",
        "environment": "lab",
        "reviewed_by": "Migration Lead",
        "reviewed_at": "2026-07-25T00:00:00Z",
        "lab_move_appliance": "move-lab-01.example.test",
        "approvals": {
            "payload_reviewed": True,
            "network_mapping_reviewed": True,
            "rollback_reviewed": True,
            "no_production_submit": True,
        },
    }
    review_path.write_text(json.dumps(review, indent=2), encoding="utf-8")

    transcript = {
        "schema_version": "nmrcp_move_lab_transcript_v1",
        "proof_scope": "approved_lab_move_appliance",
        "evidence_state": "captured_approved_lab",
        "environment": "lab",
        "lab_move_appliance": "move-lab-01.example.test",
        "payload_sha256": sha256_file(payload_path),
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
                "request_sha256": "a" * 64,
                "response_sha256": "b" * 64,
            }
        ],
        "results": {
            "accepted_payloads": 1,
            "created_plans": 1,
            "started_migrations": 0,
        },
    }
    transcript_path.write_text(json.dumps(transcript, indent=2), encoding="utf-8")
    transcript_validation = validate_move_lab_transcript(transcript_path, payload_path, review_path)
    transcript_validation_path.write_text(json.dumps(transcript_validation.to_dict(), indent=2), encoding="utf-8")

    proof = {
        "schema_version": "nmrcp_move_lab_proof_v1",
        "proof_scope": proof_scope,
        "environment": "lab",
        "reviewed_by": "Migration Lead",
        "reviewed_at": "2026-07-25T00:00:00Z",
        "lab_move_appliance": "move-lab-01.example.test",
        "api_round_trip": True,
        "dry_run_only": True,
        "mutation_performed": False,
        "production_targets": False,
        "transcript_validation_sha256": sha256_file(transcript_validation_path),
        "results": {
            "payload_workloads": 1,
            "accepted_payloads": 1,
            "created_plans": 1,
            "started_migrations": 0,
        },
        "approvals": {
            "change_window_reviewed": True,
            "rollback_reviewed": True,
            "operator_present": True,
            "no_production_targets": True,
            "credentials_not_persisted": True,
        },
        "notes": "Approved lab dry-run evidence; no production targets or started migrations.",
    }
    proof_path.write_text(json.dumps(proof, indent=2), encoding="utf-8")
    proof_validation = validate_move_lab_proof(
        proof_path,
        payload_path,
        review_path,
        transcript_validation_path=transcript_validation_path,
    )
    proof_validation_path.write_text(json.dumps(proof_validation.to_dict(), indent=2), encoding="utf-8")

    capture_kit_validation_path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_capture_kit_validation_v1",
                "status": "pass",
                "checks": [
                    {
                        "name": "move-lab-capture-template-payload-hash",
                        "status": "pass",
                        "detail": "sha256 matched",
                    },
                    {
                        "name": "move-lab-capture-attestation-payload-hash",
                        "status": "pass",
                        "detail": "sha256 matched",
                    },
                    {
                        "name": "move-lab-capture-template-state",
                        "status": "pass",
                        "detail": "template_only_replace_after_lab_capture",
                    },
                    {
                        "name": "move-lab-capture-checklist-text-validate-move-lab-evidence-intake",
                        "status": "pass",
                        "detail": "validate-move-lab-evidence-intake",
                    },
                ],
                "errors": [],
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return {
        "payload_path": payload_path,
        "review_path": review_path,
        "transcript_path": transcript_path,
        "transcript_validation_path": transcript_validation_path,
        "proof_path": proof_path,
        "proof_validation_path": proof_validation_path,
        "capture_kit_validation_path": capture_kit_validation_path,
    }


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    unittest.main()
