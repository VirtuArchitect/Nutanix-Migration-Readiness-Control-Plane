import json
import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.external_proof_plan import build_external_proof_plan
from nmrcp.mvp_proof_bundle import (
    build_mvp_closure_report,
    package_mvp_proof,
    summarize_mvp_proof_package,
    validate_mvp_closure_report,
    validate_mvp_proof_summary,
    verify_mvp_proof_package,
    write_mvp_closure_report,
    write_mvp_proof_summary,
)
from nmrcp.move_lab_closure_checklist import write_move_lab_closure_checklist
from nmrcp.move_lab_evidence_request import write_move_lab_evidence_request
from nmrcp.source_endpoint_evidence_request import write_source_endpoint_evidence_request
from nmrcp.source_collection_plan import write_source_collection_plan
from tests.test_source_collection_plan import write_completed_intake


class MvpProofBundleTests(unittest.TestCase):
    def test_package_mvp_proof_includes_hash_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            live = write_json(root / "live-proof.json", live_endpoint_proof())
            transcript = write_json(
                root / "move-lab-transcript.json",
                {"schema_version": "nmrcp_move_lab_transcript_validation_v1", "status": "warn", "errors": [], "warnings": []},
            )
            move = write_json(
                root / "move-proof.json",
                {"schema_version": "nmrcp_move_lab_proof_validation_v1", "status": "warn", "errors": [], "warnings": []},
            )
            runbook = write_valid_runbook(root / "move-lab-runbook.md")
            closure_checklist = write_move_lab_closure_checklist(root / "move-lab-closure-checklist.md")
            capture_kit = write_capture_kit(root)
            capture_validation = write_json(root / "move-lab-capture-kit-validation.json", capture_kit_validation("pass"))
            readiness_packet = write_json(root / "move-lab-readiness-packet.json", readiness_packet_payload("warn"))
            intake = write_json(root / "move-lab-evidence-intake.json", evidence_intake("pass"))
            source_request = write_source_endpoint_evidence_request([], root / "source-endpoint-evidence-request.md")
            source_intake = write_completed_intake(root / "assessment-intake.csv")
            source_plan = root / "source-collection-plan.md"
            self.assertTrue(write_source_collection_plan(source_intake, source_plan).ok)
            move_request = write_move_lab_evidence_request([], [], root / "move-lab-evidence-request.md")
            external_plan = write_json(root / "external-proof-plan.json", build_external_proof_plan(root).to_dict())
            package = root / "mvp-proof.zip"

            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                live_proof_path=live,
                move_lab_transcript_path=transcript,
                move_lab_proof_path=move,
                move_lab_runbook_path=runbook,
                move_lab_closure_checklist_path=closure_checklist,
                move_lab_capture_kit_dir=capture_kit,
                move_lab_capture_validation_path=capture_validation,
                move_lab_readiness_packet_path=readiness_packet,
                move_lab_evidence_intake_path=intake,
                source_collection_plan_path=source_plan,
                source_endpoint_evidence_request_path=source_request,
                move_lab_evidence_request_path=move_request,
                external_proof_plan_path=external_plan,
            )
            result = verify_mvp_proof_package(package)

            self.assertTrue(result.ok, result.errors)
            with zipfile.ZipFile(package, "r") as archive:
                names = set(archive.namelist())
                manifest = json.loads(archive.read("mvp-proof-manifest.json").decode("utf-8"))
            self.assertIn("proof/mvp-audit.json", names)
            self.assertIn("proof/live-proof-validation.json", names)
            self.assertIn("proof/move-lab-transcript-validation.json", names)
            self.assertIn("proof/move-lab-proof-validation.json", names)
            self.assertIn("proof/move-lab-execution-runbook.md", names)
            self.assertIn("proof/move-lab-closure-checklist.md", names)
            self.assertIn("proof/move-lab-transcript.template.json", names)
            self.assertIn("proof/move-lab-capture-checklist.md", names)
            self.assertIn("proof/move-lab-capture-kit-validation.json", names)
            self.assertIn("proof/move-lab-readiness-packet.json", names)
            self.assertIn("proof/move-lab-evidence-intake.json", names)
            self.assertIn("proof/source-collection-plan.md", names)
            self.assertIn("proof/source-endpoint-evidence-request.md", names)
            self.assertIn("proof/move-lab-evidence-request.md", names)
            self.assertIn("proof/external-proof-plan.json", names)
            self.assertEqual(manifest["schema_version"], "nmrcp_mvp_proof_manifest_v1")
            self.assertFalse(any("source_path" in entry for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_runbook" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_closure_checklist" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_capture_template" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_capture_checklist" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_capture_validation" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_readiness_packet" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_evidence_intake" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "source_collection_plan" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "source_endpoint_evidence_request" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_evidence_request" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "external_proof_plan" for entry in manifest["files"]))
            self.assertIn("move_lab_transcript", result.roles)
            self.assertIn("move_lab_runbook", result.roles)
            self.assertIn("move_lab_closure_checklist", result.roles)
            self.assertIn("move_lab_capture_template", result.roles)
            self.assertIn("move_lab_capture_checklist", result.roles)
            self.assertIn("move_lab_capture_validation", result.roles)
            self.assertIn("move_lab_readiness_packet", result.roles)
            self.assertIn("move_lab_evidence_intake", result.roles)
            self.assertIn("source_collection_plan", result.roles)
            self.assertIn("source_endpoint_evidence_request", result.roles)
            self.assertIn("move_lab_evidence_request", result.roles)
            self.assertIn("external_proof_plan", result.roles)

    def test_verify_mvp_proof_rejects_packaged_source_collection_plan_with_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            source_intake = write_completed_intake(root / "assessment-intake.csv")
            source_plan = root / "source-collection-plan.md"
            write_source_collection_plan(source_intake, source_plan)
            source_plan.write_text(
                source_plan.read_text(encoding="utf-8") + "\nLeaked endpoint: https://vcenter01.corp.local/sdk\n",
                encoding="utf-8",
            )
            package = root / "mvp-proof.zip"

            package_mvp_proof(package, mvp_audit_path=audit, source_collection_plan_path=source_plan)
            result = verify_mvp_proof_package(package)

        self.assertFalse(result.ok)
        self.assertTrue(any("source-collection-plan.md" in error and "endpoint or secret-like material" in error for error in result.errors))

    def test_verify_mvp_proof_rejects_external_proof_plan_without_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            payload = build_external_proof_plan(root).to_dict()
            payload["operator_boundaries"] = ["ready for handoff"]
            plan = write_json(root / "external-proof-plan.json", payload)
            package = root / "mvp-proof.zip"
            package_mvp_proof(package, mvp_audit_path=audit, external_proof_plan_path=plan)

            result = verify_mvp_proof_package(package)

        self.assertFalse(result.ok)
        self.assertTrue(any("Do not claim external handoff readiness" in error for error in result.errors))

    def test_package_mvp_proof_rejects_failed_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("fail"))

            with self.assertRaises(ValueError) as failure:
                package_mvp_proof(root / "mvp-proof.zip", mvp_audit_path=audit)

            self.assertIn("status must not be fail", str(failure.exception))

    def test_verify_mvp_proof_detects_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            broken = root / "broken.zip"
            package_mvp_proof(package, mvp_audit_path=audit)

            with zipfile.ZipFile(package, "r") as source, zipfile.ZipFile(broken, "w") as target:
                for name in source.namelist():
                    if name != "proof/mvp-audit.json":
                        target.writestr(name, source.read(name))

            result = verify_mvp_proof_package(broken)

            self.assertFalse(result.ok)
            self.assertTrue(any("proof/mvp-audit.json" in error for error in result.errors))

    def test_verify_mvp_proof_detects_missing_required_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            broken = root / "broken.zip"
            package_mvp_proof(package, mvp_audit_path=audit)

            with zipfile.ZipFile(package, "r") as source:
                manifest = json.loads(source.read("mvp-proof-manifest.json").decode("utf-8"))
                manifest["files"] = []
                with zipfile.ZipFile(broken, "w") as target:
                    for name in source.namelist():
                        if name == "mvp-proof-manifest.json":
                            target.writestr(name, json.dumps(manifest, indent=2))
                        else:
                            target.writestr(name, source.read(name))

            result = verify_mvp_proof_package(broken)

        self.assertFalse(result.ok)
        self.assertTrue(any("missing required MVP proof role: mvp_audit" in error for error in result.errors))

    def test_verify_mvp_proof_rejects_stale_move_lab_runbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            runbook = write_valid_runbook(root / "move-lab-runbook.md")
            text = runbook.read_text(encoding="utf-8").replace("validate-move-lab-evidence-intake", "validate-move-lab-proof")
            runbook.write_text(text, encoding="utf-8")
            package = root / "mvp-proof.zip"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                move_lab_runbook_path=runbook,
            )

            result = verify_mvp_proof_package(package)

        self.assertFalse(result.ok)
        self.assertTrue(any("validate-move-lab-evidence-intake" in error for error in result.errors))

    def test_verify_mvp_proof_rejects_unsupported_or_duplicate_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            broken = root / "broken.zip"
            package_mvp_proof(package, mvp_audit_path=audit)

            with zipfile.ZipFile(package, "r") as source:
                manifest = json.loads(source.read("mvp-proof-manifest.json").decode("utf-8"))
                first = dict(manifest["files"][0])
                manifest["files"].append({**first, "role": "unexpected_role", "path": "proof/unexpected.json"})
                manifest["files"].append(dict(first))
                with zipfile.ZipFile(broken, "w") as target:
                    for name in source.namelist():
                        if name == "mvp-proof-manifest.json":
                            target.writestr(name, json.dumps(manifest, indent=2))
                        else:
                            target.writestr(name, source.read(name))
                    target.writestr("proof/unexpected.json", b"unexpected")

            result = verify_mvp_proof_package(broken)

        self.assertFalse(result.ok)
        self.assertTrue(any("unsupported manifest role" in error for error in result.errors))
        self.assertTrue(any("duplicate manifest role mvp_audit" in error for error in result.errors))

    def test_verify_mvp_proof_rejects_wrong_role_schema_even_when_hash_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            live = write_json(root / "live-proof.json", {"schema_version": "wrong_schema", "status": "pass"})
            package = root / "mvp-proof.zip"
            package_mvp_proof(package, mvp_audit_path=audit, live_proof_path=live)

            result = verify_mvp_proof_package(package)

        self.assertFalse(result.ok)
        self.assertTrue(any("schema_version must be nmrcp_live_endpoint_proof_v1" in error for error in result.errors))

    def test_verify_mvp_proof_rejects_stale_live_endpoint_proof_without_intake_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            live = write_json(root / "live-proof.json", {"schema_version": "nmrcp_live_endpoint_proof_v1", "status": "pass"})
            package = root / "mvp-proof.zip"
            package_mvp_proof(package, mvp_audit_path=audit, live_proof_path=live)

            result = verify_mvp_proof_package(package)

        self.assertFalse(result.ok)
        self.assertTrue(any("collection-summary-assessment-intake" in error for error in result.errors))

    def test_verify_mvp_proof_rejects_capture_template_not_marked_template_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            capture_kit = write_capture_kit(root, evidence_state="captured_approved_lab")
            capture_validation = write_json(root / "move-lab-capture-kit-validation.json", capture_kit_validation("pass"))
            package = root / "mvp-proof.zip"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                move_lab_capture_kit_dir=capture_kit,
                move_lab_capture_validation_path=capture_validation,
            )

            result = verify_mvp_proof_package(package)

        self.assertFalse(result.ok)
        self.assertTrue(any("must remain template_only_replace_after_lab_capture" in error for error in result.errors))

    def test_verify_mvp_proof_rejects_failed_capture_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            capture_kit = write_capture_kit(root)
            capture_validation = write_json(root / "move-lab-capture-kit-validation.json", capture_kit_validation("fail"))
            package = root / "mvp-proof.zip"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                move_lab_capture_kit_dir=capture_kit,
                move_lab_capture_validation_path=capture_validation,
            )

            result = verify_mvp_proof_package(package)

        self.assertFalse(result.ok)
        self.assertTrue(any("status must be one of pass" in error for error in result.errors))

    def test_verify_mvp_proof_requires_capture_kit_roles_as_pair(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            capture_kit = write_capture_kit(root)
            capture_validation = write_json(root / "move-lab-capture-kit-validation.json", capture_kit_validation("pass"))
            readiness_packet = write_json(root / "move-lab-readiness-packet.json", readiness_packet_payload("pass"))
            intake = write_json(root / "move-lab-evidence-intake.json", evidence_intake("pass"))
            package = root / "mvp-proof.zip"
            broken = root / "broken.zip"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                move_lab_capture_kit_dir=capture_kit,
                move_lab_capture_validation_path=capture_validation,
            )

            with zipfile.ZipFile(package, "r") as source:
                manifest = json.loads(source.read("mvp-proof-manifest.json").decode("utf-8"))
                manifest["files"] = [
                    entry for entry in manifest["files"] if entry.get("role") != "move_lab_capture_checklist"
                ]
                with zipfile.ZipFile(broken, "w") as target:
                    for name in source.namelist():
                        if name == "mvp-proof-manifest.json":
                            target.writestr(name, json.dumps(manifest, indent=2))
                        else:
                            target.writestr(name, source.read(name))

            result = verify_mvp_proof_package(broken)

        self.assertFalse(result.ok)
        self.assertTrue(any("capture kit roles must be packaged together" in error for error in result.errors))

    def test_verify_mvp_proof_requires_capture_kit_and_validation_as_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            capture_kit = write_capture_kit(root)
            package = root / "mvp-proof.zip"
            package_mvp_proof(package, mvp_audit_path=audit, move_lab_capture_kit_dir=capture_kit)

            result = verify_mvp_proof_package(package)

        self.assertFalse(result.ok)
        self.assertTrue(any("capture kit and validation proof must be packaged together" in error for error in result.errors))

    def test_verify_mvp_proof_rejects_invalid_closure_checklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            closure_checklist = write_text(root / "move-lab-closure-checklist.md", "# Move Lab Closure Checklist\n")
            package = root / "mvp-proof.zip"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                move_lab_closure_checklist_path=closure_checklist,
            )

            result = verify_mvp_proof_package(package)

        self.assertFalse(result.ok)
        self.assertTrue(any("missing required section" in error for error in result.errors))

    def test_verify_mvp_proof_rejects_tampered_packaged_evidence_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            source_request = write_text(root / "source-endpoint-evidence-request.md", "# Source Endpoint Evidence Request\n")
            package = root / "mvp-proof.zip"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                source_endpoint_evidence_request_path=source_request,
            )

            result = verify_mvp_proof_package(package)

        self.assertFalse(result.ok)
        self.assertTrue(any("source-endpoint-evidence-request.md" in error and "missing required section" in error for error in result.errors))

    def test_cli_package_and_verify_mvp_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            with patch("sys.stdout"):
                package_code = main(["package-mvp-proof", "--mvp-audit", str(audit), "--out", str(package)])
                verify_code = main(["verify-mvp-proof", "--package", str(package)])

            self.assertEqual(package_code, 0)
            self.assertEqual(verify_code, 0)

    def test_summarize_mvp_proof_reports_partial_move_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            move = write_json(
                root / "move-proof.json",
                {
                    "schema_version": "nmrcp_move_lab_proof_validation_v1",
                    "status": "warn",
                    "checks": [{"name": "move-lab-proof-scope", "status": "pass", "detail": "simulated_contract"}],
                    "errors": [],
                    "warnings": ["Move lab proof is simulated_contract; real lab Move appliance behavior remains unproven"],
                },
            )
            transcript = write_json(
                root / "move-lab-transcript.json",
                {"schema_version": "nmrcp_move_lab_transcript_validation_v1", "status": "warn", "errors": [], "warnings": []},
            )
            runbook = write_valid_runbook(root / "move-lab-runbook.md")
            closure_checklist = write_move_lab_closure_checklist(root / "move-lab-closure-checklist.md")
            capture_kit = write_capture_kit(root)
            capture_validation = write_json(root / "move-lab-capture-kit-validation.json", capture_kit_validation("pass"))
            source_request = write_source_endpoint_evidence_request([], root / "source-endpoint-evidence-request.md")
            move_request = write_move_lab_evidence_request([], [], root / "move-lab-evidence-request.md")
            package = root / "mvp-proof.zip"
            out = root / "mvp-proof-summary.md"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                move_lab_transcript_path=transcript,
                move_lab_proof_path=move,
                move_lab_runbook_path=runbook,
                move_lab_closure_checklist_path=closure_checklist,
                move_lab_capture_kit_dir=capture_kit,
                move_lab_capture_validation_path=capture_validation,
                source_endpoint_evidence_request_path=source_request,
                move_lab_evidence_request_path=move_request,
            )

            summary = write_mvp_proof_summary(package, out)
            direct = summarize_mvp_proof_package(package)
            text = out.read_text(encoding="utf-8")

        self.assertTrue(summary.verification.ok, summary.verification.errors)
        self.assertEqual(summary.move_lab_scope, "simulated_contract")
        self.assertEqual(summary.move_lab_transcript_status, "warn")
        self.assertEqual(direct.move_lab_status, "warn")
        self.assertTrue(summary.has_closure_checklist)
        self.assertTrue(summary.has_capture_kit)
        self.assertEqual(summary.move_lab_capture_validation_status, "pass")
        self.assertEqual(summary.move_lab_evidence_intake_status, "missing")
        self.assertTrue(summary.has_source_endpoint_evidence_request)
        self.assertTrue(summary.has_move_lab_evidence_request)
        self.assertEqual(summary.handoff_verification_status, "missing")
        self.assertEqual(summary.handoff_roles, ())
        self.assertIn("Real approved Nutanix Move appliance proof remains unproven", text)
        self.assertIn("Move lab transcript", text)
        self.assertIn("Move lab closure checklist", text)
        self.assertIn("Move lab capture kit", text)
        self.assertIn("Move lab capture validation", text)
        self.assertIn("Move lab evidence intake", text)
        self.assertIn("Source endpoint evidence request", text)
        self.assertIn("Move lab evidence request", text)
        self.assertIn("move_lab_runbook", text)
        self.assertIn("move_lab_closure_checklist", text)

    def test_summary_lists_nested_handoff_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            handoff = write_zip(root / "handoff.zip")
            package = root / "mvp-proof.zip"
            out = root / "mvp-proof-summary.md"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                handoff_package_path=handoff,
            )

            summary = write_mvp_proof_summary(package, out)
            text = out.read_text(encoding="utf-8")
            payload = summary.to_dict()

        self.assertEqual(summary.handoff_verification_status, "verified")
        self.assertIn("move_lab_readiness_packet", summary.handoff_roles)
        self.assertEqual(summary.handoff_role_counts["move_lab_readiness_packet"], 1)
        self.assertEqual(summary.handoff_role_counts["assessment_artifact"], 6)
        self.assertEqual(payload["proof_status"]["handoff_move_lab_readiness_packet"], "present")
        self.assertEqual(payload["handoff_role_counts"]["move_lab_readiness_packet"], 1)
        self.assertIn("## Handoff Package Roles", text)
        self.assertIn("| `move_lab_readiness_packet` | `1` |", text)
        self.assertIn("| `assessment_artifact` | `6` |", text)

    def test_mvp_closure_report_requires_intake_for_approved_move_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("pass"))
            live = write_json(root / "live-proof.json", live_endpoint_proof())
            submit = write_json(root / "move-submit.json", {"schema_version": "nmrcp_move_submit_readiness_v1", "status": "pass", "errors": []})
            transcript = write_json(
                root / "move-lab-transcript.json",
                {"schema_version": "nmrcp_move_lab_transcript_validation_v1", "status": "pass", "errors": [], "warnings": []},
            )
            move = write_json(root / "move-proof.json", approved_move_proof_validation())
            runbook = write_valid_runbook(root / "move-lab-runbook.md")
            capture_kit = write_capture_kit(root)
            capture_validation = write_json(root / "move-lab-capture-kit-validation.json", capture_kit_validation("pass"))
            operator_summary = write_valid_operator_gate_summary(root / "operator-gate-summary.md")
            source_request = write_source_endpoint_evidence_request([], root / "source-endpoint-evidence-request.md")
            source_intake = write_completed_intake(root / "assessment-intake.csv")
            source_plan = root / "source-collection-plan.md"
            self.assertTrue(write_source_collection_plan(source_intake, source_plan).ok)
            move_request = write_move_lab_evidence_request([], [], root / "move-lab-evidence-request.md")
            external_plan_payload = build_external_proof_plan(root).to_dict()
            external_plan_payload["status"] = "ready_for_external_handoff"
            for step in external_plan_payload["steps"]:
                step["status"] = "pass"
                step["current_gap"] = "closed by supplied proof"
            external_plan = write_json(root / "external-proof-plan.json", external_plan_payload)
            handoff = write_zip(root / "handoff.zip")
            package = root / "mvp-proof.zip"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                live_proof_path=live,
                move_submit_readiness_path=submit,
                move_lab_transcript_path=transcript,
                move_lab_proof_path=move,
                move_lab_runbook_path=runbook,
                move_lab_capture_kit_dir=capture_kit,
                move_lab_capture_validation_path=capture_validation,
                operator_gate_summary_path=operator_summary,
                source_endpoint_evidence_request_path=source_request,
                move_lab_evidence_request_path=move_request,
                external_proof_plan_path=external_plan,
                handoff_package_path=handoff,
            )

            report = build_mvp_closure_report(package)

        self.assertFalse(report.ready_for_external_handoff)
        self.assertTrue(any(item.area == "move_lab_evidence_intake" for item in report.open_items))

    def test_verify_mvp_proof_rejects_invalid_nested_handoff_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            handoff = write_invalid_zip(root / "handoff.zip")
            package = root / "mvp-proof.zip"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                handoff_package_path=handoff,
            )

            result = verify_mvp_proof_package(package)

        self.assertFalse(result.ok)
        self.assertTrue(any("handoff/handoff-package.zip" in error and "handoff-manifest.json" in error for error in result.errors))

    def test_summary_marks_invalid_nested_handoff_unverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            handoff = write_invalid_zip(root / "handoff.zip")
            package = root / "mvp-proof.zip"
            out = root / "summary.md"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                handoff_package_path=handoff,
            )

            summary = write_mvp_proof_summary(package, out)
            report = build_mvp_closure_report(package)
            text = out.read_text(encoding="utf-8")

        self.assertFalse(summary.verification.ok)
        self.assertEqual(summary.handoff_verification_status, "invalid")
        self.assertIn("Handoff package: `invalid`", text)
        self.assertIn("Nested handoff package failed semantic handoff verification", text)
        self.assertEqual(report.verified_roles, ())
        self.assertTrue(any(item.area == "proof_package_integrity" for item in report.open_items))

    def test_cli_summarize_mvp_proof_writes_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            out = root / "summary.md"
            package_mvp_proof(package, mvp_audit_path=audit)

            with patch("sys.stdout"):
                code = main(["summarize-mvp-proof", "--package", str(package), "--out", str(out)])

            text = out.read_text(encoding="utf-8")

        self.assertEqual(code, 0)
        self.assertIn("# MVP Proof Package Summary", text)
        self.assertIn("MVP status", text)

    def test_cli_summarize_mvp_proof_prints_nested_handoff_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            handoff = write_zip(root / "handoff.zip")
            package = root / "mvp-proof.zip"
            package_mvp_proof(package, mvp_audit_path=audit, handoff_package_path=handoff)
            stdout = io.StringIO()

            with patch("sys.stdout", stdout):
                code = main(["summarize-mvp-proof", "--package", str(package)])

            output = stdout.getvalue()

        self.assertEqual(code, 0)
        self.assertIn("Nested handoff roles: 8", output)
        self.assertIn("Handoff readiness packet: present", output)

    def test_validate_mvp_proof_summary_accepts_current_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            out = root / "summary.md"
            package_mvp_proof(package, mvp_audit_path=audit)
            write_mvp_proof_summary(package, out)

            result = validate_mvp_proof_summary(package, out)

        self.assertTrue(result.ok, result.errors)

    def test_validate_mvp_proof_summary_rejects_tampered_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            out = root / "summary.md"
            package_mvp_proof(package, mvp_audit_path=audit)
            write_mvp_proof_summary(package, out)
            text = out.read_text(encoding="utf-8").replace("- MVP status: `partial`", "- MVP status: `pass`")
            out.write_text(text, encoding="utf-8")

            result = validate_mvp_proof_summary(package, out)

        self.assertFalse(result.ok)
        self.assertTrue(any("MVP status" in error for error in result.errors))

    def test_cli_validate_mvp_proof_summary_reports_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            out = root / "summary.md"
            package_mvp_proof(package, mvp_audit_path=audit)
            write_mvp_proof_summary(package, out)

            with patch("sys.stdout"):
                code = main(["validate-mvp-proof-summary", "--package", str(package), "--summary", str(out)])

        self.assertEqual(code, 0)

    def test_mvp_closure_report_lists_simulated_move_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial", move_warning=True))
            live = write_json(root / "live-proof.json", live_endpoint_proof())
            submit = write_json(root / "move-submit.json", {"schema_version": "nmrcp_move_submit_readiness_v1", "status": "pass", "errors": []})
            transcript = write_json(
                root / "move-lab-transcript.json",
                {"schema_version": "nmrcp_move_lab_transcript_validation_v1", "status": "warn", "errors": [], "warnings": []},
            )
            move = write_json(
                root / "move-proof.json",
                {
                    "schema_version": "nmrcp_move_lab_proof_validation_v1",
                    "status": "warn",
                    "checks": [{"name": "move-lab-proof-scope", "status": "pass", "detail": "simulated_contract"}],
                    "errors": [],
                    "warnings": ["simulated proof only"],
                },
            )
            runbook = write_valid_runbook(root / "move-lab-runbook.md")
            capture_kit = write_capture_kit(root)
            capture_validation = write_json(root / "move-lab-capture-kit-validation.json", capture_kit_validation("pass"))
            source_request = write_source_endpoint_evidence_request([], root / "source-endpoint-evidence-request.md")
            move_request = write_move_lab_evidence_request([], [], root / "move-lab-evidence-request.md")
            handoff = write_zip(root / "handoff.zip")
            package = root / "mvp-proof.zip"
            out = root / "closure.md"
            json_out = root / "closure.json"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                live_proof_path=live,
                move_submit_readiness_path=submit,
                move_lab_transcript_path=transcript,
                move_lab_proof_path=move,
                move_lab_runbook_path=runbook,
                move_lab_capture_kit_dir=capture_kit,
                move_lab_capture_validation_path=capture_validation,
                source_endpoint_evidence_request_path=source_request,
                move_lab_evidence_request_path=move_request,
                handoff_package_path=handoff,
            )

            report = write_mvp_closure_report(package, out, json_out)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            text = out.read_text(encoding="utf-8")

        self.assertEqual(report.overall_status, "partial")
        self.assertFalse(report.ready_for_external_handoff)
        self.assertEqual(report.closure_summary["open_items"], len(report.open_items))
        self.assertEqual(
            report.closure_summary["blocking_open_items"],
            sum(1 for item in report.open_items if item.blocking),
        )
        self.assertGreaterEqual(report.closure_summary["required_evidence_id_count"], 2)
        self.assertIn("nmrcp_move_lab_evidence_intake_v1", report.closure_summary["required_evidence_ids"])
        self.assertIn("nmrcp_move_lab_proof_validation_v1", report.closure_summary["required_evidence_ids"])
        self.assertTrue(any(item.area == "move_lab_proof" for item in report.open_items))
        self.assertTrue(any(item.area == "move_ready_plan" for item in report.open_items))
        move_ready = next(item for item in report.open_items if item.area == "move_ready_plan")
        move_proof = next(item for item in report.open_items if item.area == "move_lab_proof")
        self.assertIn("move-lab-evidence-intake", move_ready.action)
        self.assertIn("nmrcp_move_lab_evidence_intake_v1", move_ready.required_evidence)
        self.assertIn("evidence intake", move_proof.action)
        self.assertIn("nmrcp_move_lab_evidence_intake_v1", move_proof.required_evidence)
        self.assertTrue(report.closeout_commands)
        self.assertTrue(any("generate-approved-move-lab-proof" in command for command in report.closeout_commands))
        self.assertTrue(any("validate-move-lab-evidence-intake" in command for command in report.closeout_commands))
        self.assertTrue(any("change-gate" in command for command in report.closeout_commands))
        self.assertTrue(any("--dir outputs\\sample-assessment" in command for command in report.closeout_commands))
        change_gate_index = report.closeout_commands.index("python -m nmrcp.cli change-gate `")
        self.assertIn("--dir outputs\\sample-assessment", report.closeout_commands[change_gate_index + 1])
        audit_index = report.closeout_commands.index("python -m nmrcp.cli mvp-audit `")
        self.assertIn("--assessment-intake outputs\\assessment-intake.csv", report.closeout_commands[audit_index + 3])
        self.assertIn("--live-proof outputs\\source-collection\\live-proof-validation.json", report.closeout_commands[audit_index + 4])
        package_index = report.closeout_commands.index("python -m nmrcp.cli package-mvp-proof `")
        self.assertIn("--live-proof outputs\\source-collection\\live-proof-validation.json", report.closeout_commands[package_index + 2])
        self.assertTrue(any("package-handoff" in command for command in report.closeout_commands))
        self.assertTrue(any("verify-handoff" in command for command in report.closeout_commands))
        self.assertTrue(any("verify-mvp-proof" in command for command in report.closeout_commands))
        self.assertTrue(any("summarize-mvp-proof" in command for command in report.closeout_commands))
        self.assertTrue(any("validate-mvp-proof-summary" in command for command in report.closeout_commands))
        self.assertTrue(any("validate-mvp-closure-report" in command for command in report.closeout_commands))
        self.assertTrue(any("launch-readiness-report" in command for command in report.closeout_commands))
        self.assertTrue(any("validate-launch-readiness-report" in command for command in report.closeout_commands))
        self.assertTrue(any("--move-lab-runbook" in command for command in report.closeout_commands))
        self.assertTrue(any("--move-lab-closure-checklist" in command for command in report.closeout_commands))
        self.assertTrue(any("--move-lab-readiness-packet" in command for command in report.closeout_commands))
        self.assertTrue(any("--source-collection-plan" in command for command in report.closeout_commands))
        self.assertTrue(any("--source-endpoint-evidence-request" in command for command in report.closeout_commands))
        self.assertTrue(any("--move-lab-evidence-request" in command for command in report.closeout_commands))
        self.assertEqual(payload["schema_version"], "nmrcp_mvp_closure_report_v1")
        self.assertEqual(payload["closure_summary"]["open_items"], len(payload["open_items"]))
        self.assertEqual(payload["closure_summary"]["blocking_open_items"], 2)
        self.assertTrue(any("validate-move-lab-evidence-intake" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("generate-approved-move-lab-proof" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("validate-mvp-proof-summary" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("validate-mvp-closure-report" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("validate-launch-readiness-report" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("--move-lab-runbook" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("--move-lab-readiness-packet" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("--source-collection-plan" in command for command in payload["closeout_commands"]))
        self.assertEqual(payload["handoff_role_counts"]["move_lab_readiness_packet"], 1)
        self.assertEqual(payload["handoff_role_counts"]["assessment_artifact"], 6)
        self.assertTrue(any("nmrcp_move_lab_evidence_intake_v1" in item["required_evidence"] for item in payload["open_items"]))
        self.assertIn("## Closeout Commands", text)
        self.assertIn("- Blocking open items: `2`", text)
        self.assertIn("- Required evidence IDs:", text)
        self.assertIn("## Required Evidence IDs", text)
        self.assertIn("- `nmrcp_move_lab_evidence_intake_v1`", text)
        self.assertIn("- `nmrcp_move_lab_proof_validation_v1`", text)
        self.assertIn("## Handoff Package Roles", text)
        self.assertIn("| `move_lab_readiness_packet` | `1` |", text)
        self.assertIn("validate-move-lab-evidence-intake", text)
        self.assertIn("validate-mvp-proof-summary", text)
        self.assertIn("validate-mvp-closure-report", text)
        self.assertIn("validate-launch-readiness-report", text)
        self.assertIn("Real approved Nutanix Move appliance behavior remains unproven", text)
        self.assertIn("nmrcp_move_lab_evidence_intake_v1", text)

    def test_mvp_closure_report_passes_with_approved_complete_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("pass"))
            live = write_json(root / "live-proof.json", live_endpoint_proof())
            submit = write_json(root / "move-submit.json", {"schema_version": "nmrcp_move_submit_readiness_v1", "status": "pass", "errors": []})
            transcript = write_json(
                root / "move-lab-transcript.json",
                {"schema_version": "nmrcp_move_lab_transcript_validation_v1", "status": "pass", "errors": [], "warnings": []},
            )
            move = write_json(root / "move-proof.json", approved_move_proof_validation())
            runbook = write_valid_runbook(root / "move-lab-runbook.md")
            capture_kit = write_capture_kit(root)
            capture_validation = write_json(root / "move-lab-capture-kit-validation.json", capture_kit_validation("pass"))
            readiness_packet = write_json(root / "move-lab-readiness-packet.json", readiness_packet_payload("pass"))
            intake = write_json(root / "move-lab-evidence-intake.json", evidence_intake("pass"))
            operator_summary = write_valid_operator_gate_summary(root / "operator-gate-summary.md")
            source_request = write_source_endpoint_evidence_request([], root / "source-endpoint-evidence-request.md")
            source_intake = write_completed_intake(root / "assessment-intake.csv")
            source_plan = root / "source-collection-plan.md"
            self.assertTrue(write_source_collection_plan(source_intake, source_plan).ok)
            move_request = write_move_lab_evidence_request([], [], root / "move-lab-evidence-request.md")
            external_plan_payload = build_external_proof_plan(root).to_dict()
            external_plan_payload["status"] = "ready_for_external_handoff"
            for step in external_plan_payload["steps"]:
                step["status"] = "pass"
                step["current_gap"] = "closed by supplied proof"
            external_plan = write_json(root / "external-proof-plan.json", external_plan_payload)
            handoff = write_zip(root / "handoff.zip")
            package = root / "mvp-proof.zip"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                live_proof_path=live,
                move_submit_readiness_path=submit,
                move_lab_transcript_path=transcript,
                move_lab_proof_path=move,
                move_lab_runbook_path=runbook,
                move_lab_capture_kit_dir=capture_kit,
                move_lab_capture_validation_path=capture_validation,
                move_lab_readiness_packet_path=readiness_packet,
                move_lab_evidence_intake_path=intake,
                operator_gate_summary_path=operator_summary,
                source_collection_plan_path=source_plan,
                source_endpoint_evidence_request_path=source_request,
                move_lab_evidence_request_path=move_request,
                external_proof_plan_path=external_plan,
                handoff_package_path=handoff,
            )

            report = build_mvp_closure_report(package)

        self.assertEqual(report.overall_status, "pass")
        self.assertTrue(report.ready_for_external_handoff)
        self.assertEqual(report.closure_summary["open_items"], 0)
        self.assertEqual(report.closure_summary["blocking_open_items"], 0)
        self.assertEqual(report.closure_summary["required_evidence_id_count"], 0)
        self.assertEqual(report.closure_summary["required_evidence_ids"], [])
        self.assertEqual(report.closure_summary["closeout_command_lines"], 0)
        self.assertEqual(report.open_items, ())
        self.assertEqual(report.closeout_commands, ())
        self.assertIn("handoff_package", report.verified_roles)
        self.assertIn("source_collection_plan", report.verified_roles)
        self.assertIn("source_endpoint_evidence_request", report.verified_roles)
        self.assertIn("move_lab_evidence_request", report.verified_roles)
        self.assertIn("external_proof_plan", report.verified_roles)
        self.assertIn("move_lab_readiness_packet", report.verified_roles)
        self.assertIn("move_lab_readiness_packet", report.handoff_roles)
        self.assertEqual(report.handoff_role_counts["move_lab_readiness_packet"], 1)

    def test_verify_mvp_proof_rejects_tampered_operator_gate_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            operator_summary = write_text(root / "operator-gate-summary.md", "# Operator Gate Summary\n")
            package = root / "mvp-proof.zip"
            package_mvp_proof(
                package,
                mvp_audit_path=audit,
                operator_gate_summary_path=operator_summary,
            )

            result = verify_mvp_proof_package(package)

        self.assertFalse(result.ok)
        self.assertTrue(any("Operator gate summary missing required gate row" in error for error in result.errors))

    def test_cli_mvp_closure_report_writes_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            out = root / "closure.md"
            json_out = root / "closure.json"
            package_mvp_proof(package, mvp_audit_path=audit)

            with patch("sys.stdout"):
                code = main(["mvp-closure-report", "--package", str(package), "--out", str(out), "--json-out", str(json_out)])

            text = out.read_text(encoding="utf-8")
            payload = json.loads(json_out.read_text(encoding="utf-8"))

        self.assertEqual(code, 0)
        self.assertIn("# MVP Closure Report", text)
        self.assertEqual(payload["schema_version"], "nmrcp_mvp_closure_report_v1")

    def test_cli_mvp_closure_report_prints_nested_handoff_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            handoff = write_zip(root / "handoff.zip")
            package = root / "mvp-proof.zip"
            package_mvp_proof(package, mvp_audit_path=audit, handoff_package_path=handoff)
            stdout = io.StringIO()

            with patch("sys.stdout", stdout):
                code = main(["mvp-closure-report", "--package", str(package)])

            output = stdout.getvalue()

        self.assertEqual(code, 0)
        self.assertIn("Nested handoff roles: 8", output)
        self.assertIn("Handoff readiness packet: present (1)", output)
        self.assertIn("Blocking open items:", output)
        self.assertIn("Required evidence IDs:", output)
        self.assertIn("Required evidence ID list:", output)

    def test_validate_mvp_closure_report_accepts_current_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            out = root / "closure.md"
            json_out = root / "closure.json"
            package_mvp_proof(package, mvp_audit_path=audit)
            write_mvp_closure_report(package, out, json_out)

            result = validate_mvp_closure_report(package, json_out, markdown_report_path=out)

        self.assertTrue(result.ok, result.errors)

    def test_validate_mvp_closure_report_accepts_equivalent_package_paths(self):
        with tempfile.TemporaryDirectory(dir=".") as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            out = root / "closure.md"
            json_out = root / "closure.json"
            package_mvp_proof(package, mvp_audit_path=audit)
            write_mvp_closure_report(package.resolve(), out, json_out)

            result = validate_mvp_closure_report(package, json_out, markdown_report_path=out)

        self.assertTrue(result.ok, result.errors)

    def test_validate_mvp_closure_report_rejects_stale_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            out = root / "closure.md"
            json_out = root / "closure.json"
            package_mvp_proof(package, mvp_audit_path=audit)
            write_mvp_closure_report(package, out, json_out)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            payload["overall_status"] = "pass"
            json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = validate_mvp_closure_report(package, json_out, markdown_report_path=out)

        self.assertFalse(result.ok)
        self.assertTrue(any("overall_status" in error for error in result.errors))

    def test_validate_mvp_closure_report_rejects_missing_required_evidence_id_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial", move_warning=True))
            move = write_json(
                root / "move-proof.json",
                {
                    "schema_version": "nmrcp_move_lab_proof_validation_v1",
                    "status": "warn",
                    "checks": [{"name": "move-lab-proof-scope", "status": "pass", "detail": "simulated_contract"}],
                    "errors": [],
                    "warnings": ["simulated proof only"],
                },
            )
            package = root / "mvp-proof.zip"
            out = root / "closure.md"
            json_out = root / "closure.json"
            package_mvp_proof(package, mvp_audit_path=audit, move_lab_proof_path=move)
            write_mvp_closure_report(package, out, json_out)
            text = out.read_text(encoding="utf-8").replace("- `nmrcp_move_lab_evidence_intake_v1`\n", "")
            out.write_text(text, encoding="utf-8")

            result = validate_mvp_closure_report(package, json_out, markdown_report_path=out)

        self.assertFalse(result.ok)
        self.assertTrue(any("missing required evidence ID" in error for error in result.errors))

    def test_validate_mvp_closure_report_rejects_missing_closeout_command_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial", move_warning=True))
            move = write_json(
                root / "move-proof.json",
                {
                    "schema_version": "nmrcp_move_lab_proof_validation_v1",
                    "status": "warn",
                    "checks": [{"name": "move-lab-proof-scope", "status": "pass", "detail": "simulated_contract"}],
                    "errors": [],
                    "warnings": ["simulated proof only"],
                },
            )
            package = root / "mvp-proof.zip"
            out = root / "closure.md"
            json_out = root / "closure.json"
            package_mvp_proof(package, mvp_audit_path=audit, move_lab_proof_path=move)
            write_mvp_closure_report(package, out, json_out)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            command = payload["closeout_commands"][0]
            out.write_text(out.read_text(encoding="utf-8").replace(f"{command}\n", ""), encoding="utf-8")

            result = validate_mvp_closure_report(package, json_out, markdown_report_path=out)

        self.assertFalse(result.ok)
        self.assertTrue(any("missing closeout command line" in error for error in result.errors))

    def test_validate_mvp_closure_report_rejects_tampered_summary_count_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial", move_warning=True))
            package = root / "mvp-proof.zip"
            out = root / "closure.md"
            json_out = root / "closure.json"
            package_mvp_proof(package, mvp_audit_path=audit)
            write_mvp_closure_report(package, out, json_out)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            expected = payload["closure_summary"]["closeout_command_lines"]
            out.write_text(
                out.read_text(encoding="utf-8").replace(
                    f"- Closeout command lines: `{expected}`",
                    "- Closeout command lines: `0`",
                ),
                encoding="utf-8",
            )

            result = validate_mvp_closure_report(package, json_out, markdown_report_path=out)

        self.assertFalse(result.ok)
        self.assertTrue(any("Closeout command lines" in error for error in result.errors))

    def test_cli_validate_mvp_closure_report_reports_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit = write_json(root / "mvp-audit.json", mvp_audit("partial"))
            package = root / "mvp-proof.zip"
            out = root / "closure.md"
            json_out = root / "closure.json"
            package_mvp_proof(package, mvp_audit_path=audit)
            write_mvp_closure_report(package, out, json_out)

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-mvp-closure-report",
                        "--package",
                        str(package),
                        "--report",
                        str(out),
                        "--json-report",
                        str(json_out),
                    ]
                )

        self.assertEqual(code, 0)


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def write_valid_runbook(path: Path) -> Path:
    return write_text(
        path,
        "\n".join(
            [
                "# Move Lab Execution Runbook",
                "",
                "This runbook is for non-production Nutanix Move appliance proof only.",
                "",
                "## Inputs",
                "",
                "- Payload contract: `nmrcp_move_api_payload_dry_run_v1`",
                "",
                "## Required Environment",
                "",
                '$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"',
                "",
                "## Pre-Run Gates",
                "",
                "- Confirm `dry_run_only=true` and `mutation_allowed=false`.",
                "- Confirm `start_immediately=false`.",
                "",
                "## Stop Conditions",
                "",
                "- Stop if any endpoint, workload, or target is production.",
                "- Stop if evidence contains credentials, secrets, or unredacted endpoint values.",
                "",
                "## Validation Commands",
                "",
                "python -m nmrcp.cli validate-move-submit-readiness",
                "python -m nmrcp.cli validate-move-lab-transcript",
                "python -m nmrcp.cli generate-approved-move-lab-proof",
                "python -m nmrcp.cli validate-move-lab-proof --transcript-validation outputs\\move-lab-transcript-validation.json",
                "python -m nmrcp.cli validate-move-lab-evidence-intake --capture-kit-validation outputs\\move-lab-capture-kit-validation.json",
                "",
                "## Evidence To Capture",
                "",
                "- Move lab evidence intake JSON with `status=pass`.",
                "- Confirmation that `created_plans=0` and `started_migrations=0` for MVP proof.",
                "- Redacted operator notes.",
                "",
                "## Workload Scope",
                "",
                "| VM ID | Wave | Target | Readiness | Risk | Dependency Count |",
                "| --- | --- | --- | --- | --- | --- |",
                "",
                "## Closeout",
                "",
                "Run `mvp-audit --move-proof --move-lab-evidence-intake` after proof validation and intake pass.",
                "",
            ]
        ),
    )


def write_valid_operator_gate_summary(path: Path) -> Path:
    rows = [
        ("Source endpoint evidence request", "pass", "PASS: checks=22, errors=0, warnings=0"),
        ("Move lab evidence request", "pass", "PASS: checks=21, errors=0, warnings=0"),
        ("Target capacity fit", "pass", "PASS: targets=2, errors=0, warnings=0"),
        ("Target reconciliation", "warn", "PASS: checked=3, matched=1, errors=0, warnings=1"),
        ("Source network validation", "pass", "PASS: checked=1, matched=1, errors=0, warnings=0"),
        ("Target network mapping", "pass", "PASS: checked=1, mapped=1, errors=0, warnings=0"),
        ("Final validation results", "pass", "PASS: rows=11, passed=11, failed=0, open=0, errors=0, warnings=0"),
        ("Final remediation closure", "pass", "PASS: rows=12, open=0, closed=9, accepted=3, waived=0, errors=0, warnings=0"),
        ("Final owner sign-offs", "warn", "PASS: rows=3, approved=3, pending=0, rejected=0, waived=0, errors=0, warnings=3"),
        ("Approval exception closure", "pass", "PASS: rows=10, required=0, approved=10, rejected=0, waived=0, errors=0, warnings=0"),
        ("Operator assessment review", "pass", "PASS: rows=1, errors=0, warnings=0"),
        ("Move lab capture kit", "pass", "PASS: checks=4, errors=0, warnings=0"),
        ("Move lab closure checklist", "pass", "PASS: checks=26, errors=0, warnings=0"),
        ("Approved Move lab proof", "pass", "PASS: checks=10, errors=0, warnings=0"),
        ("Move lab evidence intake", "pass", "PASS: checks=8, errors=0, warnings=0"),
    ]
    lines = [
        "# Operator Gate Summary",
        "",
        "| Gate | Status | Detail |",
        "| --- | --- | --- |",
    ]
    lines.extend(f"| {label} | {status} | {detail} |" for label, status, detail in rows)
    lines.extend(
        [
            "",
            "## Use",
            "",
            "Attach this summary with the evidence bundle so operators and change reviewers can see which source, lab, and optional closure gates were evaluated.",
            "",
        ]
    )
    return write_text(path, "\n".join(lines))


def write_zip(path: Path) -> Path:
    closure = write_move_lab_closure_checklist(path.parent / "move-lab-closure-checklist-for-handoff.md")
    request = write_move_lab_evidence_request([], [], path.parent / "move-lab-evidence-request-for-handoff.md")
    source_request = write_source_endpoint_evidence_request([], path.parent / "source-endpoint-evidence-request-for-handoff.md")
    readiness_packet = json.dumps(readiness_packet_payload("pass"), indent=2).encode("utf-8")
    entries = {
        "assessment/evidence-manifest.json": b'{"schema_version":"nmrcp_evidence_manifest_v1","artifacts":[]}',
        "assessment/assessment.json": b'{"assessments":[]}',
        "assessment/nutanix-move-plan.csv": b"source_vm_id,include_in_move_plan\n",
        "assessment/pre-post-validation-checklist.md": b"# Validation Checklist\n",
        "assessment/move-lab-closure-checklist.md": closure.read_bytes(),
        "assessment/move-lab-evidence-request.md": request.read_bytes(),
        "assessment/source-endpoint-evidence-request.md": source_request.read_bytes(),
        "move/move-lab-readiness-packet.json": readiness_packet,
    }
    manifest_files = [
        handoff_manifest_entry("assessment/evidence-manifest.json", "assessment_manifest", entries["assessment/evidence-manifest.json"]),
        handoff_manifest_entry("assessment/assessment.json", "assessment_artifact", entries["assessment/assessment.json"]),
        handoff_manifest_entry("assessment/nutanix-move-plan.csv", "assessment_artifact", entries["assessment/nutanix-move-plan.csv"]),
        handoff_manifest_entry("assessment/pre-post-validation-checklist.md", "assessment_artifact", entries["assessment/pre-post-validation-checklist.md"]),
        handoff_manifest_entry("assessment/move-lab-closure-checklist.md", "assessment_artifact", entries["assessment/move-lab-closure-checklist.md"]),
        handoff_manifest_entry("assessment/move-lab-evidence-request.md", "assessment_artifact", entries["assessment/move-lab-evidence-request.md"]),
        handoff_manifest_entry("assessment/source-endpoint-evidence-request.md", "assessment_artifact", entries["assessment/source-endpoint-evidence-request.md"]),
        handoff_manifest_entry("move/move-lab-readiness-packet.json", "move_lab_readiness_packet", entries["move/move-lab-readiness-packet.json"]),
    ]
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "handoff-manifest.json",
            json.dumps(
                {
                    "schema_version": "nmrcp_handoff_manifest_v1",
                    "generated_at": "2026-07-25T00:00:00+00:00",
                    "assessment_dir": "assessment",
                    "files": manifest_files,
                },
                indent=2,
            ),
        )
        for archive_path, data in entries.items():
            archive.writestr(archive_path, data)
    return path


def write_invalid_zip(path: Path) -> Path:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("README.md", "not a handoff package")
    return path


def handoff_manifest_entry(path: str, role: str, data: bytes) -> dict:
    import hashlib

    return {
        "path": path,
        "role": role,
        "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
    }


def write_capture_kit(root: Path, *, evidence_state: str = "template_only_replace_after_lab_capture") -> Path:
    kit = root / "capture-kit"
    kit.mkdir()
    write_json(
        kit / "move-lab-transcript.template.json",
        {
            "schema_version": "nmrcp_move_lab_transcript_v1",
            "proof_scope": "approved_lab_move_appliance",
            "evidence_state": evidence_state,
            "environment": "lab",
            "production_targets": False,
            "mutation_performed": False,
        },
    )
    write_text(kit / "move-lab-capture-checklist.md", "# Move Lab Capture Checklist\n")
    return kit


def capture_kit_validation(status: str) -> dict:
    return {
        "schema_version": "nmrcp_move_lab_capture_kit_validation_v1",
        "status": status,
        "checks": [],
        "errors": ["template failed"] if status == "fail" else [],
        "warnings": [],
    }


def evidence_intake(status: str) -> dict:
    return {
        "schema_version": "nmrcp_move_lab_evidence_intake_v1",
        "status": status,
        "checks": [],
        "errors": ["intake failed"] if status == "fail" else [],
        "warnings": [],
    }


def readiness_packet_payload(status: str) -> dict:
    return {
        "schema_version": "nmrcp_move_lab_readiness_packet_v1",
        "status": status,
        "flags": {
            "not_external_proof": True,
            "requires_approved_lab_capture": True,
            "lab_only": True,
            "redacted_evidence_only": True,
        },
        "artifacts": [
            {
                "role": role,
                "path": f"outputs/{role}.json",
                "state": "present",
                "bytes": "10",
                "sha256": "a" * 64,
            }
            for role in (
                "payload",
                "review",
                "move_submit_readiness",
                "capture_kit_template",
                "capture_kit_checklist",
                "capture_kit_validation",
                "evidence_preflight",
                "evidence_preflight_report",
                "runbook",
                "evidence_request",
                "closure_checklist",
            )
        ],
        "required_closeout": [
            "validate-move-lab-transcript",
            "generate-approved-move-lab-proof",
            "validate-move-lab-proof",
            "validate-move-lab-evidence-intake",
        ],
        "checks": [],
        "errors": [],
        "warnings": ["operator notes are advisory"] if status == "warn" else [],
    }


def live_endpoint_proof() -> dict:
    required_checks = (
        "live-readiness-status",
        "live-readiness-security",
        "collection-summary-schema",
        "collection-summary-privacy",
        "collection-summary-assessment-intake",
        "collection-proof-manifest-security",
        "collection-proof-manifest-api-allowlist",
        "collection-proof-manifest-assessment-intake",
        "collection-proof-manifest-assessment-intake-match",
    )
    return {
        "schema_version": "nmrcp_live_endpoint_proof_v1",
        "status": "pass",
        "checks": [
            {"name": name, "status": "pass", "detail": "validated"}
            for name in required_checks
        ],
        "errors": [],
        "warnings": [],
    }


def approved_move_proof_validation() -> dict:
    return {
        "schema_version": "nmrcp_move_lab_proof_validation_v1",
        "status": "pass",
        "checks": [
            {"name": "move-lab-proof-scope", "status": "pass", "detail": "approved_lab_move_appliance"},
            {"name": "move-lab-transcript-validation-link", "status": "pass", "detail": "sha256 matched"},
        ],
        "errors": [],
        "warnings": [],
    }


def mvp_audit(status: str, *, move_warning: bool = False) -> dict:
    requirements = []
    if move_warning:
        requirements.append(
            {
                "id": "move_ready_plan",
                "status": "partial",
                "warnings": ["Real Nutanix Move appliance API behavior is not validated"],
                "errors": [],
            }
        )
    return {
        "schema_version": "nmrcp_mvp_readiness_audit_v1",
        "status": status,
        "summary": {"pass": 6, "partial": 1 if status == "partial" else 0, "fail": 1 if status == "fail" else 0},
        "requirements": requirements,
    }


if __name__ == "__main__":
    unittest.main()
