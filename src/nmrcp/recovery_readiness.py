from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import WorkloadAssessment


RECOVERY_READINESS_SCHEMA_VERSION = "nmrcp_recovery_readiness_v1"
RECOVERY_READINESS_COLUMNS = (
    "schema_version",
    "workload_id",
    "name",
    "owner",
    "target",
    "readiness",
    "backup_protected",
    "backup_last_success_hours",
    "snapshot_count",
    "oldest_snapshot_days",
    "oldest_snapshot_created_at",
    "rollback_owner",
    "recovery_status",
    "blocking_findings",
    "required_action",
    "evidence_refs",
)
RECOVERY_FINDINGS = {
    "backup_not_confirmed",
    "backup_recovery_point_stale",
    "snapshots_present",
    "snapshot_age_exceeds_policy",
    "rollback_owner_missing",
}


@dataclass(frozen=True)
class RecoveryReadinessValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def recovery_readiness_context(inventory: dict[str, Any], assessments: list[WorkloadAssessment]) -> dict[str, Any]:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    return {
        "schema_version": RECOVERY_READINESS_SCHEMA_VERSION,
        "workloads": [recovery_readiness_row(workloads.get(assessment.workload_id, {}), assessment) for assessment in assessments],
    }


def write_recovery_readiness_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    path: Path,
) -> None:
    rows = recovery_readiness_context(inventory, assessments)["workloads"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=RECOVERY_READINESS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_recovery_readiness(path: Path, assessment_path: Path) -> RecoveryReadinessValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return RecoveryReadinessValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_recovery_rows(assessment, errors)
    by_workload = {row.get("workload_id", ""): row for row in rows}
    if len(by_workload) != len(rows):
        errors.append("recovery-readiness.csv contains duplicate workload_id rows")

    missing = sorted(set(expected).difference(by_workload))
    extra = sorted(set(by_workload).difference(expected))
    for workload_id in missing:
        errors.append(f"Missing recovery readiness row: {workload_id}")
    for workload_id in extra:
        errors.append(f"Unexpected recovery readiness row: {workload_id}")

    for workload_id, expected_row in expected.items():
        row = by_workload.get(workload_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{workload_id}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("recovery-readiness.csv cannot be empty")

    return RecoveryReadinessValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def recovery_readiness_row(workload: dict[str, Any], assessment: WorkloadAssessment) -> dict[str, str]:
    backup = workload.get("backup") if isinstance(workload.get("backup"), dict) else {}
    snapshots = workload.get("snapshots") if isinstance(workload.get("snapshots"), dict) else {}
    governance = workload.get("governance") if isinstance(workload.get("governance"), dict) else {}
    finding_codes = [finding.code for finding in assessment.findings if finding.code in RECOVERY_FINDINGS]
    status = recovery_status(finding_codes)
    rollback_owner = str(governance.get("rollback_owner") or "").strip() or "not confirmed"
    return {
        "schema_version": RECOVERY_READINESS_SCHEMA_VERSION,
        "workload_id": assessment.workload_id,
        "name": assessment.name,
        "owner": assessment.owner,
        "target": assessment.target,
        "readiness": assessment.readiness,
        "backup_protected": bool_text(backup.get("protected")),
        "backup_last_success_hours": text_value(backup.get("last_success_hours")),
        "snapshot_count": text_value(snapshots.get("count")),
        "oldest_snapshot_days": text_value(snapshots.get("oldest_days")),
        "oldest_snapshot_created_at": text_value(snapshots.get("oldest_created_at")),
        "rollback_owner": rollback_owner,
        "recovery_status": status,
        "blocking_findings": "; ".join(finding_codes),
        "required_action": required_action(status, finding_codes),
        "evidence_refs": f"assessment.json#{assessment.workload_id};pre-post-validation-checklist.md#{assessment.workload_id}",
    }


def recovery_status(finding_codes: list[str]) -> str:
    if "backup_not_confirmed" in finding_codes:
        return "blocked"
    if any(code in finding_codes for code in ("backup_recovery_point_stale", "snapshot_age_exceeds_policy", "rollback_owner_missing")):
        return "remediate"
    if "snapshots_present" in finding_codes:
        return "review"
    return "ready"


def required_action(status: str, finding_codes: list[str]) -> str:
    actions: list[str] = []
    if "backup_not_confirmed" in finding_codes:
        actions.append("Confirm recent recoverable backup and restore point before migration approval.")
    if "backup_recovery_point_stale" in finding_codes:
        actions.append("Run or verify a fresh successful backup inside the approved policy window.")
    if "snapshot_age_exceeds_policy" in finding_codes:
        actions.append("Consolidate aged snapshots and confirm datastore capacity before migration planning.")
    elif "snapshots_present" in finding_codes:
        actions.append("Remove, consolidate, or formally approve snapshots before Move staging.")
    if "rollback_owner_missing" in finding_codes:
        actions.append("Assign rollback owner and confirm stop or backout criteria.")
    if actions:
        return " ".join(actions)
    if status == "ready":
        return "Confirm backup, snapshot, and rollback evidence during pre-change review."
    return "Collect recovery evidence before Move staging."


def bool_text(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "unknown"


def text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in RECOVERY_READINESS_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read recovery readiness CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_recovery_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("recovery_readiness_context") if isinstance(assessment.get("recovery_readiness_context"), dict) else {}
    rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != RECOVERY_READINESS_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {RECOVERY_READINESS_SCHEMA_VERSION} recovery readiness context")
    assessments = assessment_rows_by_workload(assessment, errors)
    expected: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json recovery_readiness_context workload row {index} must be an object")
            continue
        workload_id = str(row.get("workload_id") or "")
        if not workload_id:
            errors.append(f"assessment.json recovery_readiness_context workload row {index} missing workload_id")
            continue
        if workload_id in expected:
            errors.append(f"assessment.json recovery_readiness_context duplicate workload_id {workload_id!r}")
        normalized = {column: str(row.get(column) or "") for column in RECOVERY_READINESS_COLUMNS}
        bind_recovery_row_to_assessment(normalized, assessments, errors)
        expected[workload_id] = normalized
    for workload_id in sorted(set(assessments).difference(expected)):
        errors.append(f"assessment.json recovery_readiness_context missing workload_id {workload_id!r}")
    return expected


def assessment_rows_by_workload(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, Any]]:
    rows = assessment.get("assessments") if isinstance(assessment.get("assessments"), list) else []
    if not rows:
        errors.append("assessment.json assessments must contain workload assessment rows")
        return {}
    assessments: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json assessments row {index} must be an object")
            continue
        workload_id = str(row.get("workload_id") or "")
        if not workload_id:
            errors.append(f"assessment.json assessments row {index} missing workload_id")
            continue
        if workload_id in assessments:
            errors.append(f"assessment.json assessments duplicate workload_id {workload_id!r}")
        assessments[workload_id] = row
    return assessments


def bind_recovery_row_to_assessment(
    row: dict[str, str],
    assessments: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    workload_id = row["workload_id"]
    assessment_row = assessments.get(workload_id)
    if not assessment_row:
        errors.append(f"assessment.json recovery_readiness_context references unknown workload_id {workload_id!r}")
        return
    expected_values = {
        "name": str(assessment_row.get("name") or ""),
        "owner": str(assessment_row.get("owner") or ""),
        "target": str(assessment_row.get("target") or ""),
        "readiness": str(assessment_row.get("readiness") or ""),
    }
    finding_codes = [
        str(finding.get("code") or "")
        for finding in assessment_row.get("findings", [])
        if isinstance(finding, dict) and str(finding.get("code") or "") in RECOVERY_FINDINGS
    ]
    status = recovery_status(finding_codes)
    expected_values.update(
        {
            "recovery_status": status,
            "blocking_findings": "; ".join(finding_codes),
            "required_action": required_action(status, finding_codes),
            "evidence_refs": f"assessment.json#{workload_id};pre-post-validation-checklist.md#{workload_id}",
        }
    )
    for field, expected_value in expected_values.items():
        actual = row.get(field, "")
        if actual != expected_value:
            errors.append(
                f"assessment.json recovery_readiness_context {workload_id!r} "
                f"{field} expected {expected_value!r}, got {actual!r}"
            )
