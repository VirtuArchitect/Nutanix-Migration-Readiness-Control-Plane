import json
import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.capacity import validate_capacity_fit, write_capacity_fit_csv
from nmrcp.change_gate import run_change_gate
from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.evidence_bundle import package_evidence
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.dependencies import merge_dependencies, read_dependency_csv
from nmrcp.network_mapping import validate_network_mappings, write_network_mapping_csv
from nmrcp.operator_review import write_operator_review_template
from nmrcp.scoring import assess_inventory
from nmrcp.source_networks import validate_source_networks, write_source_network_validation_csv
from nmrcp.target_reconciliation import reconcile_target_inventory, write_target_reconciliation_csv
from nmrcp.waves import plan_waves
from nmrcp.approval_exceptions import read_rows


class ChangeGateTests(unittest.TestCase):
    def test_change_gate_passes_verified_pre_change_package_with_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            bundle = Path(tmp) / "bundle.zip"
            package_evidence(out_dir, bundle)

            result = run_change_gate(out_dir, bundle_path=bundle)

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.status, "pass")
            self.assertTrue(any("Validation results not provided" in warning for warning in result.warnings))

    def test_change_gate_includes_final_validation_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            bundle = Path(tmp) / "bundle.zip"
            package_evidence(out_dir, bundle)

            result = run_change_gate(
                out_dir,
                bundle_path=bundle,
                validation_results_path=Path("examples/sample_validation_results.csv"),
                remediation_tracker_path=Path("examples/sample_remediation_tracker_closed.csv"),
            )

            self.assertTrue(result.ok, result.errors)
            validation_check = next(check for check in result.checks if check["name"] == "validation-results")
            remediation_check = next(check for check in result.checks if check["name"] == "remediation-tracker")
            self.assertIn("passed=11", validation_check["detail"])
            self.assertIn("closed=9", remediation_check["detail"])

    def test_change_gate_includes_approved_operator_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            review = write_approved_operator_review(Path(tmp) / "operator-review.csv", out_dir)

            result = run_change_gate(
                out_dir,
                operator_review_path=review,
            )

            self.assertTrue(result.ok, result.errors)
            review_check = next(check for check in result.checks if check["name"] == "operator-review")
            self.assertIn("rows=1", review_check["detail"])

    def test_change_gate_rejects_operator_review_for_different_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = build_sample_assessment(root)
            review = write_approved_operator_review(root / "operator-review.csv", root / "other-assessment")

            result = run_change_gate(out_dir, operator_review_path=review)

            self.assertFalse(result.ok)
            self.assertTrue(any("does not match gated assessment" in error for error in result.errors))

    def test_change_gate_includes_approved_approval_exceptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = build_sample_assessment(root)
            approved = approved_exceptions_copy(out_dir, root / "approved-approval-exceptions.csv")

            result = run_change_gate(out_dir, approval_exceptions_path=approved)

            self.assertTrue(result.ok, result.errors)
            approvals_check = next(check for check in result.checks if check["name"] == "approval-exception-approvals")
            self.assertIn("approved=10", approvals_check["detail"])

    def test_change_gate_rejects_unresolved_approval_exceptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))

            result = run_change_gate(out_dir, approval_exceptions_path=out_dir / "approval-exceptions.csv")

            self.assertFalse(result.ok)
            self.assertTrue(any("required approval exception blocks final closure" in error for error in result.errors))

    def test_change_gate_rejects_draft_operator_review_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            review = Path(tmp) / "operator-review.csv"
            write_operator_review_template(out_dir, review)

            result = run_change_gate(out_dir, operator_review_path=review)

            self.assertFalse(result.ok)
            self.assertTrue(any("must be approved" in error for error in result.errors))

    def test_change_gate_accepts_approved_move_lab_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            proof = write_move_lab_validation(Path(tmp), scope="approved_lab_move_appliance", status="pass")
            intake = write_move_lab_evidence_intake(Path(tmp), status="pass")

            result = run_change_gate(out_dir, move_lab_proof_path=proof, move_lab_evidence_intake_path=intake)

            self.assertTrue(result.ok, result.errors)
            proof_check = next(check for check in result.checks if check["name"] == "move-lab-proof")
            intake_check = next(check for check in result.checks if check["name"] == "move-lab-evidence-intake")
            self.assertIn("PASS", proof_check["detail"])
            self.assertIn("PASS", intake_check["detail"])

    def test_change_gate_requires_evidence_intake_with_approved_move_lab_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            proof = write_move_lab_validation(Path(tmp), scope="approved_lab_move_appliance", status="pass")

            result = run_change_gate(out_dir, move_lab_proof_path=proof)

            self.assertFalse(result.ok)
            self.assertTrue(any("evidence intake is required" in error for error in result.errors))

    def test_change_gate_rejects_failed_move_lab_evidence_intake(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            proof = write_move_lab_validation(Path(tmp), scope="approved_lab_move_appliance", status="pass")
            intake = write_move_lab_evidence_intake(Path(tmp), status="fail")

            result = run_change_gate(out_dir, move_lab_proof_path=proof, move_lab_evidence_intake_path=intake)

            self.assertFalse(result.ok)
            self.assertTrue(any("evidence intake failed" in error for error in result.errors))

    def test_change_gate_includes_move_lab_capture_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            capture_validation = write_capture_validation(Path(tmp), status="pass")

            result = run_change_gate(out_dir, move_lab_capture_validation_path=capture_validation)

            self.assertTrue(result.ok, result.errors)
            capture_check = next(check for check in result.checks if check["name"] == "move-lab-capture-kit")
            self.assertIn("PASS", capture_check["detail"])

    def test_change_gate_rejects_failed_move_lab_capture_preflight(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            capture_validation = write_capture_validation(Path(tmp), status="fail")

            result = run_change_gate(out_dir, move_lab_capture_validation_path=capture_validation)

            self.assertFalse(result.ok)
            self.assertTrue(any("Move lab capture kit validation status must be pass" in error for error in result.errors))

    def test_change_gate_rejects_simulated_move_lab_proof_for_final_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            proof = write_move_lab_validation(Path(tmp), scope="simulated_contract", status="warn")

            result = run_change_gate(out_dir, move_lab_proof_path=proof)

            self.assertFalse(result.ok)
            self.assertTrue(any("approved_lab_move_appliance" in error for error in result.errors))

    def test_change_gate_fails_on_open_remediation_tracker_for_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))

            result = run_change_gate(out_dir, remediation_tracker_path=out_dir / "remediation-tracker.csv")

            self.assertFalse(result.ok)
            self.assertTrue(any("open remediation row blocks final closure" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            (out_dir / "assessment.json").write_text("tampered", encoding="utf-8")

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("assessment.json" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_executive_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            brief = out_dir / "executive-readiness-brief.md"
            brief.write_text(
                brief.read_text(encoding="utf-8").replace("- Held workloads: 2", "- Held workloads: 0"),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("Held workloads: 2" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_change_board_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            evidence = out_dir / "change-board-evidence.md"
            evidence.write_text(
                evidence.read_text(encoding="utf-8").replace("- Mutating calls: `0`", ""),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("Mutating calls" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_wave_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            summary = out_dir / "wave-readiness-summary.csv"
            summary.write_text(
                summary.read_text(encoding="utf-8").replace("Wave 0 - Pilot Ready", "Wave 0 - Pilot Ready Tampered"),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("Missing wave summary row: Wave 0 - Pilot Ready" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_business_impact_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            summary = out_dir / "business-impact-summary.csv"
            summary.write_text(
                summary.read_text(encoding="utf-8").replace("critical,2,", "critical,99,"),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("critical: total_workloads expected '2'" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_risk_register(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            register = out_dir / "migration-risk-register.csv"
            register.write_text(
                register.read_text(encoding="utf-8").replace("vds_mapping_required,medium,2,", "vds_mapping_required,medium,99,"),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("vds_mapping_required: affected_workloads expected '2'" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_validation_checklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            checklist = out_dir / "pre-post-validation-checklist.md"
            checklist.write_text(
                checklist.read_text(encoding="utf-8").replace(
                    "- Stop if an excluded or blocked workload appears in the execution list.",
                    "",
                ),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("excluded or blocked workload" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_migration_runbook(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            runbook = out_dir / "migration-runbook.md"
            runbook.write_text(
                runbook.read_text(encoding="utf-8").replace(
                    "- Do not stage this workload in Nutanix Move until all required actions are cleared.",
                    "",
                ),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("hold instruction" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_operator_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            report = out_dir / "operator-report.html"
            report.write_text(report.read_text(encoding="utf-8").replace("Collection Audit Proof", "Collection Notes"), encoding="utf-8")

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("Collection Audit Proof" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_operator_portal(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            portal = out_dir / "operator-portal.html"
            portal.write_text(
                portal.read_text(encoding="utf-8").replace("nmrcp_operator_portal_v1", "nmrcp_old_portal_v1"),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("operator portal" in error.lower() and "schema_version" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_operator_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            dashboard = out_dir / "operator-dashboard.html"
            dashboard.write_text(
                dashboard.read_text(encoding="utf-8").replace("nmrcp_operator_dashboard_v1", "nmrcp_old_dashboard_v1"),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("schema_version" in error for error in result.errors))

    def test_cli_change_gate_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            with patch("sys.stdout"):
                result = main(
                    [
                        "change-gate",
                        "--dir",
                        str(out_dir),
                        "--remediation-tracker",
                        "examples/sample_remediation_tracker_closed.csv",
                        "--json",
                    ]
                )

            self.assertEqual(result, 0)

    def test_change_gate_checks_present_capacity_fit_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            capacity_result = validate_capacity_fit(
                Path("examples/sample_inventory.json"),
                out_dir / "nutanix-move-plan.csv",
                Path("examples/sample_target_capacity.json"),
            )
            write_capacity_fit_csv(capacity_result, out_dir / "target-capacity-fit.csv")
            from nmrcp.evidence import write_evidence_manifest

            write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)

            result = run_change_gate(out_dir)

            self.assertTrue(result.ok, result.errors)
            capacity_check = next(check for check in result.checks if check["name"] == "capacity-fit")
            self.assertIn("targets=", capacity_check["detail"])

    def test_change_gate_checks_present_network_mapping_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            network_result = validate_network_mappings(
                out_dir / "nutanix-move-plan.csv",
                Path("examples/sample_move_payload_config.json"),
            )
            write_network_mapping_csv(network_result, out_dir / "target-network-mapping.csv")
            from nmrcp.evidence import write_evidence_manifest

            write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)

            result = run_change_gate(out_dir)

            self.assertTrue(result.ok, result.errors)
            network_check = next(check for check in result.checks if check["name"] == "network-mapping")
            self.assertIn("checked=", network_check["detail"])

    def test_change_gate_checks_present_target_reconciliation_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            reconciliation = reconcile_target_inventory(
                Path("examples/sample_inventory.json"),
                Path("examples/sample_prism_inventory.json"),
                out_dir / "nutanix-move-plan.csv",
            )
            write_target_reconciliation_csv(reconciliation, out_dir / "target-reconciliation.csv")
            from nmrcp.evidence import write_evidence_manifest

            write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)

            result = run_change_gate(out_dir)

            self.assertTrue(result.ok, result.errors)
            reconciliation_check = next(check for check in result.checks if check["name"] == "target-reconciliation")
            self.assertIn("matched=1", reconciliation_check["detail"])

    def test_change_gate_checks_present_source_network_validation_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_sample_assessment(tmp_path)
            networks = write_vcenter_network_inventory(tmp_path, ["120"])
            source_networks = validate_source_networks(out_dir / "nutanix-move-plan.csv", networks)
            write_source_network_validation_csv(source_networks, out_dir / "source-network-validation.csv")
            from nmrcp.evidence import write_evidence_manifest

            write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)

            result = run_change_gate(out_dir)

            self.assertTrue(result.ok, result.errors)
            source_network_check = next(check for check in result.checks if check["name"] == "source-network-validation")
            self.assertIn("matched=1", source_network_check["detail"])

    def test_change_gate_fails_on_failed_source_network_validation_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            (out_dir / "source-network-validation.csv").write_text(
                "\n".join(
                    [
                        "schema_version,source_vm_id,source_vm_name,wave,owner,target,source_network,status,notes",
                        "nmrcp_source_network_validation_v1,vm-1001,pilot-web-01,Wave 0 - Pilot Ready,Platform Team,ahv,999,fail,source network missing from vCenter network inventory",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            from nmrcp.evidence import write_evidence_manifest

            write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("source network validation failed" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_owner_risk_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            summary = out_dir / "owner-risk-summary.csv"
            summary.write_text(
                summary.read_text(encoding="utf-8").replace("Business Apps,1,", "Business Apps,99,"),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("Business Apps: total_workloads expected '1'" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_migration_waves(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            waves = out_dir / "migration-waves.csv"
            waves.write_text(
                waves.read_text(encoding="utf-8").replace("Wave 0 - Pilot Ready,vm-1001", "Excluded Until Cleared,vm-1001"),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "migration-waves" and check["status"] == "fail" for check in result.checks))

    def test_change_gate_fails_when_included_workload_has_critical_coverage_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            (out_dir / "inventory-coverage.csv").write_text(
                "\n".join(
                    [
                        "workload_id,name,coverage_percent,present_fields,partial_fields,missing_fields",
                        "vm-1001,pilot-web-01,88,owner;guest_os;networking;tools;backup;storage;application_owner_approval,,guest_identity;rollback_owner",
                        "vm-2020,erp-app-01,100,owner;guest_os;networking;guest_identity;tools;backup;storage;application_owner_approval;rollback_owner,,",
                        "vm-3030,payments-edge-01,100,owner;guest_os;networking;guest_identity;tools;backup;storage;application_owner_approval;rollback_owner,,",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            from nmrcp.evidence import write_evidence_manifest

            write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("critical inventory coverage gaps" in error for error in result.errors))


def build_sample_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
    inventory = merge_dependencies(inventory, read_dependency_csv(Path("examples/sample_dependencies.csv")))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


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
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_evidence_intake_v1",
                "status": status,
                "checks": [],
                "errors": [] if status == "pass" else ["evidence intake failed"],
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


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


def write_vcenter_network_inventory(tmp: Path, vlans: list[str]) -> Path:
    path = tmp / "vcenter-networks.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_vcenter_network_inventory_v1",
                "source": {"system": "test-vcenter", "mutating_calls": 0},
                "networks": [{"network": f"VLAN{vlan}", "name": f"VLAN{vlan}", "vlan": vlan} for vlan in vlans],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
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


if __name__ == "__main__":
    unittest.main()
