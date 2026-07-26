from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Finding, Wave, WorkloadAssessment


PARTNER_HANDOFF_SCHEMA_VERSION = "nmrcp_partner_handoff_matrix_v1"
PARTNER_HANDOFF_COLUMNS = (
    "schema_version",
    "role",
    "handoff_scope",
    "owned_artifacts",
    "required_review",
    "handoff_status",
    "blocking_condition",
    "next_action",
)


@dataclass(frozen=True)
class PartnerHandoffValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def partner_handoff_context(assessments: list[WorkloadAssessment], waves: list[Wave]) -> dict[str, Any]:
    return {
        "schema_version": PARTNER_HANDOFF_SCHEMA_VERSION,
        "roles": partner_handoff_rows(assessments, waves),
    }


def write_partner_handoff_matrix_csv(assessments: list[WorkloadAssessment], waves: list[Wave], path: Path) -> None:
    rows = partner_handoff_rows(assessments, waves)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PARTNER_HANDOFF_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_partner_handoff_matrix(matrix_path: Path, assessment_path: Path) -> PartnerHandoffValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(matrix_path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return PartnerHandoffValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_handoff_rows(assessment, errors)
    by_role = {row.get("role", ""): row for row in rows}
    if len(by_role) != len(rows):
        errors.append("partner-handoff-matrix.csv contains duplicate role rows")

    missing = sorted(set(expected).difference(by_role))
    extra = sorted(set(by_role).difference(expected))
    for role in missing:
        errors.append(f"Missing partner handoff row: {role}")
    for role in extra:
        errors.append(f"Unexpected partner handoff row: {role}")

    for role, expected_row in expected.items():
        row = by_role.get(role)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{role}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("partner-handoff-matrix.csv cannot be empty")

    return PartnerHandoffValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def partner_handoff_rows(assessments: list[WorkloadAssessment], waves: list[Wave]) -> list[dict[str, str]]:
    summary = summarize(assessments)
    wave_names = ";".join(wave.name for wave in waves)
    held = summary["prepare"] + summary["blocked"]
    high_risk = sum(1 for assessment in assessments if assessment.risk_score >= 70)
    return [
        role_row(
            "migration_lead",
            f"Coordinate assessment handoff across {len(waves)} waves.",
            "assessment.json;evidence-manifest.json;wave-execution-calendar.csv;operator-gate-summary.md",
            f"Confirm wave order, open blockers, and handoff package completeness for {wave_names}.",
            "blocked" if held else "ready",
            "Held workloads remain open." if held else "",
            "Close held workload actions or record accepted risk before external handoff." if held else "Package evidence and schedule review.",
        ),
        role_row(
            "application_owner",
            "Review workload impact, sign-off, and validation ownership.",
            "owner-signoff-matrix.csv;stakeholder-communication-plan.csv;what-will-break-report.csv;workload-validation-checklist.csv",
            "Confirm application owner approval, validation contact, and workload breakage actions.",
            "blocked" if held else "ready",
            "Prepare or blocked workloads need owner response." if held else "",
            "Respond to stakeholder plan and update sign-off matrix." if held else "Confirm sign-off and validation owner.",
        ),
        role_row(
            "platform_owner",
            "Review Prism/AHV/NC2 target readiness and governance mapping.",
            "target-readiness-comparison.csv;target-capacity-fit.csv;prism-category-mapping.csv;move-staging-readiness.csv",
            "Confirm target selection, capacity posture, category plan, and staging readiness.",
            "review_required",
            "Target artifacts may be optional or environment-specific.",
            "Attach platform-owner review or mark unavailable context as not applicable.",
        ),
        role_row(
            "network_owner",
            "Review source and target network reachability before Move staging.",
            "connectivity-checklist.csv;source-network-validation.csv;target-network-mapping.csv;identity-cutover-plan.csv",
            "Confirm VLAN, DNS, IPAM, firewall, and target network mapping evidence.",
            "blocked" if any_finding(assessments, ("vds", "nsx", "connectivity")) else "review_required",
            "Network-related findings remain open." if any_finding(assessments, ("vds", "nsx", "connectivity")) else "Network proof may be optional until source network export is supplied.",
            "Close network findings or attach mapping proof." if any_finding(assessments, ("vds", "nsx", "connectivity")) else "Review connectivity and mapping artifacts.",
        ),
        role_row(
            "backup_and_rollback_owner",
            "Review recoverability, snapshot cleanup, and rollback ownership.",
            "recovery-readiness.csv;rollback-plan.csv;pre-post-validation-checklist.md;move-lab-closure-checklist.md",
            "Confirm backup proof, snapshot posture, rollback owner, and stop criteria.",
            "blocked" if any_finding(assessments, ("backup", "snapshot", "rollback")) else "ready",
            "Recovery or rollback findings remain open." if any_finding(assessments, ("backup", "snapshot", "rollback")) else "",
            "Close recovery findings and confirm rollback owner." if any_finding(assessments, ("backup", "snapshot", "rollback")) else "Confirm rollback criteria.",
        ),
        role_row(
            "risk_and_change_board",
            "Review risk acceptance, exceptions, and launch readiness posture.",
            "migration-risk-register.csv;approval-exceptions.csv;executive-readiness-brief.md;launch-readiness-report.md",
            "Confirm high-risk findings, exceptions, warning acceptance, and external proof gaps.",
            "blocked" if high_risk else "review_required",
            "High-risk workloads require risk acceptance." if high_risk else "Warning acceptance may still be required.",
            "Approve exceptions or keep external handoff blocked." if high_risk else "Review launch readiness report.",
        ),
        role_row(
            "move_operator",
            "Review Move dry-run payload and lab-only proof chain.",
            "nutanix-move-plan.csv;move-api-payload.dry-run.json;move-submit-readiness.json;move-lab-capture-kit-validation.json",
            "Confirm dry-run payload, lab acknowledgement, capture kit, and no production mutation.",
            "blocked",
            "Approved non-production Move appliance proof remains external unless supplied.",
            "Run approved lab proof workflow and attach passing evidence intake before external handoff.",
        ),
    ]


def role_row(
    role: str,
    handoff_scope: str,
    owned_artifacts: str,
    required_review: str,
    handoff_status: str,
    blocking_condition: str,
    next_action: str,
) -> dict[str, str]:
    return {
        "schema_version": PARTNER_HANDOFF_SCHEMA_VERSION,
        "role": role,
        "handoff_scope": handoff_scope,
        "owned_artifacts": owned_artifacts,
        "required_review": required_review,
        "handoff_status": handoff_status,
        "blocking_condition": blocking_condition,
        "next_action": next_action,
    }


def summarize(assessments: list[WorkloadAssessment]) -> dict[str, int]:
    summary = {"ready": 0, "research": 0, "prepare": 0, "blocked": 0}
    for assessment in assessments:
        if assessment.readiness in summary:
            summary[assessment.readiness] += 1
    return summary


def any_finding(assessments: list[WorkloadAssessment], tokens: tuple[str, ...]) -> bool:
    return any(
        token in finding.code
        for assessment in assessments
        for finding in assessment.findings
        for token in tokens
    )


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in PARTNER_HANDOFF_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read partner handoff matrix: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_handoff_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    derived = derived_handoff_rows(assessment, errors)
    context = assessment.get("partner_handoff_context") if isinstance(assessment.get("partner_handoff_context"), dict) else {}
    if context.get("schema_version") != PARTNER_HANDOFF_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {PARTNER_HANDOFF_SCHEMA_VERSION} partner handoff context")
    context_rows = context.get("roles") if isinstance(context.get("roles"), list) else []
    context_by_role: dict[str, dict[str, str]] = {}
    for row in context_rows:
        if not isinstance(row, dict):
            continue
        normalized = {column: str(row.get(column) or "") for column in PARTNER_HANDOFF_COLUMNS}
        context_by_role[normalized["role"]] = normalized
    if derived and context_by_role != derived:
        errors.append("assessment.json partner_handoff_context does not match assessments and waves")
    return derived or context_by_role


def derived_handoff_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    assessments = parse_workload_assessments(assessment.get("assessments"), errors)
    assessment_workload_ids = {assessment.workload_id for assessment in assessments}
    waves = parse_waves(assessment.get("waves"), assessment_workload_ids, errors)
    if not assessments or not waves:
        return {}
    return {
        row["role"]: {column: str(row.get(column) or "") for column in PARTNER_HANDOFF_COLUMNS}
        for row in partner_handoff_rows(assessments, waves)
    }


def parse_workload_assessments(value: Any, errors: list[str]) -> list[WorkloadAssessment]:
    if not isinstance(value, list) or not value:
        errors.append("assessment.json assessments must contain workload assessment rows")
        return []
    assessments: list[WorkloadAssessment] = []
    for index, row in enumerate(value, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json assessments row {index} must be an object")
            continue
        findings: list[Finding] = []
        raw_findings = row.get("findings") if isinstance(row.get("findings"), list) else []
        for finding in raw_findings:
            if not isinstance(finding, dict):
                continue
            findings.append(
                Finding(
                    code=str(finding.get("code") or ""),
                    severity=str(finding.get("severity") or ""),
                    message=str(finding.get("message") or ""),
                    recommended_action=str(finding.get("recommended_action") or ""),
                )
            )
        assessments.append(
            WorkloadAssessment(
                workload_id=str(row.get("workload_id") or ""),
                name=str(row.get("name") or ""),
                owner=str(row.get("owner") or ""),
                readiness=str(row.get("readiness") or ""),
                risk_score=parse_int(row.get("risk_score")),
                target=str(row.get("target") or ""),
                findings=tuple(findings),
            )
        )
    return assessments


def parse_waves(value: Any, workload_ids: set[str], errors: list[str]) -> list[Wave]:
    if not isinstance(value, list) or not value:
        errors.append("assessment.json waves must contain wave rows")
        return []
    waves: list[Wave] = []
    assigned_workloads: dict[str, str] = {}
    for index, row in enumerate(value, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json waves row {index} must be an object")
            continue
        wave_name = str(row.get("name") or "")
        wave_workload_ids = row.get("workload_ids") if isinstance(row.get("workload_ids"), list) else []
        for workload_id in wave_workload_ids:
            if not isinstance(workload_id, str):
                continue
            if workload_id not in workload_ids:
                errors.append(f"assessment.json wave {wave_name!r} references unknown workload_id {workload_id!r}")
            previous_wave = assigned_workloads.get(workload_id)
            if previous_wave:
                errors.append(
                    f"assessment.json workload_id {workload_id!r} appears in multiple waves: "
                    f"{previous_wave!r} and {wave_name!r}"
                )
            assigned_workloads[workload_id] = wave_name
        waves.append(
            Wave(
                name=wave_name,
                description=str(row.get("description") or ""),
                workload_ids=tuple(str(workload_id) for workload_id in wave_workload_ids),
            )
        )
    return waves


def parse_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0
