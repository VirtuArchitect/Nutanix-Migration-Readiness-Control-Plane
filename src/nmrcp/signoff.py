from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SIGNOFF_COLUMNS = [
    "status",
    "owner",
    "wave",
    "workload_id",
    "workload_name",
    "target",
    "readiness",
    "risk_score",
    "required_signoffs",
    "blocking_reason",
    "approval_due",
    "evidence_refs",
    "approval_ref",
    "approved_by",
    "approved_at",
    "notes",
]
ALLOWED_STATUSES = {"pending", "approved", "rejected", "waived"}
ALLOWED_READINESS = {"ready", "research", "prepare", "blocked"}
ALLOWED_TARGETS = {"ahv", "nc2"}
ALLOWED_SIGNOFFS = {
    "application_owner",
    "migration_lead",
    "risk_acceptance",
    "dependency_owner",
    "backup_owner",
    "rollback_owner",
    "network_owner",
    "storage_owner",
    "cloud_owner",
}


@dataclass(frozen=True)
class SignoffValidation:
    path: Path
    row_count: int
    approved_count: int
    pending_count: int
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
            f"{status}: rows={self.row_count}, approved={self.approved_count}, "
            f"pending={self.pending_count}, rejected={self.rejected_count}, waived={self.waived_count}, "
            f"errors={len(self.errors)}, warnings={len(self.warnings)}"
        )


@dataclass(frozen=True)
class SignoffMatrixContractValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_signoffs(path: Path, allow_pending: bool = False) -> SignoffValidation:
    errors: list[str] = []
    warnings: list[str] = []
    approved_count = 0
    pending_count = 0
    rejected_count = 0
    waived_count = 0

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [column for column in SIGNOFF_COLUMNS if column not in fieldnames]
        extra = [column for column in fieldnames if column not in SIGNOFF_COLUMNS]
        if missing:
            errors.append(f"Missing required columns: {', '.join(missing)}")
        if extra:
            warnings.append(f"Unexpected columns ignored by nmrcp validator: {', '.join(extra)}")
        rows = list(reader)

    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=2):
        workload_id = (row.get("workload_id") or "").strip()
        workload_name = (row.get("workload_name") or "").strip()
        owner = (row.get("owner") or "").strip()
        wave = (row.get("wave") or "").strip()
        target = (row.get("target") or "").strip()
        readiness = (row.get("readiness") or "").strip()
        status = (row.get("status") or "").strip().lower()
        signoffs = split_signoffs(row.get("required_signoffs") or "")
        blocking_reason = (row.get("blocking_reason") or "").strip()
        approval_due = (row.get("approval_due") or "").strip()
        evidence_refs = split_refs(row.get("evidence_refs") or "")
        approval_ref = (row.get("approval_ref") or "").strip()
        approved_by = (row.get("approved_by") or "").strip()
        approved_at = (row.get("approved_at") or "").strip()
        notes = (row.get("notes") or "").strip()

        if not workload_id:
            errors.append(f"Row {index}: workload_id is required")
        if workload_id in seen_ids:
            errors.append(f"Row {index}: duplicate workload_id {workload_id!r}")
        seen_ids.add(workload_id)
        if not workload_name:
            errors.append(f"Row {index}: workload_name is required")
        if not owner:
            errors.append(f"Row {index}: owner is required")
        if not wave:
            errors.append(f"Row {index}: wave is required")
        if target not in ALLOWED_TARGETS:
            errors.append(f"Row {index}: target must be one of {', '.join(sorted(ALLOWED_TARGETS))}")
        if readiness not in ALLOWED_READINESS:
            errors.append(f"Row {index}: readiness must be one of {', '.join(sorted(ALLOWED_READINESS))}")
        if status not in ALLOWED_STATUSES:
            errors.append(f"Row {index}: status must be one of {', '.join(sorted(ALLOWED_STATUSES))}")
        if not signoffs:
            errors.append(f"Row {index}: required_signoffs is required")
        unknown_signoffs = sorted(signoffs - ALLOWED_SIGNOFFS)
        if unknown_signoffs:
            errors.append(f"Row {index}: unknown required_signoffs: {', '.join(unknown_signoffs)}")
        if not blocking_reason:
            errors.append(f"Row {index}: blocking_reason is required")
        if not approval_due:
            errors.append(f"Row {index}: approval_due is required")
        if not evidence_refs:
            warnings.append(f"Row {index}: evidence_refs should include assessment and plan references")
        try:
            risk_score = int(row.get("risk_score") or "")
        except ValueError:
            errors.append(f"Row {index}: risk_score must be an integer")
        else:
            if risk_score < 0 or risk_score > 100:
                errors.append(f"Row {index}: risk_score must be between 0 and 100")
            if status == "approved" and risk_score >= 75:
                warnings.append(f"Row {index}: high-risk workload approved; confirm risk acceptance evidence")

        if status == "approved":
            approved_count += 1
            validate_approval_fields(index, approval_ref, approved_by, approved_at, errors)
        elif status == "pending":
            pending_count += 1
            if not allow_pending:
                errors.append(f"Row {index}: pending sign-off blocks final approval")
        elif status == "rejected":
            rejected_count += 1
            errors.append(f"Row {index}: rejected sign-off blocks final approval")
        elif status == "waived":
            waived_count += 1
            validate_approval_fields(index, approval_ref, approved_by, approved_at, errors)
            if "risk_acceptance" not in signoffs:
                warnings.append(f"Row {index}: waived sign-off should be reviewed for risk acceptance")
            if not notes:
                warnings.append(f"Row {index}: waived sign-off should include waiver rationale in notes")

        if readiness in {"prepare", "blocked"} and status == "approved":
            warnings.append(f"Row {index}: {readiness} workload approved before remediation closure")

    if not rows:
        errors.append("Sign-off matrix cannot be empty")

    return SignoffValidation(
        path=path,
        row_count=len(rows),
        approved_count=approved_count,
        pending_count=pending_count,
        rejected_count=rejected_count,
        waived_count=waived_count,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_signoff_matrix_contract(matrix_path: Path, assessment_path: Path) -> SignoffMatrixContractValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_signoff_rows(matrix_path, errors, warnings)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return SignoffMatrixContractValidation("fail", len(rows), tuple(errors), tuple(warnings))

    draft = validate_signoffs(matrix_path, allow_pending=True)
    errors.extend(draft.errors)
    warnings.extend(draft.warnings)

    expected = expected_signoff_rows(assessment, errors)
    by_workload = {row.get("workload_id", ""): row for row in rows}
    if len(by_workload) != len(rows):
        errors.append("owner-signoff-matrix.csv contains duplicate workload_id rows")

    missing = sorted(set(expected).difference(by_workload))
    extra = sorted(set(by_workload).difference(expected))
    for workload_id in missing:
        errors.append(f"Missing sign-off matrix row: {workload_id}")
    for workload_id in extra:
        errors.append(f"Unexpected sign-off matrix row: {workload_id}")

    for workload_id, expected_row in expected.items():
        row = by_workload.get(workload_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{workload_id}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("owner-signoff-matrix.csv cannot be empty")

    return SignoffMatrixContractValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def read_signoff_rows(path: Path, errors: list[str], warnings: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in SIGNOFF_COLUMNS if column not in fieldnames]
            extra = [column for column in fieldnames if column not in SIGNOFF_COLUMNS]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            if extra:
                warnings.append(f"Unexpected columns ignored by nmrcp validator: {', '.join(extra)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read owner sign-off matrix: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_signoff_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("signoff_context") if isinstance(assessment.get("signoff_context"), dict) else {}
    context_rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != "nmrcp_signoff_context_v1":
        errors.append("assessment.json missing nmrcp_signoff_context_v1 sign-off context")
    required_by_workload = {
        str(row.get("workload_id") or ""): sorted(str(item) for item in row.get("required_signoffs", []) if str(item))
        for row in context_rows
        if isinstance(row, dict)
    }

    assessments = {
        str(item.get("workload_id") or ""): item
        for item in assessment.get("assessments", [])
        if isinstance(item, dict)
    }
    wave_by_workload = {
        workload_id: str(wave.get("name") or "Unassigned")
        for wave in assessment.get("waves", [])
        if isinstance(wave, dict)
        for workload_id in wave.get("workload_ids", [])
        if isinstance(workload_id, str)
    }

    expected: dict[str, dict[str, str]] = {}
    for workload_id, row in assessments.items():
        expected[workload_id] = {
            "status": "pending",
            "owner": str(row.get("owner") or "Unassigned"),
            "wave": wave_by_workload.get(workload_id, "Unassigned"),
            "workload_id": workload_id,
            "workload_name": str(row.get("name") or ""),
            "target": str(row.get("target") or ""),
            "readiness": str(row.get("readiness") or ""),
            "risk_score": str(int(row.get("risk_score") or 0)),
            "required_signoffs": ";".join(required_by_workload.get(workload_id, baseline_signoffs(row))),
            "blocking_reason": signoff_blocking_reason(row),
            "approval_due": signoff_due(row),
            "evidence_refs": ";".join(
                [
                    f"assessment.json#{workload_id}",
                    f"nutanix-move-plan.csv#{workload_id}",
                    f"pre-post-validation-checklist.md#{workload_id}",
                ]
            ),
            "approval_ref": "",
            "approved_by": "",
            "approved_at": "",
            "notes": "",
        }
    return expected


def validate_approval_fields(
    index: int,
    approval_ref: str,
    approved_by: str,
    approved_at: str,
    errors: list[str],
) -> None:
    if not approval_ref:
        errors.append(f"Row {index}: approval_ref is required when status is approved or waived")
    if not approved_by:
        errors.append(f"Row {index}: approved_by is required when status is approved or waived")
    if not approved_at:
        errors.append(f"Row {index}: approved_at is required when status is approved or waived")


def baseline_signoffs(row: dict[str, Any]) -> list[str]:
    signoffs = {"application_owner", "migration_lead", "rollback_owner"}
    findings = row.get("findings") if isinstance(row.get("findings"), list) else []
    severities = {str(finding.get("severity") or "") for finding in findings if isinstance(finding, dict)}
    if row.get("readiness") in {"prepare", "blocked"} or severities & {"critical", "high"}:
        signoffs.add("risk_acceptance")
    if row.get("target") == "nc2":
        signoffs.add("cloud_owner")
    return sorted(signoffs)


def signoff_blocking_reason(row: dict[str, Any]) -> str:
    readiness = str(row.get("readiness") or "")
    if readiness == "blocked":
        return "blocked workload requires remediation and formal risk acceptance"
    if readiness == "prepare":
        return "remediation must close before owner approval"
    if readiness == "research":
        return "research findings require application owner acceptance"
    return "owner approval required before Move staging"


def signoff_due(row: dict[str, Any]) -> str:
    readiness = str(row.get("readiness") or "")
    if readiness in {"blocked", "prepare"}:
        return "before remediation closure"
    if readiness == "research":
        return "before wave scheduling"
    return "before Move staging"


def split_signoffs(value: str) -> set[str]:
    return {item.strip() for item in value.split(";") if item.strip()}


def split_refs(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]
