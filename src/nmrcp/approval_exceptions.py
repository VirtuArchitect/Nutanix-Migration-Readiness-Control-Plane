from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Finding, Wave, WorkloadAssessment


APPROVAL_EXCEPTIONS_SCHEMA_VERSION = "nmrcp_approval_exceptions_v1"
APPROVAL_EXCEPTIONS_COLUMNS = (
    "schema_version",
    "exception_id",
    "workload_id",
    "name",
    "owner",
    "target",
    "wave",
    "readiness",
    "risk_score",
    "exception_type",
    "finding_code",
    "severity",
    "required_approval",
    "approval_status",
    "blocking_reason",
    "required_action",
    "evidence_refs",
    "approval_ref",
    "approved_by",
    "approved_at",
    "notes",
)
ALLOWED_APPROVAL_STATUSES = {"required", "approved", "rejected", "waived"}


@dataclass(frozen=True)
class ApprovalExceptionsValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


@dataclass(frozen=True)
class ApprovalExceptionApprovalsValidation:
    path: Path
    row_count: int
    required_count: int
    approved_count: int
    rejected_count: int
    waived_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return (
            f"{status}: rows={self.row_count}, required={self.required_count}, approved={self.approved_count}, "
            f"rejected={self.rejected_count}, waived={self.waived_count}, errors={len(self.errors)}, warnings={len(self.warnings)}"
        )


def approval_exceptions_context(assessments: list[WorkloadAssessment], waves: list[Wave]) -> dict[str, Any]:
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    rows: list[dict[str, str]] = []
    for assessment in assessments:
        rows.extend(approval_exception_rows(assessment, wave_by_workload.get(assessment.workload_id, "Unassigned")))
    return {
        "schema_version": APPROVAL_EXCEPTIONS_SCHEMA_VERSION,
        "exceptions": rows,
    }


def write_approval_exceptions_csv(assessments: list[WorkloadAssessment], waves: list[Wave], path: Path) -> None:
    rows = approval_exceptions_context(assessments, waves)["exceptions"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=APPROVAL_EXCEPTIONS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_approval_exceptions(path: Path, assessment_path: Path) -> ApprovalExceptionsValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return ApprovalExceptionsValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_approval_exception_rows(assessment, errors)
    by_id = {row.get("exception_id", ""): row for row in rows}
    if len(by_id) != len(rows):
        errors.append("approval-exceptions.csv contains duplicate exception_id rows")

    missing = sorted(set(expected).difference(by_id))
    extra = sorted(set(by_id).difference(expected))
    for exception_id in missing:
        errors.append(f"Missing approval exception row: {exception_id}")
    for exception_id in extra:
        errors.append(f"Unexpected approval exception row: {exception_id}")

    for exception_id, expected_row in expected.items():
        row = by_id.get(exception_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{exception_id}: {field} expected {expected_value!r}, got {actual!r}")

    if expected and not rows:
        errors.append("approval-exceptions.csv cannot be empty when approval exception context exists")
    if not expected and rows:
        errors.append("approval-exceptions.csv must be empty except header when no approval exceptions exist")

    return ApprovalExceptionsValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def approval_exception_rows(assessment: WorkloadAssessment, wave: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    if assessment.readiness in {"prepare", "blocked"}:
        rows.append(
            exception_row(
                assessment,
                wave,
                exception_type="readiness_exception",
                finding_code=f"readiness_{assessment.readiness}",
                severity="high" if assessment.readiness == "prepare" else "critical",
                required_approval="risk_acceptance;migration_lead",
                blocking_reason=f"{assessment.readiness} workload requires remediation closure or formal risk acceptance.",
                required_action="Do not approve execution until remediation closure or explicit risk acceptance is attached.",
            )
        )
    if assessment.risk_score >= 75:
        rows.append(
            exception_row(
                assessment,
                wave,
                exception_type="high_risk_exception",
                finding_code="risk_score_threshold",
                severity="high" if assessment.risk_score < 90 else "critical",
                required_approval="risk_acceptance;migration_lead",
                blocking_reason=f"Risk score {assessment.risk_score} requires explicit risk acceptance before migration approval.",
                required_action="Attach risk acceptance evidence and confirm executive or migration-lead approval.",
            )
        )
    for finding in assessment.findings:
        if severity_rank(finding.severity) >= 3:
            rows.append(finding_exception_row(assessment, wave, finding))
    return rows


def finding_exception_row(assessment: WorkloadAssessment, wave: str, finding: Finding) -> dict[str, str]:
    return exception_row(
        assessment,
        wave,
        exception_type="finding_exception",
        finding_code=finding.code,
        severity=finding.severity,
        required_approval=approval_for_finding(finding.code),
        blocking_reason=f"{finding.severity} finding `{finding.code}` requires approval or closure.",
        required_action=finding.recommended_action,
    )


def exception_row(
    assessment: WorkloadAssessment,
    wave: str,
    *,
    exception_type: str,
    finding_code: str,
    severity: str,
    required_approval: str,
    blocking_reason: str,
    required_action: str,
) -> dict[str, str]:
    exception_id = f"{assessment.workload_id}:{exception_type}:{finding_code}"
    return {
        "schema_version": APPROVAL_EXCEPTIONS_SCHEMA_VERSION,
        "exception_id": exception_id,
        "workload_id": assessment.workload_id,
        "name": assessment.name,
        "owner": assessment.owner,
        "target": assessment.target,
        "wave": wave,
        "readiness": assessment.readiness,
        "risk_score": str(assessment.risk_score),
        "exception_type": exception_type,
        "finding_code": finding_code,
        "severity": severity,
        "required_approval": required_approval,
        "approval_status": "required",
        "blocking_reason": blocking_reason,
        "required_action": required_action,
        "evidence_refs": ";".join(
            [
                f"assessment.json#{assessment.workload_id}",
                f"migration-risk-register.csv#{finding_code}",
                f"owner-signoff-matrix.csv#{assessment.workload_id}",
                f"remediation-tracker.csv#{assessment.workload_id}",
            ]
        ),
        "approval_ref": "",
        "approved_by": "",
        "approved_at": "",
        "notes": "",
    }


def validate_approval_exception_approvals(
    path: Path,
    allow_required: bool = False,
    assessment_path: Path | None = None,
) -> ApprovalExceptionApprovalsValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    if assessment_path:
        validate_final_file_matches_assessment(rows, assessment_path, errors)
    required_count = 0
    approved_count = 0
    rejected_count = 0
    waived_count = 0

    for index, row in enumerate(rows, start=2):
        exception_id = (row.get("exception_id") or "").strip()
        workload_id = (row.get("workload_id") or "").strip()
        status = (row.get("approval_status") or "").strip().lower()
        approval_ref = (row.get("approval_ref") or "").strip()
        approved_by = (row.get("approved_by") or "").strip()
        approved_at = (row.get("approved_at") or "").strip()
        notes = (row.get("notes") or "").strip()
        required_approval = (row.get("required_approval") or "").strip()

        if not exception_id:
            errors.append(f"Row {index}: exception_id is required")
        if not workload_id:
            errors.append(f"Row {index}: workload_id is required")
        if status not in ALLOWED_APPROVAL_STATUSES:
            errors.append(f"Row {index}: approval_status must be one of {', '.join(sorted(ALLOWED_APPROVAL_STATUSES))}")
            continue
        if not required_approval:
            errors.append(f"Row {index}: required_approval is required")

        if status == "required":
            required_count += 1
            if not allow_required:
                errors.append(f"Row {index}: required approval exception blocks final closure")
        elif status == "approved":
            approved_count += 1
            validate_approval_fields(index, approval_ref, approved_by, approved_at, errors)
        elif status == "rejected":
            rejected_count += 1
            errors.append(f"Row {index}: rejected approval exception blocks final closure")
        elif status == "waived":
            waived_count += 1
            validate_approval_fields(index, approval_ref, approved_by, approved_at, errors)
            if not notes:
                warnings.append(f"Row {index}: waived approval exception should include waiver rationale in notes")

    if not rows:
        errors.append("Approval exceptions approval file cannot be empty")

    return ApprovalExceptionApprovalsValidation(
        path=path,
        row_count=len(rows),
        required_count=required_count,
        approved_count=approved_count,
        rejected_count=rejected_count,
        waived_count=waived_count,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_final_file_matches_assessment(rows: list[dict[str, str]], assessment_path: Path, errors: list[str]) -> None:
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return
    expected = expected_approval_exception_rows(assessment, errors)
    by_id = {row.get("exception_id", ""): row for row in rows}
    if len(by_id) != len(rows):
        errors.append("approval exception approval file contains duplicate exception_id rows")

    missing = sorted(set(expected).difference(by_id))
    extra = sorted(set(by_id).difference(expected))
    for exception_id in missing:
        errors.append(f"Missing approval exception approval row: {exception_id}")
    for exception_id in extra:
        errors.append(f"Unexpected approval exception approval row: {exception_id}")

    closure_columns = {"approval_status", "approval_ref", "approved_by", "approved_at", "notes"}
    for exception_id, expected_row in expected.items():
        row = by_id.get(exception_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            if field in closure_columns:
                continue
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{exception_id}: {field} expected {expected_value!r}, got {actual!r}")


def validate_approval_fields(
    index: int,
    approval_ref: str,
    approved_by: str,
    approved_at: str,
    errors: list[str],
) -> None:
    if not approval_ref:
        errors.append(f"Row {index}: approval_ref is required when approval_status is approved or waived")
    if not approved_by:
        errors.append(f"Row {index}: approved_by is required when approval_status is approved or waived")
    if not approved_at:
        errors.append(f"Row {index}: approved_at is required when approval_status is approved or waived")


def approval_for_finding(code: str) -> str:
    if any(token in code for token in ("network", "vds", "nsx", "ip", "dns")):
        return "network_owner;risk_acceptance;migration_lead"
    if any(token in code for token in ("backup", "snapshot", "rollback", "recovery")):
        return "backup_owner;rollback_owner;risk_acceptance;migration_lead"
    if any(token in code for token in ("storage", "rdm", "disk", "datastore")):
        return "storage_owner;risk_acceptance;migration_lead"
    if any(token in code for token in ("dependency", "connectivity")):
        return "dependency_owner;risk_acceptance;migration_lead"
    return "application_owner;risk_acceptance;migration_lead"


def severity_rank(severity: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(severity.lower(), 0)


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in APPROVAL_EXCEPTIONS_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read approval exceptions CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_approval_exception_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("approval_exceptions_context") if isinstance(assessment.get("approval_exceptions_context"), dict) else {}
    rows = context.get("exceptions") if isinstance(context.get("exceptions"), list) else []
    if context.get("schema_version") != APPROVAL_EXCEPTIONS_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {APPROVAL_EXCEPTIONS_SCHEMA_VERSION} approval exceptions context")
    expected: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = {column: str(row.get(column) or "") for column in APPROVAL_EXCEPTIONS_COLUMNS}
        expected[normalized["exception_id"]] = normalized
    return expected
