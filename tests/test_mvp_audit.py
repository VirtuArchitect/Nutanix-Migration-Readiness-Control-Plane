import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.assessment_intake import write_assessment_intake_template
from nmrcp.cli import main
from nmrcp.change_gate import run_change_gate
from nmrcp.dependencies import merge_dependencies, read_dependency_csv
from nmrcp.evidence import write_assessment
from nmrcp.evidence_bundle import package_evidence
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.mvp_audit import audit_mvp
from nmrcp.scoring import assess_inventory
from nmrcp.source_networks import validate_source_networks, write_source_network_validation_csv
from nmrcp.warning_acceptance import WARNING_ACCEPTANCE_SCHEMA_VERSION
from nmrcp.waves import plan_waves


class MvpAuditTests(unittest.TestCase):
    def test_mvp_audit_reports_current_repo_as_partial_until_external_proof(self):
        result = audit_mvp(Path.cwd())

        self.assertTrue(result.ok)
        self.assertEqual(result.status, "partial")
        ids = {requirement.id for requirement in result.requirements}
        self.assertIn("read_only_collection", ids)
        self.assertIn("move_ready_plan", ids)
        warnings = [warning for requirement in result.requirements for warning in requirement.warnings]
        self.assertTrue(any("Real vCenter and Prism Central endpoints" in warning for warning in warnings))
        self.assertTrue(any("Real Nutanix Move appliance" in warning for warning in warnings))
        move = next(requirement for requirement in result.requirements if requirement.id == "move_ready_plan")
        self.assertIn("src/nmrcp/move_lab_capture_kit.py", move.evidence_files)
        self.assertIn("src/nmrcp/move_lab_transcript.py", move.evidence_files)
        self.assertIn("tests/test_move_lab_transcript.py", move.evidence_files)
        self.assertIn("docs/operations/move-lab-transcript.md", move.evidence_files)

    def test_mvp_audit_can_check_generated_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            assessment_dir = Path(tmp)
            for name in (
                "migration-waves.csv",
                "wave-readiness-summary.csv",
                "wave-execution-calendar.csv",
                "change-board-evidence.md",
                "migration-runbook.md",
                "dependency-review.csv",
                "connectivity-checklist.csv",
                "identity-cutover-plan.csv",
                "compatibility-research.csv",
                "migration-risk-register.csv",
                "business-impact-summary.csv",
                "approval-exceptions.csv",
                "tools-driver-readiness.csv",
                "storage-posture.csv",
                "recovery-readiness.csv",
                "rollback-plan.csv",
                "move-staging-readiness.csv",
                "move-staging-brief.md",
                "migration-execution-queue.csv",
                "prism-category-mapping.csv",
                "stakeholder-communication-plan.csv",
                "what-will-break-report.csv",
                "what-will-break-brief.md",
                "executive-readiness-brief.md",
                "operations-console.html",
                "operator-portal.html",
                "operator-report.html",
                "operator-dashboard.html",
                "nutanix-move-plan.csv",
                "move-plan-brief.md",
                "pre-post-validation-checklist.md",
                "workload-validation-checklist.csv",
                "move-api-payload.dry-run.json",
            ):
                (assessment_dir / name).write_text("sample\n", encoding="utf-8")

            result = audit_mvp(Path.cwd(), assessment_dir=assessment_dir)
            waves = next(requirement for requirement in result.requirements if requirement.id == "waves_and_change_evidence")

            self.assertNotIn("migration-waves.csv", waves.missing_files)
            self.assertEqual(waves.status, "pass")

    def test_mvp_audit_validates_generated_artifact_contracts_when_assessment_json_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            assessment_dir = build_assessment(Path(tmp))

            result = audit_mvp(Path.cwd(), assessment_dir=assessment_dir)
            waves = next(requirement for requirement in result.requirements if requirement.id == "waves_and_change_evidence")
            handoff = next(requirement for requirement in result.requirements if requirement.id == "handoff_and_review")

            self.assertEqual(waves.status, "pass", waves.errors)
            self.assertNotEqual(handoff.status, "fail", handoff.errors)

    def test_mvp_audit_uses_final_handoff_closure_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assessment_dir = build_assessment(root)
            write_move_ready_placeholders(assessment_dir)
            bundle = root / "evidence-bundle.zip"
            package_evidence(assessment_dir, bundle)
            capture_validation = write_capture_validation(root, status="pass")
            operator_review = write_approved_operator_review(root / "operator-review.csv", assessment_dir)
            warning_acceptance = write_warning_acceptance(root, assessment_dir, bundle, capture_validation, operator_review)

            result = audit_mvp(
                Path.cwd(),
                assessment_dir=assessment_dir,
                evidence_bundle_path=bundle,
                validation_results_path=Path("examples/sample_validation_results.csv"),
                remediation_tracker_path=Path("examples/sample_remediation_tracker_closed.csv"),
                signoffs_path=Path("examples/sample_owner_signoffs_approved.csv"),
                approval_exceptions_path=Path("examples/sample_approval_exceptions_approved.csv"),
                operator_review_path=operator_review,
                move_lab_capture_validation_path=capture_validation,
                warning_acceptance_path=warning_acceptance,
            )
            handoff = next(requirement for requirement in result.requirements if requirement.id == "handoff_and_review")

            self.assertEqual(handoff.status, "pass", handoff.errors)
            self.assertFalse(any("Validation results not provided" in warning for warning in handoff.warnings))
            self.assertFalse(any("Approval exception approvals not provided" in warning for warning in handoff.warnings))
            self.assertFalse(any("Approved Move lab proof not provided" in warning for warning in handoff.warnings))

    def test_mvp_audit_fails_on_tampered_generated_artifact_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            assessment_dir = build_assessment(Path(tmp))
            dashboard = assessment_dir / "operator-dashboard.html"
            dashboard.write_text(
                dashboard.read_text(encoding="utf-8").replace("nmrcp_operator_dashboard_v1", "nmrcp_old_dashboard_v1"),
                encoding="utf-8",
            )

            result = audit_mvp(Path.cwd(), assessment_dir=assessment_dir)
            waves = next(requirement for requirement in result.requirements if requirement.id == "waves_and_change_evidence")

            self.assertEqual(result.status, "fail")
            self.assertEqual(waves.status, "fail")
            self.assertTrue(any("operator-dashboard" in error and "schema_version" in error for error in waves.errors))

    def test_mvp_audit_fails_when_local_evidence_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = audit_mvp(Path(tmp))

            self.assertFalse(result.ok)
            self.assertEqual(result.status, "fail")
            self.assertTrue(any(requirement.missing_files for requirement in result.requirements))

    def test_mvp_audit_keeps_read_only_collection_partial_without_intake_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            proof = Path(tmp) / "live-proof-validation.json"
            write_live_proof(proof)

            result = audit_mvp(Path.cwd(), live_proof_path=proof)
            read_only = next(requirement for requirement in result.requirements if requirement.id == "read_only_collection")

            self.assertEqual(read_only.status, "partial")
            self.assertTrue(any("Assessment intake not provided" in warning for warning in read_only.warnings))
            self.assertEqual(result.status, "partial")

    def test_mvp_audit_accepts_live_endpoint_proof_with_completed_intake(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proof = write_live_proof(root / "live-proof-validation.json")
            intake = write_completed_intake(root / "assessment-intake.csv")

            result = audit_mvp(Path.cwd(), live_proof_path=proof, assessment_intake_path=intake)
            read_only = next(requirement for requirement in result.requirements if requirement.id == "read_only_collection")
            move = next(requirement for requirement in result.requirements if requirement.id == "move_ready_plan")

            self.assertEqual(read_only.status, "pass", read_only.errors)
            self.assertIn(str(intake), read_only.evidence_files)
            self.assertEqual(move.status, "partial")
            self.assertEqual(result.status, "partial")

    def test_mvp_audit_rejects_stale_status_only_live_endpoint_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proof = write_status_only_live_proof(root / "live-proof-validation.json")
            intake = write_completed_intake(root / "assessment-intake.csv")

            result = audit_mvp(Path.cwd(), live_proof_path=proof, assessment_intake_path=intake)
            read_only = next(requirement for requirement in result.requirements if requirement.id == "read_only_collection")

            self.assertEqual(read_only.status, "fail")
            self.assertTrue(any("live endpoint proof missing required check live-readiness-security" in error for error in read_only.errors))

    def test_mvp_audit_rejects_failed_live_endpoint_proof_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proof = write_live_proof(root / "live-proof-validation.json")
            payload = json.loads(proof.read_text(encoding="utf-8"))
            payload["checks"][1]["status"] = "fail"
            proof.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            intake = write_completed_intake(root / "assessment-intake.csv")

            result = audit_mvp(Path.cwd(), live_proof_path=proof, assessment_intake_path=intake)
            read_only = next(requirement for requirement in result.requirements if requirement.id == "read_only_collection")

            self.assertEqual(read_only.status, "fail")
            self.assertTrue(any("live endpoint proof check live-readiness-security must pass" in error for error in read_only.errors))

    def test_mvp_audit_rejects_invalid_assessment_intake_with_live_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proof = write_live_proof(root / "live-proof-validation.json")
            intake = write_assessment_intake_template(root / "assessment-intake.csv")

            result = audit_mvp(Path.cwd(), live_proof_path=proof, assessment_intake_path=intake)
            read_only = next(requirement for requirement in result.requirements if requirement.id == "read_only_collection")

            self.assertEqual(read_only.status, "fail")
            self.assertTrue(any("Assessment intake invalid" in error for error in read_only.errors))

    def test_cli_mvp_audit_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "mvp-audit.json"
            with patch("sys.stdout"):
                code = main(["mvp-audit", "--repo-root", str(Path.cwd()), "--out", str(out), "--json"])

            payload = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(payload["schema_version"], "nmrcp_mvp_readiness_audit_v1")
            self.assertEqual(payload["status"], "partial")

    def test_cli_mvp_audit_accepts_handoff_closure_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            assessment_dir = build_assessment(root)
            write_move_ready_placeholders(assessment_dir)
            bundle = root / "evidence-bundle.zip"
            out = root / "mvp-audit.json"
            capture_validation = write_capture_validation(root, status="pass")
            package_evidence(assessment_dir, bundle)
            operator_review = write_approved_operator_review(root / "operator-review.csv", assessment_dir)
            warning_acceptance = write_warning_acceptance(root, assessment_dir, bundle, capture_validation, operator_review)

            with patch("sys.stdout"):
                code = main(
                    [
                        "mvp-audit",
                        "--repo-root",
                        str(Path.cwd()),
                        "--assessment-dir",
                        str(assessment_dir),
                        "--assessment-intake",
                        "examples/sample_assessment_intake.csv",
                        "--evidence-bundle",
                        str(bundle),
                        "--validation-results",
                        "examples/sample_validation_results.csv",
                        "--remediation-tracker",
                        "examples/sample_remediation_tracker_closed.csv",
                        "--signoffs",
                        "examples/sample_owner_signoffs_approved.csv",
                        "--approval-exceptions",
                        "examples/sample_approval_exceptions_approved.csv",
                        "--operator-review",
                        str(operator_review),
                        "--move-lab-capture-validation",
                        str(capture_validation),
                        "--warning-acceptance",
                        str(warning_acceptance),
                        "--out",
                        str(out),
                        "--json",
                    ]
                )

            payload = json.loads(out.read_text(encoding="utf-8"))
            handoff = next(requirement for requirement in payload["requirements"] if requirement["id"] == "handoff_and_review")
            self.assertEqual(code, 0)
            self.assertEqual(handoff["status"], "pass")
            self.assertFalse(any("Validation results not provided" in warning for warning in handoff["warnings"]))
            self.assertFalse(any("Approval exception approvals not provided" in warning for warning in handoff["warnings"]))


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
    inventory = merge_dependencies(inventory, read_dependency_csv(Path("examples/sample_dependencies.csv")))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


def write_capture_validation(tmp: Path, status: str) -> Path:
    path = tmp / "move-lab-capture-kit-validation.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_capture_kit_validation_v1",
                "status": status,
                "checks": [],
                "errors": [] if status == "pass" else ["capture kit failed"],
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_warning_acceptance(
    tmp: Path,
    assessment_dir: Path,
    bundle: Path,
    capture_validation: Path,
    operator_review: Path,
) -> Path:
    gate = run_change_gate(
        assessment_dir,
        bundle_path=bundle,
        validation_results_path=Path("examples/sample_validation_results.csv"),
        remediation_tracker_path=Path("examples/sample_remediation_tracker_closed.csv"),
        signoffs_path=Path("examples/sample_owner_signoffs_approved.csv"),
        approval_exceptions_path=Path("examples/sample_approval_exceptions_approved.csv"),
        operator_review_path=operator_review,
        move_lab_capture_validation_path=capture_validation,
    )
    path = tmp / "warning-acceptance.csv"
    rows = [
        {
            "schema_version": WARNING_ACCEPTANCE_SCHEMA_VERSION,
            "warning_text": warning,
            "acceptance_status": "accepted",
            "acceptance_ref": f"CHG-2026-WARN-{index:03d}",
            "accepted_by": "Migration Lead",
            "accepted_at": "2026-07-25T00:00:00Z",
            "notes": "Accepted for reviewed lab closure evidence.",
        }
        for index, warning in enumerate(gate.warnings, start=1)
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_approved_operator_review(path: Path, assessment_dir: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "schema_version,assessment_dir,review_status,reviewed_by,reviewed_at,change_reference,coverage_reviewed,readiness_reviewed,move_plan_reviewed,evidence_reviewed,redaction_reviewed,rollback_reviewed,capacity_reviewed,target_reconciliation_reviewed,network_mapping_reviewed,app_map_reviewed,notes",
                f"nmrcp_operator_review_v1,{assessment_dir},approved,Lab Migration Lead,2026-07-24T12:00:00+00:00,CHG-LAB-0001,yes,yes,yes,yes,yes,yes,yes,yes,yes,yes,Reviewed matching assessment evidence.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


def write_live_proof(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_live_endpoint_proof_v1",
                "status": "pass",
                "checks": [
                    {"name": "live-readiness-status", "status": "pass", "detail": "pass"},
                    {"name": "live-readiness-security", "status": "pass", "detail": "read-only redacted mutation_allowed=false"},
                    {"name": "collection-summary-schema", "status": "pass", "detail": "nmrcp_collection_summary_v1"},
                    {"name": "collection-summary-privacy", "status": "pass", "detail": "redacted no credentials/endpoints"},
                    {"name": "collection-summary-assessment-intake", "status": "pass", "detail": "status=pass; rows=3"},
                    {"name": "collection-proof-manifest-security", "status": "pass", "detail": "read-only redacted mutation_allowed=false"},
                    {
                        "name": "collection-proof-manifest-api-allowlist",
                        "status": "pass",
                        "detail": "/api/nutanix/v3/clusters/list, /api/nutanix/v3/vms/list, /api/session, /api/vcenter/network, /api/vcenter/vm, /api/vcenter/vm/{vm}",
                    },
                    {"name": "collection-proof-manifest-assessment-intake", "status": "pass", "detail": "status=pass; rows=3"},
                    {"name": "collection-proof-manifest-assessment-intake-match", "status": "pass", "detail": "manifest matches collection summary"},
                ],
                "errors": [],
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_status_only_live_proof(path: Path) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_live_endpoint_proof_v1",
                "status": "pass",
                "checks": [],
                "errors": [],
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_completed_intake(path: Path) -> Path:
    write_assessment_intake_template(path)
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["field"] in {"secrets_stay_local_ack", "redacted_evidence_ack", "read_only_collection_ack", "no_production_mutation_ack"}:
            row["value"] = "true"
        elif row["field"] == "migration_target":
            row["value"] = "ahv"
        elif row["field"] == "approved_move_lab_available":
            row["value"] = "true"
        elif row["field"] == "rvtools_export_available":
            row["value"] = "true"
        elif row["required"] == "true":
            row["value"] = f"sample {row['field']}"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_move_ready_placeholders(assessment_dir: Path) -> None:
    networks = assessment_dir.parent / "vcenter-networks.json"
    networks.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_vcenter_network_inventory_v1",
                "source": {"system": "test-vcenter", "mutating_calls": 0},
                "networks": [{"network": "VLAN120", "name": "VLAN120", "vlan": "120"}],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    source_networks = validate_source_networks(assessment_dir / "nutanix-move-plan.csv", networks)
    write_source_network_validation_csv(source_networks, assessment_dir / "source-network-validation.csv")
    (assessment_dir / "move-api-payload.dry-run.json").write_text("{}\n", encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
