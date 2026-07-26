from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .assessment_intake import validate_assessment_intake


MVP_AUDIT_SCHEMA_VERSION = "nmrcp_mvp_readiness_audit_v1"

REQUIRED_LIVE_ENDPOINT_PROOF_CHECKS: tuple[str, ...] = (
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


REQUIREMENTS: tuple[dict[str, Any], ...] = (
    {
        "id": "read_only_collection",
        "requirement": "Connect to vCenter and Prism Central in read-only mode.",
        "files": (
            "src/nmrcp/connectors.py",
            "src/nmrcp/collection_workflow.py",
            "src/nmrcp/live_readiness.py",
            "src/nmrcp/assessment_intake.py",
            "src/nmrcp/source_collection_plan.py",
            "tests/test_connectors.py",
            "tests/test_collection_workflow.py",
            "tests/test_live_readiness.py",
            "tests/test_assessment_intake.py",
            "tests/test_source_collection_plan.py",
            "scripts/live_collector_smoke.py",
            "docs/operations/source-collection-workflow.md",
            "docs/operations/live-readiness.md",
            "docs/operations/assessment-intake.md",
            "docs/operations/source-collection-plan.md",
        ),
        "commands": (
            "python -m nmrcp.cli live-readiness --out outputs/live-readiness.json",
            "python -m nmrcp.cli validate-assessment-intake --intake outputs/assessment-intake.csv",
            "python -m nmrcp.cli source-collection-plan --intake outputs/assessment-intake.csv --out outputs/source-collection-plan.md",
            "python -m nmrcp.cli collect-sources --assessment-intake outputs/assessment-intake.csv --out-dir outputs/source-collection",
            "python scripts/live_collector_smoke.py",
        ),
        "external_gap": "Real vCenter and Prism Central endpoints still need approved lab/customer validation.",
    },
    {
        "id": "inventory_scope",
        "requirement": "Inventory VMs, networks, storage, guest OS, snapshots, tools/drivers, tags, ownership, and dependencies.",
        "files": (
            "src/nmrcp/inventory.py",
            "src/nmrcp/rvtools.py",
            "src/nmrcp/metadata.py",
            "src/nmrcp/dependencies.py",
            "src/nmrcp/dependency_hints.py",
            "src/nmrcp/dependency_review.py",
            "src/nmrcp/connectivity_checklist.py",
            "src/nmrcp/identity_cutover_plan.py",
            "src/nmrcp/guest_identity.py",
            "src/nmrcp/storage_posture.py",
            "src/nmrcp/recovery_readiness.py",
            "src/nmrcp/rollback_plan.py",
            "src/nmrcp/tools_driver_readiness.py",
            "src/nmrcp/move_staging_readiness.py",
            "src/nmrcp/prism_categories.py",
            "src/nmrcp/stakeholder_comms.py",
            "src/nmrcp/what_will_break.py",
            "tests/test_inventory.py",
            "tests/test_rvtools.py",
            "tests/test_metadata.py",
            "tests/test_dependencies.py",
            "tests/test_dependency_review.py",
            "tests/test_connectivity_checklist.py",
            "tests/test_identity_cutover_plan.py",
            "tests/test_storage_posture.py",
            "tests/test_recovery_readiness.py",
            "tests/test_rollback_plan.py",
            "tests/test_tools_driver_readiness.py",
            "tests/test_move_staging_readiness.py",
            "tests/test_prism_categories.py",
            "tests/test_stakeholder_comms.py",
            "tests/test_what_will_break.py",
            "docs/operations/readiness-signals.md",
            "docs/operations/metadata-enrichment.md",
            "docs/operations/application-map-import.md",
            "docs/operations/dependency-review.md",
            "docs/operations/connectivity-checklist.md",
            "docs/operations/identity-cutover-plan.md",
            "docs/operations/storage-posture.md",
            "docs/operations/recovery-readiness.md",
            "docs/operations/rollback-plan.md",
            "docs/operations/tools-driver-readiness.md",
            "docs/operations/move-staging-readiness.md",
            "docs/operations/prism-category-mapping.md",
            "docs/operations/stakeholder-communication-plan.md",
            "docs/operations/what-will-break-report.md",
        ),
        "commands": (
            "python -m nmrcp.cli validate-inventory --inventory examples/sample_inventory.json",
            "python -m nmrcp.cli import-rvtools --dir examples/rvtools --out outputs/rvtools-inventory.json",
            "python -m nmrcp.cli import-cmdb-metadata --export examples/sample_cmdb_export.csv --out outputs/cmdb-metadata.csv",
        ),
    },
    {
        "id": "readiness_scoring",
        "requirement": "Score each workload for AHV/NC2 migration readiness.",
        "files": (
            "src/nmrcp/scoring.py",
            "src/nmrcp/compatibility_research.py",
            "src/nmrcp/waves.py",
            "tests/test_scoring.py",
            "tests/test_compatibility_research.py",
            "tests/test_waves_and_evidence.py",
            "examples/sample_readiness_policy.json",
            "docs/operations/readiness-policy.md",
            "docs/operations/compatibility-research.md",
            "docs/operations/target-readiness-comparison.md",
        ),
        "commands": (
            "python -m nmrcp.cli assess --inventory examples/sample_inventory.json --out outputs/sample-assessment",
            "python -m nmrcp.cli assess --inventory examples/sample_inventory.json --target nc2 --out outputs/sample-nc2-assessment",
        ),
    },
    {
        "id": "waves_and_change_evidence",
        "requirement": "Generate migration waves and change-board evidence.",
        "files": (
            "src/nmrcp/evidence.py",
            "src/nmrcp/waves.py",
            "src/nmrcp/wave_execution_calendar.py",
            "src/nmrcp/operator_portal.py",
            "src/nmrcp/operations_console.py",
            "tests/test_waves_and_evidence.py",
            "tests/test_wave_execution_calendar.py",
            "tests/test_operator_portal.py",
            "tests/test_operations_console.py",
            "docs/operations/assessment-workflow.md",
            "docs/operations/change-gate.md",
            "docs/operations/wave-execution-calendar.md",
            "docs/operations/operator-portal.md",
            "docs/operations/operations-console.md",
        ),
        "artifacts": (
            "migration-waves.csv",
            "wave-readiness-summary.csv",
            "wave-execution-calendar.csv",
            "change-board-evidence.md",
            "migration-runbook.md",
            "compatibility-research.csv",
            "dependency-review.csv",
            "connectivity-checklist.csv",
            "identity-cutover-plan.csv",
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
        ),
    },
    {
        "id": "move_ready_plan",
        "requirement": "Export a Nutanix Move-ready plan plus pre/post validation checklist.",
        "files": (
            "src/nmrcp/move_plan.py",
            "src/nmrcp/move_plan_brief.py",
            "src/nmrcp/move_payload.py",
            "src/nmrcp/source_networks.py",
            "src/nmrcp/move_lab_capture_kit.py",
            "src/nmrcp/move_lab_closure_checklist.py",
            "src/nmrcp/move_lab_evidence_intake.py",
            "src/nmrcp/move_lab_evidence_request.py",
            "src/nmrcp/move_lab_proof.py",
            "src/nmrcp/move_lab_runbook.py",
            "src/nmrcp/move_lab_transcript.py",
            "src/nmrcp/validation_results.py",
            "src/nmrcp/move_submit_readiness.py",
            "src/nmrcp/workload_validation_checklist.py",
            "src/nmrcp/migration_execution_queue.py",
            "tests/test_move_plan.py",
            "tests/test_move_plan_brief.py",
            "tests/test_move_payload.py",
            "tests/test_source_networks.py",
            "tests/test_move_lab_proof.py",
            "tests/test_move_lab_closure_checklist.py",
            "tests/test_move_lab_evidence_intake.py",
            "tests/test_move_lab_evidence_request.py",
            "tests/test_move_lab_runbook.py",
            "tests/test_move_lab_transcript.py",
            "tests/test_validation_results.py",
            "tests/test_move_submit_readiness.py",
            "tests/test_workload_validation_checklist.py",
            "tests/test_migration_execution_queue.py",
            "docs/operations/move-plan-contract.md",
            "docs/operations/move-plan-brief.md",
            "docs/operations/move-api-payload-dry-run.md",
            "docs/operations/source-network-validation.md",
            "docs/operations/move-lab-proof.md",
            "docs/operations/move-lab-closure-checklist.md",
            "docs/operations/move-lab-evidence-intake.md",
            "docs/operations/move-lab-evidence-request.md",
            "docs/operations/move-lab-runbook.md",
            "docs/operations/move-lab-transcript.md",
            "docs/operations/validation-results.md",
            "docs/operations/move-submit-readiness.md",
            "docs/operations/workload-validation-checklist.md",
            "docs/operations/migration-execution-queue.md",
        ),
        "artifacts": (
            "nutanix-move-plan.csv",
            "move-plan-brief.md",
            "pre-post-validation-checklist.md",
            "move-lab-closure-checklist.md",
            "move-lab-evidence-request.md",
            "workload-validation-checklist.csv",
            "migration-execution-queue.csv",
            "source-network-validation.csv",
            "move-api-payload.dry-run.json",
        ),
        "external_gap": "Real Nutanix Move appliance API behavior is not validated; current payload remains dry-run review evidence.",
    },
    {
        "id": "local_secret_redaction",
        "requirement": "Keep all secrets local and redact evidence by default.",
        "files": (
            "src/nmrcp/redaction.py",
            "src/nmrcp/redaction_review.py",
            "src/nmrcp/collection_audit.py",
            "src/nmrcp/assessment_intake.py",
            "src/nmrcp/source_collection_plan.py",
            "src/nmrcp/source_endpoint_evidence_request.py",
            "scripts/security_scan.py",
            "tests/test_assessment_intake.py",
            "tests/test_source_collection_plan.py",
            "tests/test_source_endpoint_evidence_request.py",
            "tests/test_redaction_review.py",
            "tests/test_collection_audit.py",
            "examples/sample_assessment_intake.csv",
            "examples/sample_cmdb_export.csv",
            "docs/operations/assessment-intake.md",
            "docs/operations/source-collection-plan.md",
            "docs/operations/source-endpoint-evidence-request.md",
            "docs/security/README.md",
            "docs/operations/evidence-redaction-review.md",
            "SECURITY_REVIEW.md",
        ),
        "commands": (
            "python -m nmrcp.cli validate-assessment-intake --intake examples/sample_assessment_intake.csv",
            "python -m nmrcp.cli validate-source-collection-plan --plan outputs/source-collection-plan.md --intake examples/sample_assessment_intake.csv",
            "python scripts/security_scan.py",
            "python -m nmrcp.cli review-evidence --dir outputs/sample-assessment",
        ),
    },
    {
        "id": "handoff_and_review",
        "requirement": "Package validated evidence, owner approvals, remediation closure, and operator review for handoff.",
        "files": (
            "src/nmrcp/change_gate.py",
            "src/nmrcp/handoff_package.py",
            "src/nmrcp/partner_handoff_matrix.py",
            "src/nmrcp/operator_review.py",
            "src/nmrcp/gate_summary.py",
            "src/nmrcp/approval_exceptions.py",
            "src/nmrcp/warning_acceptance.py",
            "src/nmrcp/launch_readiness.py",
            "tests/test_change_gate.py",
            "tests/test_handoff_package.py",
            "tests/test_partner_handoff_matrix.py",
            "tests/test_operator_review.py",
            "tests/test_approval_exceptions.py",
            "tests/test_warning_acceptance.py",
            "tests/test_launch_readiness.py",
            "docs/operations/handoff-package.md",
            "docs/operations/partner-handoff-matrix.md",
            "docs/operations/operator-review.md",
            "docs/operations/operator-gate-summary.md",
            "docs/operations/approval-exceptions.md",
            "docs/operations/change-gate-warning-acceptance.md",
            "docs/operations/launch-readiness-report.md",
        ),
        "commands": (
            "python -m nmrcp.cli change-gate --dir outputs/sample-assessment",
            "python -m nmrcp.cli package-handoff --dir outputs/sample-assessment --out outputs/sample-handoff-package.zip",
            "python -m nmrcp.cli launch-readiness-report --package outputs/mvp-proof-package.zip --out outputs/launch-readiness-report.md",
        ),
    },
)


@dataclass(frozen=True)
class RequirementAudit:
    id: str
    requirement: str
    status: str
    evidence_files: tuple[str, ...]
    missing_files: tuple[str, ...]
    artifact_names: tuple[str, ...]
    commands: tuple[str, ...]
    warnings: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "requirement": self.requirement,
            "status": self.status,
            "evidence_files": list(self.evidence_files),
            "missing_files": list(self.missing_files),
            "artifact_names": list(self.artifact_names),
            "commands": list(self.commands),
            "warnings": list(self.warnings),
            "errors": list(self.errors),
        }


@dataclass(frozen=True)
class MvpAudit:
    status: str
    repo_root: str
    generated_at: str
    requirements: tuple[RequirementAudit, ...]

    @property
    def ok(self) -> bool:
        return not any(requirement.errors for requirement in self.requirements)

    def summary(self) -> str:
        counts = self.counts()
        return (
            f"{self.status.upper()}: pass={counts['pass']}, partial={counts['partial']}, "
            f"fail={counts['fail']}, requirements={len(self.requirements)}"
        )

    def counts(self) -> dict[str, int]:
        statuses = {"pass": 0, "partial": 0, "fail": 0}
        for requirement in self.requirements:
            statuses[requirement.status] = statuses.get(requirement.status, 0) + 1
        return statuses

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MVP_AUDIT_SCHEMA_VERSION,
            "status": self.status,
            "repo_root": self.repo_root,
            "generated_at": self.generated_at,
            "summary": self.counts(),
            "requirements": [requirement.to_dict() for requirement in self.requirements],
        }


def audit_mvp(
    repo_root: Path,
    assessment_dir: Path | None = None,
    assessment_intake_path: Path | None = None,
    live_proof_path: Path | None = None,
    move_proof_path: Path | None = None,
    evidence_bundle_path: Path | None = None,
    validation_results_path: Path | None = None,
    remediation_tracker_path: Path | None = None,
    signoffs_path: Path | None = None,
    approval_exceptions_path: Path | None = None,
    operator_review_path: Path | None = None,
    move_lab_capture_validation_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
    warning_acceptance_path: Path | None = None,
) -> MvpAudit:
    requirement_results = tuple(
        audit_requirement(
            repo_root,
            requirement,
            assessment_dir,
            assessment_intake_path=assessment_intake_path,
            live_proof_path=live_proof_path,
            move_proof_path=move_proof_path,
            evidence_bundle_path=evidence_bundle_path,
            validation_results_path=validation_results_path,
            remediation_tracker_path=remediation_tracker_path,
            signoffs_path=signoffs_path,
            approval_exceptions_path=approval_exceptions_path,
            operator_review_path=operator_review_path,
            move_lab_capture_validation_path=move_lab_capture_validation_path,
            move_lab_evidence_intake_path=move_lab_evidence_intake_path,
            warning_acceptance_path=warning_acceptance_path,
        )
        for requirement in REQUIREMENTS
    )
    status = "fail" if any(result.errors for result in requirement_results) else (
        "partial" if any(result.warnings for result in requirement_results) else "pass"
    )
    return MvpAudit(
        status=status,
        repo_root=str(repo_root),
        generated_at=datetime.now(UTC).isoformat(),
        requirements=requirement_results,
    )


def audit_requirement(
    repo_root: Path,
    requirement: dict[str, Any],
    assessment_dir: Path | None,
    assessment_intake_path: Path | None = None,
    live_proof_path: Path | None = None,
    move_proof_path: Path | None = None,
    evidence_bundle_path: Path | None = None,
    validation_results_path: Path | None = None,
    remediation_tracker_path: Path | None = None,
    signoffs_path: Path | None = None,
    approval_exceptions_path: Path | None = None,
    operator_review_path: Path | None = None,
    move_lab_capture_validation_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
    warning_acceptance_path: Path | None = None,
) -> RequirementAudit:
    files = tuple(str(path) for path in requirement.get("files", ()))
    missing = tuple(path for path in files if not (repo_root / path).exists())
    artifacts = tuple(str(path) for path in requirement.get("artifacts", ()))
    missing_artifacts = tuple(
        artifact for artifact in artifacts if assessment_dir is not None and not (assessment_dir / artifact).exists()
    )
    errors = tuple(
        [*(f"Missing evidence file: {path}" for path in missing), *(f"Missing assessment artifact: {path}" for path in missing_artifacts)]
    )
    warnings = tuple([requirement["external_gap"]] if requirement.get("external_gap") else [])
    if assessment_dir is not None and (assessment_dir / "assessment.json").exists():
        contract_errors, contract_warnings = validate_generated_contracts(
            requirement["id"],
            assessment_dir,
            evidence_bundle_path=evidence_bundle_path,
            validation_results_path=validation_results_path,
            remediation_tracker_path=remediation_tracker_path,
            signoffs_path=signoffs_path,
            approval_exceptions_path=approval_exceptions_path,
            operator_review_path=operator_review_path,
            move_lab_capture_validation_path=move_lab_capture_validation_path,
            move_lab_proof_path=move_proof_path,
            move_lab_evidence_intake_path=move_lab_evidence_intake_path,
            warning_acceptance_path=warning_acceptance_path,
        )
        errors = errors + contract_errors
        warnings = warnings + contract_warnings
    if requirement["id"] == "handoff_and_review" and warning_acceptance_path:
        files = files + (str(warning_acceptance_path),)
    if requirement["id"] == "read_only_collection" and live_proof_path:
        live_proof_errors = validate_live_endpoint_proof_validation_path(live_proof_path)
        if live_proof_errors:
            errors = errors + tuple(f"Live endpoint proof invalid: {error}" for error in live_proof_errors)
        else:
            warnings = tuple(warning for warning in warnings if "Real vCenter and Prism Central endpoints" not in warning)
            files = files + (str(live_proof_path),)
        if assessment_intake_path:
            intake = validate_assessment_intake(assessment_intake_path)
            if intake.ok:
                files = files + (str(assessment_intake_path),)
            else:
                errors = errors + tuple(f"Assessment intake invalid: {error}" for error in intake.errors)
        elif not live_proof_errors:
            warnings = warnings + ("Assessment intake not provided; collection kickoff acknowledgements are not bound to live proof.",)
    if requirement["id"] == "move_ready_plan" and move_proof_path:
        from .move_lab_proof import validate_move_lab_proof_validation_file

        move_proof = validate_move_lab_proof_validation_file(move_proof_path, require_approved_lab=True)
        if not move_proof.ok:
            errors = errors + tuple(f"Move lab proof invalid: {error}" for error in move_proof.errors)
        else:
            warnings = tuple(warning for warning in warnings if "Real Nutanix Move appliance" not in warning)
            files = files + (str(move_proof_path),)
    status = "fail" if errors else "partial" if warnings else "pass"
    return RequirementAudit(
        id=str(requirement["id"]),
        requirement=str(requirement["requirement"]),
        status=status,
        evidence_files=files,
        missing_files=missing + missing_artifacts,
        artifact_names=artifacts,
        commands=tuple(str(command) for command in requirement.get("commands", ())),
        warnings=warnings,
        errors=errors,
    )


def validate_generated_contracts(
    requirement_id: str,
    assessment_dir: Path,
    *,
    evidence_bundle_path: Path | None = None,
    validation_results_path: Path | None = None,
    remediation_tracker_path: Path | None = None,
    signoffs_path: Path | None = None,
    approval_exceptions_path: Path | None = None,
    operator_review_path: Path | None = None,
    move_lab_capture_validation_path: Path | None = None,
    move_lab_proof_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
    warning_acceptance_path: Path | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if requirement_id == "waves_and_change_evidence":
        return validate_waves_and_evidence_contracts(assessment_dir)
    if requirement_id == "move_ready_plan":
        return validate_move_ready_contracts(assessment_dir)
    if requirement_id == "handoff_and_review":
        return validate_handoff_contracts(
            assessment_dir,
            evidence_bundle_path=evidence_bundle_path,
            validation_results_path=validation_results_path,
            remediation_tracker_path=remediation_tracker_path,
            signoffs_path=signoffs_path,
            approval_exceptions_path=approval_exceptions_path,
            operator_review_path=operator_review_path,
            move_lab_capture_validation_path=move_lab_capture_validation_path,
            move_lab_proof_path=move_lab_proof_path,
            move_lab_evidence_intake_path=move_lab_evidence_intake_path,
            warning_acceptance_path=warning_acceptance_path,
        )
    return (), ()


def validate_waves_and_evidence_contracts(assessment_dir: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    from .approval_exceptions import validate_approval_exceptions
    from .business_impact import validate_business_impact_summary
    from .change_board_evidence import validate_change_board_evidence
    from .compatibility_research import validate_compatibility_research
    from .connectivity_checklist import validate_connectivity_checklist
    from .dependency_review import validate_dependency_review
    from .identity_cutover_plan import validate_identity_cutover_plan
    from .executive_brief import validate_executive_brief
    from .migration_runbook import validate_migration_runbook
    from .migration_waves import validate_migration_waves
    from .migration_execution_queue import validate_migration_execution_queue
    from .move_staging_readiness import validate_move_staging_readiness
    from .operator_dashboard import validate_operator_dashboard
    from .operations_console import validate_operations_console
    from .operator_portal import validate_operator_portal
    from .operator_report import validate_operator_report
    from .prism_categories import validate_prism_category_mapping
    from .recovery_readiness import validate_recovery_readiness
    from .rollback_plan import validate_rollback_plan
    from .risk_register import validate_risk_register
    from .stakeholder_comms import validate_stakeholder_comms
    from .storage_posture import validate_storage_posture
    from .tools_driver_readiness import validate_tools_driver_readiness
    from .wave_execution_calendar import validate_wave_execution_calendar
    from .wave_summary import validate_wave_readiness_summary
    from .what_will_break import validate_what_will_break

    assessment = assessment_dir / "assessment.json"
    validations = (
        ("migration-waves", validate_migration_waves(assessment_dir / "migration-waves.csv", assessment)),
        ("wave-readiness-summary", validate_wave_readiness_summary(assessment_dir / "wave-readiness-summary.csv", assessment)),
        ("wave-execution-calendar", validate_wave_execution_calendar(assessment_dir / "wave-execution-calendar.csv", assessment)),
        ("change-board-evidence", validate_change_board_evidence(assessment_dir / "change-board-evidence.md", assessment)),
        ("migration-runbook", validate_migration_runbook(assessment_dir / "migration-runbook.md", assessment)),
        ("compatibility-research", validate_compatibility_research(assessment_dir / "compatibility-research.csv", assessment)),
        ("dependency-review", validate_dependency_review(assessment_dir / "dependency-review.csv", assessment)),
        ("connectivity-checklist", validate_connectivity_checklist(assessment_dir / "connectivity-checklist.csv", assessment)),
        ("identity-cutover-plan", validate_identity_cutover_plan(assessment_dir / "identity-cutover-plan.csv", assessment)),
        ("migration-risk-register", validate_risk_register(assessment_dir / "migration-risk-register.csv", assessment)),
        ("business-impact-summary", validate_business_impact_summary(assessment_dir / "business-impact-summary.csv", assessment)),
        ("approval-exceptions", validate_approval_exceptions(assessment_dir / "approval-exceptions.csv", assessment)),
        ("tools-driver-readiness", validate_tools_driver_readiness(assessment_dir / "tools-driver-readiness.csv", assessment)),
        ("storage-posture", validate_storage_posture(assessment_dir / "storage-posture.csv", assessment)),
        ("recovery-readiness", validate_recovery_readiness(assessment_dir / "recovery-readiness.csv", assessment)),
        ("rollback-plan", validate_rollback_plan(assessment_dir / "rollback-plan.csv", assessment)),
        ("move-staging-readiness", validate_move_staging_readiness(assessment_dir / "move-staging-readiness.csv", assessment)),
        ("migration-execution-queue", validate_migration_execution_queue(assessment_dir / "migration-execution-queue.csv", assessment)),
        ("prism-category-mapping", validate_prism_category_mapping(assessment_dir / "prism-category-mapping.csv", assessment)),
        ("stakeholder-communication-plan", validate_stakeholder_comms(assessment_dir / "stakeholder-communication-plan.csv", assessment)),
        ("what-will-break-report", validate_what_will_break(assessment_dir / "what-will-break-report.csv", assessment)),
        ("executive-readiness-brief", validate_executive_brief(assessment_dir / "executive-readiness-brief.md", assessment)),
        ("operations-console", validate_operations_console(assessment_dir / "operations-console.html", assessment)),
        ("operator-portal", validate_operator_portal(assessment_dir / "operator-portal.html", assessment)),
        ("operator-report", validate_operator_report(assessment_dir / "operator-report.html", assessment)),
        ("operator-dashboard", validate_operator_dashboard(assessment_dir / "operator-dashboard.html", assessment)),
    )
    return summarize_contract_validations(validations)


def validate_move_ready_contracts(assessment_dir: Path) -> tuple[tuple[str, ...], tuple[str, ...]]:
    from .move_plan_brief import validate_move_plan_brief
    from .move_plan import validate_move_plan
    from .migration_execution_queue import validate_migration_execution_queue
    from .validation_checklist import validate_validation_checklist
    from .workload_validation_checklist import validate_workload_validation_checklist

    validations = (
        ("nutanix-move-plan", validate_move_plan(assessment_dir / "nutanix-move-plan.csv", assessment_dir / "assessment.json")),
        (
            "move-plan-brief",
            validate_move_plan_brief(
                assessment_dir / "move-plan-brief.md",
                assessment_dir / "nutanix-move-plan.csv",
                assessment_dir / "assessment.json",
            ),
        ),
        ("pre-post-validation-checklist", validate_validation_checklist(assessment_dir / "pre-post-validation-checklist.md")),
        ("workload-validation-checklist", validate_workload_validation_checklist(assessment_dir / "workload-validation-checklist.csv", assessment_dir / "assessment.json")),
        ("migration-execution-queue", validate_migration_execution_queue(assessment_dir / "migration-execution-queue.csv", assessment_dir / "assessment.json")),
    )
    return summarize_contract_validations(validations)


def validate_handoff_contracts(
    assessment_dir: Path,
    *,
    evidence_bundle_path: Path | None = None,
    validation_results_path: Path | None = None,
    remediation_tracker_path: Path | None = None,
    signoffs_path: Path | None = None,
    approval_exceptions_path: Path | None = None,
    operator_review_path: Path | None = None,
    move_lab_capture_validation_path: Path | None = None,
    move_lab_proof_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
    warning_acceptance_path: Path | None = None,
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    from .change_gate import run_change_gate
    from .warning_acceptance import validate_warning_acceptance

    gate = run_change_gate(
        assessment_dir,
        bundle_path=evidence_bundle_path,
        validation_results_path=validation_results_path,
        remediation_tracker_path=remediation_tracker_path,
        signoffs_path=signoffs_path,
        approval_exceptions_path=approval_exceptions_path,
        operator_review_path=operator_review_path,
        move_lab_capture_validation_path=move_lab_capture_validation_path,
        move_lab_proof_path=move_lab_proof_path,
        move_lab_evidence_intake_path=move_lab_evidence_intake_path,
    )
    errors = tuple(f"Assessment change gate: {error}" for error in gate.errors)
    gate_warnings = tuple(gate.warnings)
    acceptance_warnings: tuple[str, ...] = ()
    if warning_acceptance_path:
        acceptance = validate_warning_acceptance(warning_acceptance_path, gate_warnings)
        if acceptance.ok:
            accepted = set(acceptance.accepted_warnings)
            gate_warnings = tuple(warning for warning in gate_warnings if warning not in accepted)
        else:
            errors = errors + tuple(f"Warning acceptance: {error}" for error in acceptance.errors)
        acceptance_warnings = tuple(f"Warning acceptance: {warning}" for warning in acceptance.warnings)
    warnings = tuple(f"Assessment change gate: {warning}" for warning in gate_warnings) + acceptance_warnings
    return errors, warnings


def summarize_contract_validations(validations: tuple[tuple[str, Any], ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    errors: list[str] = []
    warnings: list[str] = []
    for name, validation in validations:
        errors.extend(f"{name}: {error}" for error in validation.errors)
        warnings.extend(f"{name}: {warning}" for warning in validation.warnings)
    return tuple(errors), tuple(warnings)


def validate_external_proof_path(
    path: Path,
    schema_version: str,
    required_check: tuple[str, str] | None = None,
) -> tuple[str, ...]:
    if not path.exists():
        return (f"{path}: missing",)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return (f"{path}: could not read JSON: {exc}",)
    if not isinstance(payload, dict):
        return (f"{path}: JSON root must be an object",)
    errors: list[str] = []
    if payload.get("schema_version") != schema_version:
        errors.append(f"{path}: schema_version must be {schema_version}")
    if payload.get("status") != "pass":
        errors.append(f"{path}: status must be pass")
    if payload.get("errors"):
        errors.append(f"{path}: proof contains errors")
    if required_check:
        check_name, expected_detail = required_check
        checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
        match = next((check for check in checks if isinstance(check, dict) and check.get("name") == check_name), None)
        if not match:
            errors.append(f"{path}: proof missing required check {check_name}")
        elif match.get("status") != "pass" or match.get("detail") != expected_detail:
            errors.append(f"{path}: proof check {check_name} must pass with detail {expected_detail}")
    return tuple(errors)


def validate_live_endpoint_proof_validation_path(path: Path) -> tuple[str, ...]:
    errors = list(validate_external_proof_path(path, "nmrcp_live_endpoint_proof_v1"))
    if errors:
        return tuple(errors)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return (f"{path}: could not read JSON: {exc}",)
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    checks_by_name = {
        str(check.get("name") or ""): check
        for check in checks
        if isinstance(check, dict) and check.get("name")
    }
    for check_name in REQUIRED_LIVE_ENDPOINT_PROOF_CHECKS:
        check = checks_by_name.get(check_name)
        if not check:
            errors.append(f"{path}: live endpoint proof missing required check {check_name}")
        elif check.get("status") != "pass":
            errors.append(f"{path}: live endpoint proof check {check_name} must pass")
    for check in checks:
        if isinstance(check, dict) and check.get("status") == "fail":
            errors.append(f"{path}: live endpoint proof contains failed check {check.get('name') or 'unknown'}")
    return tuple(errors)
