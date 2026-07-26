import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.move_lab_proof import validate_move_lab_proof, write_approved_move_lab_proof, write_move_lab_proof_template
from nmrcp.move_lab_transcript import validate_move_lab_transcript
from nmrcp.mvp_audit import audit_mvp


class MoveLabProofTests(unittest.TestCase):
    def test_simulated_move_lab_proof_passes_with_warning(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
            payload = write_payload(Path(tmp))
            result = validate_move_lab_proof(
                Path("examples/sample_move_lab_proof_simulated.json"),
                payload,
                Path("examples/sample_move_submit_review.json"),
            )

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.status, "warn")
        self.assertTrue(any("simulated_contract" in warning for warning in result.warnings))

    def test_move_lab_proof_rejects_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            proof = Path(tmp) / "move-lab-proof.json"
            move_payload = write_payload(Path(tmp))
            payload = json.loads(Path("examples/sample_move_lab_proof_simulated.json").read_text(encoding="utf-8"))
            payload["mutation_performed"] = True
            proof.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            with patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
                result = validate_move_lab_proof(
                    proof,
                    move_payload,
                    Path("examples/sample_move_submit_review.json"),
                )

        self.assertFalse(result.ok)
        self.assertTrue(any("mutation_performed=false" in error for error in result.errors))

    def test_move_lab_proof_rejects_secret_like_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            proof = Path(tmp) / "move-lab-proof.json"
            move_payload = write_payload(Path(tmp))
            payload = json.loads(Path("examples/sample_move_lab_proof_simulated.json").read_text(encoding="utf-8"))
            payload["debug"] = "token=not-for-proof"
            proof.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            with patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
                result = validate_move_lab_proof(
                    proof,
                    move_payload,
                    Path("examples/sample_move_submit_review.json"),
                )

        self.assertFalse(result.ok)
        self.assertTrue(any("potential secret-assignment leak" in error for error in result.errors))

    def test_cli_validate_move_lab_proof_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "move-lab-proof-validation.json"
            payload = write_payload(Path(tmp))
            with patch("sys.stdout"), patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
                code = main(
                    [
                        "validate-move-lab-proof",
                        "--proof",
                        "examples/sample_move_lab_proof_simulated.json",
                        "--payload",
                        str(payload),
                        "--review",
                        "examples/sample_move_submit_review.json",
                        "--out",
                        str(out),
                        "--json",
                    ]
                )

            payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(code, 0)
        self.assertEqual(payload["schema_version"], "nmrcp_move_lab_proof_validation_v1")
        self.assertEqual(payload["status"], "warn")

    def test_approved_move_lab_proof_requires_transcript_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root, include_operator_notes=False)
            proof = write_approved_proof(root)

            with patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
                result = validate_move_lab_proof(
                    proof,
                    payload,
                    Path("examples/sample_move_submit_review.json"),
                )

        self.assertFalse(result.ok)
        self.assertTrue(any("--transcript-validation" in error for error in result.errors))

    def test_approved_move_lab_proof_passes_with_linked_transcript_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root, include_operator_notes=False)
            transcript_validation = write_transcript_validation(root)
            proof = write_approved_proof(root, transcript_validation)

            with patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
                result = validate_move_lab_proof(
                    proof,
                    payload,
                    Path("examples/sample_move_submit_review.json"),
                    transcript_validation_path=transcript_validation,
                )

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.status, "pass")
        link_check = next(check for check in result.checks if check["name"] == "move-lab-transcript-validation-link")
        self.assertEqual(link_check["status"], "pass")

    def test_generate_move_lab_proof_template_drafts_approved_lab_scope(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root)
            proof = root / "move-lab-proof.json"

            write_move_lab_proof_template(
                payload,
                Path("examples/sample_move_submit_review.json"),
                proof,
                proof_scope="approved_lab_move_appliance",
            )

            data = json.loads(proof.read_text(encoding="utf-8"))
            self.assertEqual(data["schema_version"], "nmrcp_move_lab_proof_v1")
            self.assertEqual(data["proof_scope"], "approved_lab_move_appliance")
            self.assertEqual(data["results"]["payload_workloads"], 1)
            self.assertEqual(data["results"]["accepted_payloads"], 0)
            self.assertFalse(data["api_round_trip"])
            self.assertTrue(all(value is False for value in data["approvals"].values()))

    def test_cli_generate_move_lab_proof_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root)
            proof = root / "move-lab-proof.json"

            with patch("sys.stdout"):
                code = main(
                    [
                        "generate-move-lab-proof-template",
                        "--payload",
                        str(payload),
                        "--review",
                        "examples/sample_move_submit_review.json",
                        "--proof-scope",
                        "simulated_contract",
                        "--out",
                        str(proof),
                    ]
                )

            data = json.loads(proof.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(data["proof_scope"], "simulated_contract")
            self.assertEqual(data["results"]["payload_workloads"], 1)

    def test_generate_approved_move_lab_proof_links_clean_transcript_validation(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
            root = Path(tmp)
            payload = write_payload(root, include_operator_notes=False)
            transcript = write_clean_transcript(root, payload)
            transcript_validation = write_real_transcript_validation(root, transcript, payload)
            proof = root / "move-lab-proof.approved.json"

            write_approved_move_lab_proof(
                payload,
                Path("examples/sample_move_submit_review.json"),
                transcript,
                transcript_validation,
                proof,
                approved_by="Lab Migration Lead",
            )
            result = validate_move_lab_proof(
                proof,
                payload,
                Path("examples/sample_move_submit_review.json"),
                transcript_validation_path=transcript_validation,
            )

            data = json.loads(proof.read_text(encoding="utf-8"))
            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.status, "pass")
            self.assertEqual(data["proof_scope"], "approved_lab_move_appliance")
            self.assertEqual(data["transcript_validation_sha256"], hashlib.sha256(transcript_validation.read_bytes()).hexdigest())
            self.assertTrue(all(data["approvals"].values()))

    def test_generate_approved_move_lab_proof_rejects_transcript_warnings(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
            root = Path(tmp)
            payload = write_payload(root, include_operator_notes=False)
            transcript = write_clean_transcript(root, payload, include_hashes=False)
            transcript_validation = write_real_transcript_validation(root, transcript, payload)

            with self.assertRaises(ValueError) as error:
                write_approved_move_lab_proof(
                    payload,
                    Path("examples/sample_move_submit_review.json"),
                    transcript,
                    transcript_validation,
                    root / "move-lab-proof.approved.json",
                    approved_by="Lab Migration Lead",
                )

        self.assertIn("warnings must be resolved", str(error.exception))

    def test_cli_generate_approved_move_lab_proof(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"}):
            root = Path(tmp)
            payload = write_payload(root, include_operator_notes=False)
            transcript = write_clean_transcript(root, payload)
            transcript_validation = write_real_transcript_validation(root, transcript, payload)
            proof = root / "move-lab-proof.approved.json"

            with patch("sys.stdout"):
                code = main(
                    [
                        "generate-approved-move-lab-proof",
                        "--payload",
                        str(payload),
                        "--review",
                        "examples/sample_move_submit_review.json",
                        "--transcript",
                        str(transcript),
                        "--transcript-validation",
                        str(transcript_validation),
                        "--approved-by",
                        "Lab Migration Lead",
                        "--out",
                        str(proof),
                    ]
                )

            data = json.loads(proof.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(data["proof_scope"], "approved_lab_move_appliance")
            self.assertEqual(data["results"]["accepted_payloads"], 1)

    def test_mvp_audit_requires_approved_lab_move_proof_to_clear_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            simulated = Path(tmp) / "simulated-validation.json"
            approved = Path(tmp) / "approved-validation.json"
            simulated.write_text(
                json.dumps(
                    {
                        "schema_version": "nmrcp_move_lab_proof_validation_v1",
                        "status": "pass",
                        "checks": [{"name": "move-lab-proof-scope", "status": "pass", "detail": "simulated_contract"}],
                        "errors": [],
                        "warnings": [],
                    }
                ),
                encoding="utf-8",
            )
            approved.write_text(
                json.dumps(
                    {
                        "schema_version": "nmrcp_move_lab_proof_validation_v1",
                        "status": "pass",
                        "checks": [
                            {"name": "move-lab-proof-scope", "status": "pass", "detail": "approved_lab_move_appliance"},
                            {"name": "move-lab-transcript-validation-link", "status": "pass", "detail": "sha256 matched"},
                        ],
                        "errors": [],
                        "warnings": [],
                    }
                ),
                encoding="utf-8",
            )

            simulated_result = audit_mvp(Path.cwd(), move_proof_path=simulated)
            approved_result = audit_mvp(Path.cwd(), move_proof_path=approved)

        simulated_move = next(requirement for requirement in simulated_result.requirements if requirement.id == "move_ready_plan")
        approved_move = next(requirement for requirement in approved_result.requirements if requirement.id == "move_ready_plan")
        self.assertEqual(simulated_result.status, "fail")
        self.assertTrue(any("approved_lab_move_appliance" in error for error in simulated_move.errors))
        self.assertEqual(approved_move.status, "pass")


def write_payload(root: Path, *, include_operator_notes: bool = True) -> Path:
    path = root / "move-api-payload.lab.dry-run.json"
    payload = {
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
    }
    if include_operator_notes:
        payload["operator_notes"] = ["test fixture"]
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_transcript_validation(root: Path) -> Path:
    path = root / "move-lab-transcript-validation.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_transcript_validation_v1",
                "status": "pass",
                "checks": [{"name": "move-lab-transcript-scope", "status": "pass", "detail": "approved_lab_move_appliance"}],
                "errors": [],
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_clean_transcript(root: Path, payload_path: Path, *, include_hashes: bool = True) -> Path:
    path = root / "move-lab-transcript.approved.json"
    interaction = {
        "name": "create-reviewed-dry-run-plan",
        "method": "POST",
        "path": "/api/move/lab/dry-run-plans",
        "status_code": 202,
        "dry_run": True,
        "mutating": False,
        "redacted": True,
    }
    if include_hashes:
        interaction["request_sha256"] = "a" * 64
        interaction["response_sha256"] = "b" * 64
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_transcript_v1",
                "proof_scope": "approved_lab_move_appliance",
                "evidence_state": "captured_approved_lab",
                "environment": "lab",
                "lab_move_appliance": "move-lab-01",
                "payload_sha256": hashlib.sha256(payload_path.read_bytes()).hexdigest(),
                "dry_run_only": True,
                "mutation_performed": False,
                "production_targets": False,
                "interactions": [interaction],
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


def write_real_transcript_validation(root: Path, transcript: Path, payload: Path) -> Path:
    path = root / "move-lab-transcript-validation.json"
    result = validate_move_lab_transcript(transcript, payload, Path("examples/sample_move_submit_review.json"))
    path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    return path


def write_approved_proof(root: Path, transcript_validation: Path | None = None) -> Path:
    path = root / "move-lab-proof.approved.json"
    transcript_hash = hashlib.sha256(transcript_validation.read_bytes()).hexdigest() if transcript_validation else ""
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_proof_v1",
                "proof_scope": "approved_lab_move_appliance",
                "environment": "lab",
                "reviewed_by": "Lab Migration Lead",
                "reviewed_at": "2026-07-24T12:00:00+00:00",
                "lab_move_appliance": "move-lab-01",
                "api_round_trip": True,
                "dry_run_only": True,
                "mutation_performed": False,
                "production_targets": False,
                "transcript_validation_sha256": transcript_hash,
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
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
