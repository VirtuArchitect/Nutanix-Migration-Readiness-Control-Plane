import json
import hashlib
import csv
import tempfile
import unittest
import zipfile
from pathlib import Path

from nmrcp.evidence import write_assessment
from nmrcp.evidence_bundle import package_evidence
from nmrcp.handoff_package import package_handoff, verify_handoff_package
from nmrcp.move_payload import build_move_payload
from nmrcp.scoring import assess_inventory
from nmrcp.source_collection_plan import write_source_collection_plan
from nmrcp.waves import plan_waves
from nmrcp.approval_exceptions import read_rows
from tests.test_source_collection_plan import write_completed_intake


class HandoffPackageTests(unittest.TestCase):
    def test_package_handoff_includes_verified_operational_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            bundle = Path(tmp) / "evidence.zip"
            handoff = Path(tmp) / "handoff.zip"
            move_payload = Path(tmp) / "move-api-payload.dry-run.json"
            approval_exceptions = approved_exceptions_copy(out_dir, Path(tmp) / "approved-approval-exceptions.csv")
            move_lab_proof = write_move_lab_validation(Path(tmp), scope="approved_lab_move_appliance", status="pass")
            move_lab_evidence_intake = write_move_lab_evidence_intake(Path(tmp), status="pass")
            move_lab_readiness_packet = write_move_lab_readiness_packet(Path(tmp), status="warn")
            source_collection_plan = write_source_collection_plan_for_test(Path(tmp))
            operator_review = write_approved_operator_review(Path(tmp) / "operator-review.csv", out_dir)
            capture_kit = write_capture_kit(Path(tmp))
            capture_validation = write_json(
                Path(tmp) / "move-lab-capture-kit-validation.json",
                capture_kit_validation("pass"),
            )
            package_evidence(out_dir, bundle)
            move_payload.write_text(
                json.dumps(
                    build_move_payload(
                        out_dir / "nutanix-move-plan.csv",
                        Path("examples/sample_move_payload_config.json"),
                    ),
                    indent=2,
                ),
                encoding="utf-8",
            )

            package_handoff(
                out_dir,
                handoff,
                bundle_path=bundle,
                validation_results_path=Path("examples/sample_validation_results.csv"),
                remediation_tracker_path=Path("examples/sample_remediation_tracker_closed.csv"),
                signoffs_path=Path("examples/sample_owner_signoffs_approved.csv"),
                approval_exceptions_path=approval_exceptions,
                operator_review_path=operator_review,
                move_lab_proof_path=move_lab_proof,
                move_lab_evidence_intake_path=move_lab_evidence_intake,
                move_lab_readiness_packet_path=move_lab_readiness_packet,
                move_lab_capture_kit_dir=capture_kit,
                move_lab_capture_validation_path=capture_validation,
                source_collection_plan_path=source_collection_plan,
                move_payload_path=move_payload,
            )
            result = verify_handoff_package(handoff)

            self.assertTrue(result.ok, result.errors)
            with zipfile.ZipFile(handoff, "r") as archive:
                names = set(archive.namelist())
                manifest = json.loads(archive.read("handoff-manifest.json").decode("utf-8"))
            self.assertIn("assessment/assessment.json", names)
            self.assertIn("assessment/move-lab-closure-checklist.md", names)
            self.assertIn("assessment/move-lab-evidence-request.md", names)
            self.assertIn("assessment/source-endpoint-evidence-request.md", names)
            self.assertIn("bundles/evidence-bundle.zip", names)
            self.assertIn("validation/validation-results.csv", names)
            self.assertIn("remediation/final-remediation-tracker.csv", names)
            self.assertIn("signoffs/final-owner-signoffs.csv", names)
            self.assertIn("signoffs/final-approval-exceptions.csv", names)
            self.assertIn("review/operator-review.csv", names)
            self.assertIn("move/move-lab-proof-validation.json", names)
            self.assertIn("move/move-lab-evidence-intake.json", names)
            self.assertIn("move/move-lab-readiness-packet.json", names)
            self.assertIn("source/source-collection-plan.md", names)
            self.assertIn("move/move-lab-transcript.template.json", names)
            self.assertIn("move/move-lab-capture-checklist.md", names)
            self.assertIn("move/move-lab-capture-kit-validation.json", names)
            self.assertIn("move/move-api-payload.dry-run.json", names)
            self.assertEqual(manifest["schema_version"], "nmrcp_handoff_manifest_v1")
            self.assertTrue(any(entry["role"] == "remediation_tracker" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "owner_signoffs" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "approval_exceptions" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "operator_review" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_proof" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_evidence_intake" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_readiness_packet" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "source_collection_plan" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_capture_template" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_capture_checklist" for entry in manifest["files"]))
            self.assertTrue(any(entry["role"] == "move_lab_capture_validation" for entry in manifest["files"]))
            self.assertFalse(any("source_path" in entry for entry in manifest["files"]))

    def test_package_handoff_rejects_simulated_move_lab_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"
            proof = write_move_lab_validation(Path(tmp), scope="simulated_contract", status="warn")
            intake = write_move_lab_evidence_intake(Path(tmp), status="pass")

            with self.assertRaises(ValueError) as failure:
                package_handoff(out_dir, handoff, move_lab_proof_path=proof, move_lab_evidence_intake_path=intake)

            self.assertIn("Move lab proof validation failed", str(failure.exception))

    def test_package_handoff_requires_evidence_intake_with_move_lab_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"
            proof = write_move_lab_validation(Path(tmp), scope="approved_lab_move_appliance", status="pass")

            with self.assertRaises(ValueError) as failure:
                package_handoff(out_dir, handoff, move_lab_proof_path=proof)

            self.assertIn("Approved Move lab proof handoff requires Move lab evidence intake", str(failure.exception))

    def test_package_handoff_rejects_failed_evidence_intake(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"
            intake = write_move_lab_evidence_intake(Path(tmp), status="fail")

            with self.assertRaises(ValueError) as failure:
                package_handoff(out_dir, handoff, move_lab_evidence_intake_path=intake)

            self.assertIn("Move lab evidence intake validation failed", str(failure.exception))

    def test_package_handoff_requires_capture_kit_and_validation_together(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = build_sample_assessment(root)
            handoff = root / "handoff.zip"
            capture_kit = write_capture_kit(root)

            with self.assertRaises(ValueError) as failure:
                package_handoff(out_dir, handoff, move_lab_capture_kit_dir=capture_kit)

            self.assertIn("Move lab capture kit and validation proof must be packaged together", str(failure.exception))

    def test_package_handoff_rejects_failed_capture_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = build_sample_assessment(root)
            handoff = root / "handoff.zip"
            capture_kit = write_capture_kit(root)
            capture_validation = write_json(root / "move-lab-capture-kit-validation.json", capture_kit_validation("fail"))

            with self.assertRaises(ValueError) as failure:
                package_handoff(
                    out_dir,
                    handoff,
                    move_lab_capture_kit_dir=capture_kit,
                    move_lab_capture_validation_path=capture_validation,
                )

            self.assertIn("Move lab capture kit validation failed", str(failure.exception))

    def test_verify_handoff_requires_capture_roles_as_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = build_sample_assessment(root)
            handoff = root / "handoff.zip"
            broken = root / "missing-capture-validation.zip"
            capture_kit = write_capture_kit(root)
            capture_validation = write_json(root / "move-lab-capture-kit-validation.json", capture_kit_validation("pass"))
            package_handoff(
                out_dir,
                handoff,
                move_lab_capture_kit_dir=capture_kit,
                move_lab_capture_validation_path=capture_validation,
            )

            def mutate_manifest(manifest):
                manifest["files"] = [
                    entry
                    for entry in manifest["files"]
                    if entry.get("role") != "move_lab_capture_validation"
                ]

            rewrite_handoff_package(handoff, broken, mutate_manifest=mutate_manifest)
            result = verify_handoff_package(broken)

            self.assertFalse(result.ok)
            self.assertTrue(any("capture kit and validation proof must be packaged together" in error for error in result.errors))

    def test_verify_handoff_requires_intake_with_move_lab_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = build_sample_assessment(root)
            handoff = root / "handoff.zip"
            broken = root / "missing-move-lab-intake.zip"
            proof = write_move_lab_validation(root, scope="approved_lab_move_appliance", status="pass")
            intake = write_move_lab_evidence_intake(root, status="pass")
            package_handoff(
                out_dir,
                handoff,
                move_lab_proof_path=proof,
                move_lab_evidence_intake_path=intake,
            )

            def mutate_manifest(manifest):
                manifest["files"] = [
                    entry
                    for entry in manifest["files"]
                    if entry.get("role") != "move_lab_evidence_intake"
                ]

            rewrite_handoff_package(handoff, broken, mutate_manifest=mutate_manifest)
            result = verify_handoff_package(broken)

            self.assertFalse(result.ok)
            self.assertTrue(any("requires Move lab evidence intake" in error for error in result.errors))

    def test_package_handoff_rejects_open_remediation_tracker(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"

            with self.assertRaises(ValueError) as failure:
                package_handoff(out_dir, handoff, remediation_tracker_path=out_dir / "remediation-tracker.csv")

            self.assertIn("Remediation tracker validation failed", str(failure.exception))

    def test_package_handoff_rejects_pending_signoffs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"

            with self.assertRaises(ValueError) as failure:
                package_handoff(out_dir, handoff, signoffs_path=out_dir / "owner-signoff-matrix.csv")

            self.assertIn("Sign-off validation failed", str(failure.exception))

    def test_package_handoff_rejects_unresolved_approval_exceptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"

            with self.assertRaises(ValueError) as failure:
                package_handoff(out_dir, handoff, approval_exceptions_path=out_dir / "approval-exceptions.csv")

            self.assertIn("Approval exception validation failed", str(failure.exception))

    def test_package_handoff_rejects_operator_review_for_different_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = build_sample_assessment(root)
            handoff = root / "handoff.zip"
            review = write_approved_operator_review(root / "operator-review.csv", root / "other-assessment")

            with self.assertRaises(ValueError) as failure:
                package_handoff(out_dir, handoff, operator_review_path=review)

            self.assertIn("does not match gated assessment", str(failure.exception))

    def test_verify_handoff_detects_missing_manifest_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"
            broken = Path(tmp) / "broken.zip"
            package_handoff(out_dir, handoff)

            with zipfile.ZipFile(handoff, "r") as source, zipfile.ZipFile(broken, "w") as target:
                for name in source.namelist():
                    if name != "assessment/assessment.json":
                        target.writestr(name, source.read(name))

            result = verify_handoff_package(broken)

            self.assertFalse(result.ok)
            self.assertTrue(any("assessment/assessment.json" in error for error in result.errors))

    def test_verify_handoff_rejects_duplicate_unique_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"
            broken = Path(tmp) / "duplicate-role.zip"
            package_handoff(out_dir, handoff)

            def mutate_manifest(manifest):
                for entry in manifest["files"]:
                    if entry["path"] == "assessment/assessment.json":
                        entry["role"] = "assessment_manifest"
                        break

            rewrite_handoff_package(handoff, broken, mutate_manifest=mutate_manifest)
            result = verify_handoff_package(broken)

            self.assertFalse(result.ok)
            self.assertTrue(any("duplicate manifest role assessment_manifest" in error for error in result.errors))

    def test_verify_handoff_rejects_unmanifested_archive_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"
            broken = Path(tmp) / "extra-entry.zip"
            package_handoff(out_dir, handoff)

            rewrite_handoff_package(
                handoff,
                broken,
                extra_entries={"untracked/customer-export.csv": b"vm,password\napp-01,secret\n"},
            )
            result = verify_handoff_package(broken)

            self.assertFalse(result.ok)
            self.assertTrue(any("untracked/customer-export.csv: archive entry is not listed in handoff manifest" in error for error in result.errors))

    def test_verify_handoff_rejects_missing_core_assessment_artifact_role(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"
            broken = Path(tmp) / "missing-core-artifact.zip"
            package_handoff(out_dir, handoff)

            def mutate_manifest(manifest):
                manifest["files"] = [
                    entry
                    for entry in manifest["files"]
                    if entry["path"] != "assessment/pre-post-validation-checklist.md"
                ]

            rewrite_handoff_package(handoff, broken, mutate_manifest=mutate_manifest)
            result = verify_handoff_package(broken)

            self.assertFalse(result.ok)
            self.assertTrue(
                any("missing required assessment artifact: assessment/pre-post-validation-checklist.md" in error for error in result.errors)
            )

    def test_verify_handoff_rejects_tampered_move_lab_closure_checklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"
            broken = Path(tmp) / "tampered-move-lab-closure.zip"
            package_handoff(out_dir, handoff)

            rewrite_handoff_package(
                handoff,
                broken,
                replacements={"assessment/move-lab-closure-checklist.md": b"# Move Lab Closure Checklist\n"},
            )
            result = verify_handoff_package(broken)

            self.assertFalse(result.ok)
            self.assertTrue(any("move-lab-closure-checklist.md" in error and "missing required section" in error for error in result.errors))

    def test_verify_handoff_rejects_tampered_move_lab_evidence_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"
            broken = Path(tmp) / "tampered-move-lab-request.zip"
            package_handoff(out_dir, handoff)

            rewrite_handoff_package(
                handoff,
                broken,
                replacements={"assessment/move-lab-evidence-request.md": b"# Move Lab Evidence Request\n"},
            )
            result = verify_handoff_package(broken)

            self.assertFalse(result.ok)
            self.assertTrue(any("move-lab-evidence-request.md" in error and "missing required section" in error for error in result.errors))

    def test_verify_handoff_rejects_tampered_source_endpoint_evidence_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"
            broken = Path(tmp) / "tampered-source-endpoint-request.zip"
            package_handoff(out_dir, handoff)

            rewrite_handoff_package(
                handoff,
                broken,
                replacements={"assessment/source-endpoint-evidence-request.md": b"# Source Endpoint Evidence Request\n"},
            )
            result = verify_handoff_package(broken)

        self.assertFalse(result.ok)
        self.assertTrue(any("source-endpoint-evidence-request.md" in error and "missing required section" in error for error in result.errors))

    def test_verify_handoff_rejects_tampered_source_collection_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = build_sample_assessment(root)
            handoff = root / "handoff.zip"
            broken = root / "tampered-source-collection-plan.zip"
            source_collection_plan = write_source_collection_plan_for_test(root)
            package_handoff(out_dir, handoff, source_collection_plan_path=source_collection_plan)

            text = source_collection_plan.read_text(encoding="utf-8") + "\nLeaked endpoint: https://vcenter01.corp.local/sdk\n"
            rewrite_handoff_package(
                handoff,
                broken,
                replacements={"source/source-collection-plan.md": text.encode("utf-8")},
            )
            result = verify_handoff_package(broken)

        self.assertFalse(result.ok)
        self.assertTrue(any("source-collection-plan.md" in error and "endpoint or secret-like material" in error for error in result.errors))

    def test_verify_handoff_rejects_mutating_move_payload_even_when_hash_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            handoff = Path(tmp) / "handoff.zip"
            broken = Path(tmp) / "mutating-move-payload.zip"
            move_payload = Path(tmp) / "move-api-payload.dry-run.json"
            payload = build_move_payload(
                out_dir / "nutanix-move-plan.csv",
                Path("examples/sample_move_payload_config.json"),
            )
            move_payload.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            package_handoff(out_dir, handoff, move_payload_path=move_payload)

            payload["dry_run_only"] = False
            payload["mutation_allowed"] = True
            replacement = json.dumps(payload, indent=2).encode("utf-8")
            rewrite_handoff_package(
                handoff,
                broken,
                replacements={"move/move-api-payload.dry-run.json": replacement},
            )
            result = verify_handoff_package(broken)

            self.assertFalse(result.ok)
            self.assertTrue(any("dry_run_only must be true" in error for error in result.errors))
            self.assertTrue(any("mutation_allowed must be false" in error for error in result.errors))

    def test_verify_handoff_rejects_tampered_move_lab_readiness_packet(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = build_sample_assessment(root)
            handoff = root / "handoff.zip"
            broken = root / "tampered-readiness-packet.zip"
            packet = write_move_lab_readiness_packet(root, status="warn")
            package_handoff(out_dir, handoff, move_lab_readiness_packet_path=packet)

            payload = json.loads(packet.read_text(encoding="utf-8"))
            payload["flags"]["lab_only"] = False
            replacement = json.dumps(payload, indent=2).encode("utf-8")
            rewrite_handoff_package(
                handoff,
                broken,
                replacements={"move/move-lab-readiness-packet.json": replacement},
            )
            result = verify_handoff_package(broken)

            self.assertFalse(result.ok)
            self.assertTrue(any("flag lab_only must be true" in error for error in result.errors))


def build_sample_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


def write_source_collection_plan_for_test(root: Path) -> Path:
    intake = write_completed_intake(root / "assessment-intake.csv")
    plan = root / "source-collection-plan.md"
    result = write_source_collection_plan(intake, plan)
    if not result.ok:
        raise AssertionError(result.errors)
    return plan


def write_move_lab_validation(tmp: Path, scope: str, status: str) -> Path:
    path = tmp / f"move-lab-proof-{scope}.json"
    checks = [{"name": "move-lab-proof-scope", "status": "pass", "detail": scope}]
    if scope == "approved_lab_move_appliance":
        checks.append({"name": "move-lab-transcript-validation-link", "status": "pass", "detail": "sha256 matched"})
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_proof_validation_v1",
                "status": status,
                "checks": checks,
                "errors": [],
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_move_lab_evidence_intake(tmp: Path, status: str) -> Path:
    path = tmp / f"move-lab-evidence-intake-{status}.json"
    write_json(
        path,
        {
            "schema_version": "nmrcp_move_lab_evidence_intake_v1",
            "status": status,
            "checks": [],
            "errors": [] if status == "pass" else ["evidence intake failed"],
            "warnings": [],
        },
    )
    return path


def write_move_lab_readiness_packet(tmp: Path, status: str) -> Path:
    path = tmp / f"move-lab-readiness-packet-{status}.json"
    roles = (
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
    write_json(
        path,
        {
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
                    "path": f"outputs/{role}",
                    "state": "present",
                    "bytes": "1",
                    "sha256": "a" * 64,
                }
                for role in roles
            ],
            "checks": [],
            "errors": [],
            "warnings": ["operator-note: confirm approved lab schedule"] if status == "warn" else [],
            "required_closeout": [
                "validate-move-lab-transcript",
                "generate-approved-move-lab-proof",
                "validate-move-lab-proof",
                "validate-move-lab-evidence-intake",
            ],
            "remaining_external_gate": "Approved non-production Nutanix Move appliance capture is still required.",
        },
    )
    return path


def write_capture_kit(root: Path, *, evidence_state: str = "template_only_replace_after_lab_capture") -> Path:
    kit = root / "capture-kit"
    kit.mkdir(parents=True, exist_ok=True)
    write_json(
        kit / "move-lab-transcript.template.json",
        {
            "schema_version": "nmrcp_move_lab_transcript_v1",
            "evidence_state": evidence_state,
            "production_targets": False,
            "mutation_performed": False,
        },
    )
    (kit / "move-lab-capture-checklist.md").write_text("# Move Lab Capture Checklist\n", encoding="utf-8")
    return kit


def capture_kit_validation(status: str) -> dict:
    return {
        "schema_version": "nmrcp_move_lab_capture_kit_validation_v1",
        "status": status,
        "checks": [],
        "errors": [] if status == "pass" else ["capture kit failed"],
        "warnings": [],
    }


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def approved_exceptions_copy(out_dir: Path, path: Path) -> Path:
    rows = read_rows(out_dir / "approval-exceptions.csv", [])
    for index, row in enumerate(rows, start=1):
        row["approval_status"] = "approved"
        row["approval_ref"] = f"CHG-2026-EXC-{index:03d}"
        row["approved_by"] = "Migration Lead"
        row["approved_at"] = "2026-07-25T00:00:00Z"
        row["notes"] = "Approved for lab change-board review."
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


def rewrite_handoff_package(
    source_path: Path,
    target_path: Path,
    *,
    mutate_manifest=None,
    replacements: dict[str, bytes] | None = None,
    extra_entries: dict[str, bytes] | None = None,
) -> None:
    replacements = replacements or {}
    extra_entries = extra_entries or {}
    with zipfile.ZipFile(source_path, "r") as source:
        contents = {name: source.read(name) for name in source.namelist()}
    manifest = json.loads(contents["handoff-manifest.json"].decode("utf-8"))
    for entry in manifest["files"]:
        path = entry.get("path")
        if path in replacements:
            data = replacements[path]
            entry["size_bytes"] = len(data)
            entry["sha256"] = hashlib.sha256(data).hexdigest()
            contents[path] = data
    if mutate_manifest:
        mutate_manifest(manifest)
    contents["handoff-manifest.json"] = json.dumps(manifest, indent=2).encode("utf-8")
    contents.update(extra_entries)
    with zipfile.ZipFile(target_path, "w", compression=zipfile.ZIP_DEFLATED) as target:
        for name, data in contents.items():
            target.writestr(name, data)


if __name__ == "__main__":
    unittest.main()
