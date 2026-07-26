from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .approval_exceptions import validate_approval_exception_approvals, validate_approval_exceptions
from .business_impact import validate_business_impact_summary
from .capacity import validate_capacity_fit_csv
from .change_board_evidence import validate_change_board_evidence
from .compatibility_research import validate_compatibility_research
from .connectivity_checklist import validate_connectivity_checklist
from .dependency_review import validate_dependency_review
from .dependency_sequence import validate_dependency_sequence
from .evidence_bundle import verify_evidence, verify_evidence_bundle
from .executive_brief import validate_executive_brief
from .identity_cutover_plan import validate_identity_cutover_plan
from .migration_execution_queue import validate_migration_execution_queue
from .inventory_coverage import validate_inventory_coverage_csv
from .migration_waves import validate_migration_waves
from .move_lab_capture_kit import validate_move_lab_capture_kit_validation_file
from .move_lab_closure_checklist import validate_move_lab_closure_checklist
from .move_lab_evidence_intake import validate_move_lab_evidence_intake_validation_file
from .move_lab_evidence_request import validate_move_lab_evidence_request
from .move_lab_proof import validate_move_lab_proof_validation_file
from .move_plan import validate_move_plan
from .move_plan_brief import validate_move_plan_brief
from .move_staging_readiness import validate_move_staging_brief, validate_move_staging_readiness
from .network_mapping import validate_network_mapping_csv
from .migration_runbook import validate_migration_runbook
from .operator_review import validate_operator_review
from .operator_report import validate_operator_report
from .operator_dashboard import validate_operator_dashboard
from .operator_portal import validate_operator_portal
from .operations_console import validate_operations_console
from .partner_handoff_matrix import validate_partner_handoff_matrix
from .prism_categories import validate_prism_category_mapping
from .owner_risk import validate_owner_risk_summary
from .recovery_readiness import validate_recovery_readiness
from .redaction_review import review_evidence_dir
from .remediation import validate_remediation_tracker, validate_remediation_tracker_contract
from .risk_register import validate_risk_register
from .rollback_plan import validate_rollback_plan
from .signoff import validate_signoff_matrix_contract, validate_signoffs
from .source_endpoint_evidence_request import validate_source_endpoint_evidence_request
from .source_networks import validate_source_network_validation_csv
from .stakeholder_comms import validate_stakeholder_comms
from .storage_posture import validate_storage_posture
from .target_comparison import validate_target_readiness_comparison
from .target_reconciliation import validate_target_reconciliation_csv
from .tools_driver_readiness import validate_tools_driver_readiness
from .validation_checklist import validate_validation_checklist
from .validation_results import validate_validation_results
from .wave_execution_calendar import validate_wave_execution_calendar
from .wave_summary import validate_wave_readiness_summary
from .workload_validation_checklist import validate_workload_validation_checklist
from .what_will_break import validate_what_will_break, validate_what_will_break_brief


REQUIRED_ASSESSMENT_ARTIFACTS = {
    "assessment.json",
    "inventory-coverage.csv",
    "migration-waves.csv",
    "wave-readiness-summary.csv",
    "wave-execution-calendar.csv",
    "partner-handoff-matrix.csv",
    "target-readiness-comparison.csv",
    "compatibility-research.csv",
    "dependency-sequence.csv",
    "dependency-review.csv",
    "connectivity-checklist.csv",
    "identity-cutover-plan.csv",
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
    "remediation-tracker.csv",
    "migration-risk-register.csv",
    "owner-risk-summary.csv",
    "business-impact-summary.csv",
    "owner-signoff-matrix.csv",
    "approval-exceptions.csv",
    "nutanix-move-plan.csv",
    "move-plan-brief.md",
    "executive-readiness-brief.md",
    "change-board-evidence.md",
    "migration-runbook.md",
    "operations-console.html",
    "operator-portal.html",
    "operator-report.html",
    "operator-dashboard.html",
    "pre-post-validation-checklist.md",
    "move-lab-closure-checklist.md",
    "move-lab-evidence-request.md",
    "source-endpoint-evidence-request.md",
    "workload-validation-checklist.csv",
    "evidence-manifest.json",
}


@dataclass(frozen=True)
class ChangeGateResult:
    status: str
    checks: tuple[dict[str, Any], ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={len(self.checks)}, errors={len(self.errors)}, warnings={len(self.warnings)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": list(self.checks),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def run_change_gate(
    assessment_dir: Path,
    bundle_path: Path | None = None,
    validation_results_path: Path | None = None,
    remediation_tracker_path: Path | None = None,
    signoffs_path: Path | None = None,
    approval_exceptions_path: Path | None = None,
    operator_review_path: Path | None = None,
    move_lab_capture_validation_path: Path | None = None,
    move_lab_proof_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
    allow_pending_signoffs: bool = False,
    allow_draft_operator_review: bool = False,
) -> ChangeGateResult:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    missing = sorted(name for name in REQUIRED_ASSESSMENT_ARTIFACTS if not (assessment_dir / name).exists())
    add_check(checks, "required-artifacts", not missing, f"missing={len(missing)}")
    errors.extend(f"Missing required assessment artifact: {name}" for name in missing)

    try:
        assessment = json.loads((assessment_dir / "assessment.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        add_check(checks, "assessment-json", False, "assessment.json could not be read")
        errors.append(f"assessment.json could not be read: {exc}")
        assessment = {}
    else:
        summary = assessment.get("summary") if isinstance(assessment.get("summary"), dict) else {}
        coverage = assessment.get("inventory_coverage") if isinstance(assessment.get("inventory_coverage"), dict) else {}
        add_check(checks, "assessment-json", True, f"workloads={summary.get('total', 0)}")
        if int(summary.get("blocked") or 0) or int(summary.get("prepare") or 0):
            warnings.append(
                f"Assessment contains held workloads: prepare={summary.get('prepare', 0)}, blocked={summary.get('blocked', 0)}"
            )
        if float(coverage.get("average_coverage_percent") or 0) < 90:
            warnings.append(f"Average inventory coverage is below 90%: {coverage.get('average_coverage_percent', 0)}")

    try:
        executive_brief = validate_executive_brief(assessment_dir / "executive-readiness-brief.md", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "executive-readiness-brief", False, "validation raised an exception")
        errors.append(f"Executive readiness brief validation failed: {exc}")
    else:
        add_check(checks, "executive-readiness-brief", executive_brief.ok, executive_brief.summary())
        errors.extend(executive_brief.errors)
        warnings.extend(executive_brief.warnings)

    try:
        change_board_evidence = validate_change_board_evidence(assessment_dir / "change-board-evidence.md", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "change-board-evidence", False, "validation raised an exception")
        errors.append(f"Change-board evidence validation failed: {exc}")
    else:
        add_check(checks, "change-board-evidence", change_board_evidence.ok, change_board_evidence.summary())
        errors.extend(change_board_evidence.errors)
        warnings.extend(change_board_evidence.warnings)

    try:
        wave_summary = validate_wave_readiness_summary(assessment_dir / "wave-readiness-summary.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "wave-readiness-summary", False, "validation raised an exception")
        errors.append(f"Wave readiness summary validation failed: {exc}")
    else:
        add_check(checks, "wave-readiness-summary", wave_summary.ok, wave_summary.summary())
        errors.extend(wave_summary.errors)
        warnings.extend(wave_summary.warnings)

    try:
        wave_calendar = validate_wave_execution_calendar(assessment_dir / "wave-execution-calendar.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "wave-execution-calendar", False, "validation raised an exception")
        errors.append(f"Wave execution calendar validation failed: {exc}")
    else:
        add_check(checks, "wave-execution-calendar", wave_calendar.ok, wave_calendar.summary())
        errors.extend(wave_calendar.errors)
        warnings.extend(wave_calendar.warnings)

    try:
        partner_handoff = validate_partner_handoff_matrix(assessment_dir / "partner-handoff-matrix.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "partner-handoff-matrix", False, "validation raised an exception")
        errors.append(f"Partner handoff matrix validation failed: {exc}")
    else:
        add_check(checks, "partner-handoff-matrix", partner_handoff.ok, partner_handoff.summary())
        errors.extend(partner_handoff.errors)
        warnings.extend(partner_handoff.warnings)

    try:
        migration_waves = validate_migration_waves(assessment_dir / "migration-waves.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "migration-waves", False, "validation raised an exception")
        errors.append(f"Migration waves validation failed: {exc}")
    else:
        add_check(checks, "migration-waves", migration_waves.ok, migration_waves.summary())
        errors.extend(migration_waves.errors)
        warnings.extend(migration_waves.warnings)

    try:
        dependency_sequence = validate_dependency_sequence(assessment_dir / "dependency-sequence.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "dependency-sequence", False, "validation raised an exception")
        errors.append(f"Dependency sequence validation failed: {exc}")
    else:
        add_check(checks, "dependency-sequence", dependency_sequence.ok, dependency_sequence.summary())
        errors.extend(dependency_sequence.errors)
        warnings.extend(dependency_sequence.warnings)

    try:
        compatibility_research = validate_compatibility_research(assessment_dir / "compatibility-research.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "compatibility-research", False, "validation raised an exception")
        errors.append(f"Compatibility research validation failed: {exc}")
    else:
        add_check(checks, "compatibility-research", compatibility_research.ok, compatibility_research.summary())
        errors.extend(compatibility_research.errors)
        warnings.extend(compatibility_research.warnings)

    try:
        dependency_review = validate_dependency_review(assessment_dir / "dependency-review.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "dependency-review", False, "validation raised an exception")
        errors.append(f"Dependency review validation failed: {exc}")
    else:
        add_check(checks, "dependency-review", dependency_review.ok, dependency_review.summary())
        errors.extend(dependency_review.errors)
        warnings.extend(dependency_review.warnings)

    try:
        connectivity_checklist = validate_connectivity_checklist(assessment_dir / "connectivity-checklist.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "connectivity-checklist", False, "validation raised an exception")
        errors.append(f"Connectivity checklist validation failed: {exc}")
    else:
        add_check(checks, "connectivity-checklist", connectivity_checklist.ok, connectivity_checklist.summary())
        errors.extend(connectivity_checklist.errors)
        warnings.extend(connectivity_checklist.warnings)

    try:
        identity_cutover = validate_identity_cutover_plan(assessment_dir / "identity-cutover-plan.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "identity-cutover-plan", False, "validation raised an exception")
        errors.append(f"Identity cutover plan validation failed: {exc}")
    else:
        add_check(checks, "identity-cutover-plan", identity_cutover.ok, identity_cutover.summary())
        errors.extend(identity_cutover.errors)
        warnings.extend(identity_cutover.warnings)

    try:
        tools_driver = validate_tools_driver_readiness(assessment_dir / "tools-driver-readiness.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "tools-driver-readiness", False, "validation raised an exception")
        errors.append(f"Tools driver readiness validation failed: {exc}")
    else:
        add_check(checks, "tools-driver-readiness", tools_driver.ok, tools_driver.summary())
        errors.extend(tools_driver.errors)
        warnings.extend(tools_driver.warnings)

    try:
        storage_posture = validate_storage_posture(assessment_dir / "storage-posture.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "storage-posture", False, "validation raised an exception")
        errors.append(f"Storage posture validation failed: {exc}")
    else:
        add_check(checks, "storage-posture", storage_posture.ok, storage_posture.summary())
        errors.extend(storage_posture.errors)
        warnings.extend(storage_posture.warnings)

    try:
        recovery_readiness = validate_recovery_readiness(assessment_dir / "recovery-readiness.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "recovery-readiness", False, "validation raised an exception")
        errors.append(f"Recovery readiness validation failed: {exc}")
    else:
        add_check(checks, "recovery-readiness", recovery_readiness.ok, recovery_readiness.summary())
        errors.extend(recovery_readiness.errors)
        warnings.extend(recovery_readiness.warnings)

    try:
        rollback_plan = validate_rollback_plan(assessment_dir / "rollback-plan.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "rollback-plan", False, "validation raised an exception")
        errors.append(f"Rollback plan validation failed: {exc}")
    else:
        add_check(checks, "rollback-plan", rollback_plan.ok, rollback_plan.summary())
        errors.extend(rollback_plan.errors)
        warnings.extend(rollback_plan.warnings)

    try:
        move_staging_readiness = validate_move_staging_readiness(assessment_dir / "move-staging-readiness.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "move-staging-readiness", False, "validation raised an exception")
        errors.append(f"Move staging readiness validation failed: {exc}")
    else:
        add_check(checks, "move-staging-readiness", move_staging_readiness.ok, move_staging_readiness.summary())
        errors.extend(move_staging_readiness.errors)
        warnings.extend(move_staging_readiness.warnings)

    try:
        move_plan_brief = validate_move_plan_brief(
            assessment_dir / "move-plan-brief.md",
            assessment_dir / "nutanix-move-plan.csv",
            assessment_dir / "assessment.json",
        )
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "move-plan-brief", False, "validation raised an exception")
        errors.append(f"Move plan brief validation failed: {exc}")
    else:
        add_check(checks, "move-plan-brief", move_plan_brief.ok, move_plan_brief.summary())
        errors.extend(move_plan_brief.errors)
        warnings.extend(move_plan_brief.warnings)

    try:
        move_staging_brief = validate_move_staging_brief(assessment_dir / "move-staging-brief.md", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "move-staging-brief", False, "validation raised an exception")
        errors.append(f"Move staging brief validation failed: {exc}")
    else:
        add_check(checks, "move-staging-brief", move_staging_brief.ok, move_staging_brief.summary())
        errors.extend(move_staging_brief.errors)
        warnings.extend(move_staging_brief.warnings)

    try:
        execution_queue = validate_migration_execution_queue(assessment_dir / "migration-execution-queue.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "migration-execution-queue", False, "validation raised an exception")
        errors.append(f"Migration execution queue validation failed: {exc}")
    else:
        add_check(checks, "migration-execution-queue", execution_queue.ok, execution_queue.summary())
        errors.extend(execution_queue.errors)
        warnings.extend(execution_queue.warnings)

    try:
        prism_categories = validate_prism_category_mapping(assessment_dir / "prism-category-mapping.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "prism-category-mapping", False, "validation raised an exception")
        errors.append(f"Prism category mapping validation failed: {exc}")
    else:
        add_check(checks, "prism-category-mapping", prism_categories.ok, prism_categories.summary())
        errors.extend(prism_categories.errors)
        warnings.extend(prism_categories.warnings)

    try:
        stakeholder_comms = validate_stakeholder_comms(assessment_dir / "stakeholder-communication-plan.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "stakeholder-communication-plan", False, "validation raised an exception")
        errors.append(f"Stakeholder communication plan validation failed: {exc}")
    else:
        add_check(checks, "stakeholder-communication-plan", stakeholder_comms.ok, stakeholder_comms.summary())
        errors.extend(stakeholder_comms.errors)
        warnings.extend(stakeholder_comms.warnings)

    try:
        what_will_break = validate_what_will_break(assessment_dir / "what-will-break-report.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "what-will-break-report", False, "validation raised an exception")
        errors.append(f"What-will-break report validation failed: {exc}")
    else:
        add_check(checks, "what-will-break-report", what_will_break.ok, what_will_break.summary())
        errors.extend(what_will_break.errors)
        warnings.extend(what_will_break.warnings)

    try:
        what_will_break_brief = validate_what_will_break_brief(assessment_dir / "what-will-break-brief.md", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "what-will-break-brief", False, "validation raised an exception")
        errors.append(f"What-will-break brief validation failed: {exc}")
    else:
        add_check(checks, "what-will-break-brief", what_will_break_brief.ok, what_will_break_brief.summary())
        errors.extend(what_will_break_brief.errors)
        warnings.extend(what_will_break_brief.warnings)

    try:
        business_impact = validate_business_impact_summary(assessment_dir / "business-impact-summary.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "business-impact-summary", False, "validation raised an exception")
        errors.append(f"Business impact summary validation failed: {exc}")
    else:
        add_check(checks, "business-impact-summary", business_impact.ok, business_impact.summary())
        errors.extend(business_impact.errors)
        warnings.extend(business_impact.warnings)

    try:
        target_comparison = validate_target_readiness_comparison(assessment_dir / "target-readiness-comparison.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "target-readiness-comparison", False, "validation raised an exception")
        errors.append(f"Target readiness comparison validation failed: {exc}")
    else:
        add_check(checks, "target-readiness-comparison", target_comparison.ok, target_comparison.summary())
        errors.extend(target_comparison.errors)
        warnings.extend(target_comparison.warnings)

    try:
        risk_register = validate_risk_register(assessment_dir / "migration-risk-register.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "migration-risk-register", False, "validation raised an exception")
        errors.append(f"Migration risk register validation failed: {exc}")
    else:
        add_check(checks, "migration-risk-register", risk_register.ok, risk_register.summary())
        errors.extend(risk_register.errors)
        warnings.extend(risk_register.warnings)

    try:
        owner_risk = validate_owner_risk_summary(assessment_dir / "owner-risk-summary.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "owner-risk-summary", False, "validation raised an exception")
        errors.append(f"Owner risk summary validation failed: {exc}")
    else:
        add_check(checks, "owner-risk-summary", owner_risk.ok, owner_risk.summary())
        errors.extend(owner_risk.errors)
        warnings.extend(owner_risk.warnings)

    try:
        signoff_matrix = validate_signoff_matrix_contract(assessment_dir / "owner-signoff-matrix.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "owner-signoff-matrix", False, "validation raised an exception")
        errors.append(f"Owner sign-off matrix validation failed: {exc}")
    else:
        add_check(checks, "owner-signoff-matrix", signoff_matrix.ok, signoff_matrix.summary())
        errors.extend(signoff_matrix.errors)
        warnings.extend(signoff_matrix.warnings)

    try:
        approval_exceptions = validate_approval_exceptions(assessment_dir / "approval-exceptions.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "approval-exceptions", False, "validation raised an exception")
        errors.append(f"Approval exceptions validation failed: {exc}")
    else:
        add_check(checks, "approval-exceptions", approval_exceptions.ok, approval_exceptions.summary())
        errors.extend(approval_exceptions.errors)
        warnings.extend(approval_exceptions.warnings)

    try:
        remediation_baseline = validate_remediation_tracker_contract(assessment_dir / "remediation-tracker.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "remediation-tracker-baseline", False, "validation raised an exception")
        errors.append(f"Remediation tracker baseline validation failed: {exc}")
    else:
        add_check(checks, "remediation-tracker-baseline", remediation_baseline.ok, remediation_baseline.summary())
        errors.extend(remediation_baseline.errors)
        warnings.extend(remediation_baseline.warnings)

    try:
        validation_checklist = validate_validation_checklist(assessment_dir / "pre-post-validation-checklist.md")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "pre-post-validation-checklist", False, "validation raised an exception")
        errors.append(f"Pre/post validation checklist validation failed: {exc}")
    else:
        add_check(checks, "pre-post-validation-checklist", validation_checklist.ok, validation_checklist.summary())
        errors.extend(validation_checklist.errors)
        warnings.extend(validation_checklist.warnings)

    try:
        move_lab_closure = validate_move_lab_closure_checklist(assessment_dir / "move-lab-closure-checklist.md")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "move-lab-closure-checklist", False, "validation raised an exception")
        errors.append(f"Move lab closure checklist validation failed: {exc}")
    else:
        add_check(checks, "move-lab-closure-checklist", move_lab_closure.ok, move_lab_closure.summary())
        errors.extend(move_lab_closure.errors)
        warnings.extend(move_lab_closure.warnings)

    try:
        move_lab_request = validate_move_lab_evidence_request(assessment_dir / "move-lab-evidence-request.md")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "move-lab-evidence-request", False, "validation raised an exception")
        errors.append(f"Move lab evidence request validation failed: {exc}")
    else:
        add_check(checks, "move-lab-evidence-request", move_lab_request.ok, move_lab_request.summary())
        errors.extend(move_lab_request.errors)
        warnings.extend(move_lab_request.warnings)

    try:
        source_endpoint_request = validate_source_endpoint_evidence_request(assessment_dir / "source-endpoint-evidence-request.md")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "source-endpoint-evidence-request", False, "validation raised an exception")
        errors.append(f"Source endpoint evidence request validation failed: {exc}")
    else:
        add_check(checks, "source-endpoint-evidence-request", source_endpoint_request.ok, source_endpoint_request.summary())
        errors.extend(source_endpoint_request.errors)
        warnings.extend(source_endpoint_request.warnings)

    try:
        workload_validation = validate_workload_validation_checklist(assessment_dir / "workload-validation-checklist.csv", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "workload-validation-checklist", False, "validation raised an exception")
        errors.append(f"Workload validation checklist validation failed: {exc}")
    else:
        add_check(checks, "workload-validation-checklist", workload_validation.ok, workload_validation.summary())
        errors.extend(workload_validation.errors)
        warnings.extend(workload_validation.warnings)

    try:
        migration_runbook = validate_migration_runbook(assessment_dir / "migration-runbook.md", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "migration-runbook", False, "validation raised an exception")
        errors.append(f"Migration runbook validation failed: {exc}")
    else:
        add_check(checks, "migration-runbook", migration_runbook.ok, migration_runbook.summary())
        errors.extend(migration_runbook.errors)
        warnings.extend(migration_runbook.warnings)

    try:
        operations_console = validate_operations_console(assessment_dir / "operations-console.html", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "operations-console", False, "validation raised an exception")
        errors.append(f"Operations console validation failed: {exc}")
    else:
        add_check(checks, "operations-console", operations_console.ok, operations_console.summary())
        errors.extend(operations_console.errors)
        warnings.extend(operations_console.warnings)

    try:
        operator_portal = validate_operator_portal(assessment_dir / "operator-portal.html", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "operator-portal", False, "validation raised an exception")
        errors.append(f"Operator portal validation failed: {exc}")
    else:
        add_check(checks, "operator-portal", operator_portal.ok, operator_portal.summary())
        errors.extend(operator_portal.errors)
        warnings.extend(operator_portal.warnings)

    try:
        operator_report = validate_operator_report(assessment_dir / "operator-report.html", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "operator-report", False, "validation raised an exception")
        errors.append(f"Operator report validation failed: {exc}")
    else:
        add_check(checks, "operator-report", operator_report.ok, operator_report.summary())
        errors.extend(operator_report.errors)
        warnings.extend(operator_report.warnings)

    try:
        operator_dashboard = validate_operator_dashboard(assessment_dir / "operator-dashboard.html", assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "operator-dashboard", False, "validation raised an exception")
        errors.append(f"Operator dashboard validation failed: {exc}")
    else:
        add_check(checks, "operator-dashboard", operator_dashboard.ok, operator_dashboard.summary())
        errors.extend(operator_dashboard.errors)
        warnings.extend(operator_dashboard.warnings)

    coverage_path = assessment_dir / "inventory-coverage.csv"
    move_plan_path = assessment_dir / "nutanix-move-plan.csv"
    try:
        coverage_result = validate_inventory_coverage_csv(coverage_path, move_plan_path)
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "inventory-coverage", False, "validation raised an exception")
        errors.append(f"Inventory coverage validation failed: {exc}")
    else:
        add_check(checks, "inventory-coverage", coverage_result.ok, coverage_result.summary())
        errors.extend(coverage_result.errors)
        warnings.extend(coverage_result.warnings)

    try:
        evidence = verify_evidence(assessment_dir)
    except Exception as exc:  # noqa: BLE001 - gate should report all verifier failures as data.
        add_check(checks, "evidence-manifest", False, "verification raised an exception")
        errors.append(f"Evidence verification failed: {exc}")
    else:
        add_check(checks, "evidence-manifest", evidence.ok, evidence.summary())
        errors.extend(evidence.errors)

    try:
        redaction = review_evidence_dir(assessment_dir)
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "redaction-review", False, "review raised an exception")
        errors.append(f"Redaction review failed: {exc}")
    else:
        add_check(checks, "redaction-review", redaction.ok, redaction.summary())
        errors.extend(redaction.findings)

    move_plan_path = assessment_dir / "nutanix-move-plan.csv"
    try:
        move_plan = validate_move_plan(move_plan_path, assessment_dir / "assessment.json")
    except Exception as exc:  # noqa: BLE001
        add_check(checks, "move-plan", False, "validation raised an exception")
        errors.append(f"Move plan validation failed: {exc}")
    else:
        add_check(checks, "move-plan", move_plan.ok, move_plan.summary())
        errors.extend(move_plan.errors)
        warnings.extend(move_plan.warnings)
        if move_plan.included_count == 0:
            errors.append("Move plan has no included workloads")

    network_mapping_path = assessment_dir / "target-network-mapping.csv"
    source_network_path = assessment_dir / "source-network-validation.csv"
    if source_network_path.exists():
        try:
            source_network = validate_source_network_validation_csv(source_network_path)
        except Exception as exc:  # noqa: BLE001
            add_check(checks, "source-network-validation", False, "validation raised an exception")
            errors.append(f"Source network validation failed: {exc}")
        else:
            add_check(checks, "source-network-validation", source_network.ok, source_network.summary())
            errors.extend(source_network.errors)
            warnings.extend(source_network.warnings)
    else:
        add_check(checks, "source-network-validation", True, "not provided; source network inventory proof not evaluated")
        warnings.append("Source network validation proof not provided; Move source network hints not evaluated")

    if network_mapping_path.exists():
        try:
            network_mapping = validate_network_mapping_csv(network_mapping_path)
        except Exception as exc:  # noqa: BLE001
            add_check(checks, "network-mapping", False, "validation raised an exception")
            errors.append(f"Network mapping validation failed: {exc}")
        else:
            add_check(checks, "network-mapping", network_mapping.ok, network_mapping.summary())
            errors.extend(network_mapping.errors)
            warnings.extend(network_mapping.warnings)
    else:
        add_check(checks, "network-mapping", True, "not provided; target network mappings not evaluated")
        warnings.append("Target network mapping proof not provided; Move network mappings not evaluated")

    capacity_fit_path = assessment_dir / "target-capacity-fit.csv"
    if capacity_fit_path.exists():
        try:
            capacity_fit = validate_capacity_fit_csv(capacity_fit_path)
        except Exception as exc:  # noqa: BLE001
            add_check(checks, "capacity-fit", False, "validation raised an exception")
            errors.append(f"Capacity fit validation failed: {exc}")
        else:
            add_check(checks, "capacity-fit", capacity_fit.ok, capacity_fit.summary())
            errors.extend(capacity_fit.errors)
            warnings.extend(capacity_fit.warnings)
    else:
        add_check(checks, "capacity-fit", True, "not provided; target capacity fit not evaluated")
        warnings.append("Target capacity fit not provided; target cluster headroom not evaluated")

    target_reconciliation_path = assessment_dir / "target-reconciliation.csv"
    if target_reconciliation_path.exists():
        try:
            target_reconciliation = validate_target_reconciliation_csv(target_reconciliation_path)
        except Exception as exc:  # noqa: BLE001
            add_check(checks, "target-reconciliation", False, "validation raised an exception")
            errors.append(f"Target reconciliation validation failed: {exc}")
        else:
            add_check(checks, "target-reconciliation", target_reconciliation.ok, target_reconciliation.summary())
            errors.extend(target_reconciliation.errors)
            warnings.extend(target_reconciliation.warnings)
    else:
        add_check(checks, "target-reconciliation", True, "not provided; Prism inventory collision check not evaluated")
        warnings.append("Prism target inventory reconciliation not provided; name collisions not evaluated")

    if bundle_path:
        try:
            bundle = verify_evidence_bundle(bundle_path)
        except Exception as exc:  # noqa: BLE001
            add_check(checks, "evidence-bundle", False, "bundle verification raised an exception")
            errors.append(f"Evidence bundle verification failed: {exc}")
        else:
            add_check(checks, "evidence-bundle", bundle.ok, bundle.summary())
            errors.extend(bundle.errors)
    else:
        add_check(checks, "evidence-bundle", True, "not provided; directory manifest verified")
        warnings.append("Evidence bundle path not provided; only assessment directory was verified")

    if validation_results_path:
        try:
            validation = validate_validation_results(validation_results_path)
        except Exception as exc:  # noqa: BLE001
            add_check(checks, "validation-results", False, "validation raised an exception")
            errors.append(f"Validation results failed: {exc}")
        else:
            add_check(checks, "validation-results", validation.ok, validation.summary())
            errors.extend(validation.errors)
            warnings.extend(validation.warnings)
    else:
        add_check(checks, "validation-results", True, "not provided; pre-change gate only")
        warnings.append("Validation results not provided; post-migration closure gate not evaluated")

    if remediation_tracker_path:
        try:
            remediation = validate_remediation_tracker(remediation_tracker_path)
        except Exception as exc:  # noqa: BLE001
            add_check(checks, "remediation-tracker", False, "validation raised an exception")
            errors.append(f"Remediation tracker validation failed: {exc}")
        else:
            add_check(checks, "remediation-tracker", remediation.ok, remediation.summary())
            errors.extend(remediation.errors)
            warnings.extend(remediation.warnings)
    else:
        add_check(checks, "remediation-tracker", True, "not provided; remediation closure not evaluated")
        warnings.append("Remediation tracker not provided; remediation closure gate not evaluated")

    if signoffs_path:
        try:
            signoffs = validate_signoffs(signoffs_path, allow_pending=allow_pending_signoffs)
        except Exception as exc:  # noqa: BLE001
            add_check(checks, "signoffs", False, "validation raised an exception")
            errors.append(f"Sign-off validation failed: {exc}")
        else:
            add_check(checks, "signoffs", signoffs.ok, signoffs.summary())
            errors.extend(signoffs.errors)
            warnings.extend(signoffs.warnings)
    else:
        add_check(checks, "signoffs", True, "not provided; owner approvals not evaluated")
        warnings.append("Sign-off matrix not provided; owner approval closure gate not evaluated")

    if approval_exceptions_path:
        try:
            exception_approvals = validate_approval_exception_approvals(approval_exceptions_path, assessment_path=assessment_dir / "assessment.json")
        except Exception as exc:  # noqa: BLE001
            add_check(checks, "approval-exception-approvals", False, "validation raised an exception")
            errors.append(f"Approval exception approval validation failed: {exc}")
        else:
            add_check(checks, "approval-exception-approvals", exception_approvals.ok, exception_approvals.summary())
            errors.extend(exception_approvals.errors)
            warnings.extend(exception_approvals.warnings)
    else:
        add_check(checks, "approval-exception-approvals", True, "not provided; exception approvals not evaluated")
        warnings.append("Approval exception approvals not provided; risk acceptance closure gate not evaluated")

    if operator_review_path:
        try:
            operator_review = validate_operator_review(
                operator_review_path,
                allow_draft=allow_draft_operator_review,
                assessment_dir=assessment_dir,
            )
        except Exception as exc:  # noqa: BLE001
            add_check(checks, "operator-review", False, "validation raised an exception")
            errors.append(f"Operator review validation failed: {exc}")
        else:
            add_check(checks, "operator-review", operator_review.ok, operator_review.summary())
            errors.extend(operator_review.errors)
            warnings.extend(operator_review.warnings)
    else:
        add_check(checks, "operator-review", True, "not provided; human assessment review not evaluated")
        warnings.append("Operator review not provided; human assessment review evidence not evaluated")

    if move_lab_capture_validation_path:
        try:
            move_lab_capture = validate_move_lab_capture_kit_validation_file(move_lab_capture_validation_path)
        except Exception as exc:  # noqa: BLE001
            add_check(checks, "move-lab-capture-kit", False, "validation raised an exception")
            errors.append(f"Move lab capture kit validation failed: {exc}")
        else:
            add_check(checks, "move-lab-capture-kit", move_lab_capture.ok, move_lab_capture.summary())
            errors.extend(move_lab_capture.errors)
            warnings.extend(move_lab_capture.warnings)
    else:
        add_check(checks, "move-lab-capture-kit", True, "not provided; approved lab capture preflight not evaluated")
        warnings.append("Move lab capture kit validation not provided; approved lab capture preflight not evaluated")

    if move_lab_proof_path:
        try:
            move_lab_proof = validate_move_lab_proof_validation_file(move_lab_proof_path, require_approved_lab=True)
        except Exception as exc:  # noqa: BLE001
            add_check(checks, "move-lab-proof", False, "validation raised an exception")
            errors.append(f"Move lab proof validation failed: {exc}")
        else:
            add_check(checks, "move-lab-proof", move_lab_proof.ok, move_lab_proof.summary())
            errors.extend(move_lab_proof.errors)
            warnings.extend(move_lab_proof.warnings)
        if move_lab_evidence_intake_path:
            try:
                move_lab_intake = validate_move_lab_evidence_intake_validation_file(move_lab_evidence_intake_path)
            except Exception as exc:  # noqa: BLE001
                add_check(checks, "move-lab-evidence-intake", False, "validation raised an exception")
                errors.append(f"Move lab evidence intake validation failed: {exc}")
            else:
                add_check(checks, "move-lab-evidence-intake", move_lab_intake.ok and move_lab_intake.status == "pass", move_lab_intake.summary())
                errors.extend(move_lab_intake.errors)
                warnings.extend(move_lab_intake.warnings)
        else:
            add_check(checks, "move-lab-evidence-intake", False, "missing; approved Move lab proof requires final evidence intake")
            errors.append("Move lab evidence intake is required when approved Move lab proof is supplied")
    else:
        add_check(checks, "move-lab-proof", True, "not provided; approved Move lab appliance proof not evaluated")
        warnings.append("Approved Move lab proof not provided; Nutanix Move appliance behavior not evaluated")
        if move_lab_evidence_intake_path:
            try:
                move_lab_intake = validate_move_lab_evidence_intake_validation_file(move_lab_evidence_intake_path)
            except Exception as exc:  # noqa: BLE001
                add_check(checks, "move-lab-evidence-intake", False, "validation raised an exception")
                errors.append(f"Move lab evidence intake validation failed: {exc}")
            else:
                add_check(checks, "move-lab-evidence-intake", move_lab_intake.ok and move_lab_intake.status == "pass", move_lab_intake.summary())
                errors.extend(move_lab_intake.errors)
                warnings.extend(move_lab_intake.warnings)

    status = "pass" if not errors else "fail"
    return ChangeGateResult(status, tuple(checks), tuple(errors), tuple(warnings))


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})
