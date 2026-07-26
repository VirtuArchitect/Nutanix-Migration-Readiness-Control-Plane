from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REMEDIATION_COLUMNS = [
    "status",
    "owner",
    "wave",
    "workload_id",
    "workload_name",
    "target",
    "readiness",
    "risk_score",
    "severity",
    "finding_code",
    "recommended_action",
    "evidence_ref",
    "closure_ref",
    "closed_by",
    "closed_at",
    "notes",
]
ALLOWED_STATUSES = {"open", "closed", "accepted", "waived"}
ALLOWED_READINESS = {"ready", "research", "prepare", "blocked"}
ALLOWED_TARGETS = {"ahv", "nc2"}
ALLOWED_SEVERITIES = {"low", "medium", "high", "critical"}


@dataclass(frozen=True)
class RemediationValidation:
    path: Path
    row_count: int
    open_count: int
    closed_count: int
    accepted_count: int
    waived_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return (
            f"{status}: rows={self.row_count}, open={self.open_count}, closed={self.closed_count}, "
            f"accepted={self.accepted_count}, waived={self.waived_count}, "
            f"errors={len(self.errors)}, warnings={len(self.warnings)}"
        )


@dataclass(frozen=True)
class RemediationTrackerContractValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_remediation_tracker(path: Path, allow_open: bool = False) -> RemediationValidation:
    errors: list[str] = []
    warnings: list[str] = []
    open_count = 0
    closed_count = 0
    accepted_count = 0
    waived_count = 0

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [column for column in REMEDIATION_COLUMNS if column not in fieldnames]
        extra = [column for column in fieldnames if column not in REMEDIATION_COLUMNS]
        if missing:
            errors.append(f"Missing required columns: {', '.join(missing)}")
        if extra:
            warnings.append(f"Unexpected columns ignored by nmrcp validator: {', '.join(extra)}")
        rows = list(reader)

    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, start=2):
        workload_id = (row.get("workload_id") or "").strip()
        workload_name = (row.get("workload_name") or "").strip()
        owner = (row.get("owner") or "").strip()
        wave = (row.get("wave") or "").strip()
        target = (row.get("target") or "").strip()
        readiness = (row.get("readiness") or "").strip()
        severity = (row.get("severity") or "").strip()
        finding_code = (row.get("finding_code") or "").strip()
        recommended_action = (row.get("recommended_action") or "").strip()
        evidence_ref = (row.get("evidence_ref") or "").strip()
        status = (row.get("status") or "").strip().lower()
        closure_ref = (row.get("closure_ref") or "").strip()
        closed_by = (row.get("closed_by") or "").strip()
        closed_at = (row.get("closed_at") or "").strip()
        notes = (row.get("notes") or "").strip()

        if not workload_id:
            errors.append(f"Row {index}: workload_id is required")
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
        if severity not in ALLOWED_SEVERITIES:
            errors.append(f"Row {index}: severity must be one of {', '.join(sorted(ALLOWED_SEVERITIES))}")
        if not finding_code:
            errors.append(f"Row {index}: finding_code is required")
        if not recommended_action:
            errors.append(f"Row {index}: recommended_action is required")
        if not evidence_ref:
            warnings.append(f"Row {index}: evidence_ref should point back to assessment evidence")
        if status not in ALLOWED_STATUSES:
            errors.append(f"Row {index}: status must be one of {', '.join(sorted(ALLOWED_STATUSES))}")

        key = (workload_id, finding_code)
        if key in seen:
            errors.append(f"Row {index}: duplicate remediation row {workload_id}/{finding_code}")
        seen.add(key)

        try:
            risk_score = int(row.get("risk_score") or "")
        except ValueError:
            errors.append(f"Row {index}: risk_score must be an integer")
        else:
            if risk_score < 0 or risk_score > 100:
                errors.append(f"Row {index}: risk_score must be between 0 and 100")

        if status == "open":
            open_count += 1
            if not allow_open:
                errors.append(f"Row {index}: open remediation row blocks final closure")
        elif status == "closed":
            closed_count += 1
            validate_closure_fields(index, closure_ref, closed_by, closed_at, errors)
        elif status == "accepted":
            accepted_count += 1
            validate_closure_fields(index, closure_ref, closed_by, closed_at, errors)
            if severity in {"high", "critical"} and not notes:
                warnings.append(f"Row {index}: accepted {severity} finding should include risk-acceptance notes")
        elif status == "waived":
            waived_count += 1
            validate_closure_fields(index, closure_ref, closed_by, closed_at, errors)
            if not notes:
                warnings.append(f"Row {index}: waived finding should include waiver rationale in notes")

    if not rows:
        errors.append("Remediation tracker cannot be empty")

    return RemediationValidation(
        path=path,
        row_count=len(rows),
        open_count=open_count,
        closed_count=closed_count,
        accepted_count=accepted_count,
        waived_count=waived_count,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_remediation_tracker_contract(tracker_path: Path, assessment_path: Path) -> RemediationTrackerContractValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_remediation_rows(tracker_path, errors, warnings)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return RemediationTrackerContractValidation("fail", len(rows), tuple(errors), tuple(warnings))

    draft = validate_remediation_tracker(tracker_path, allow_open=True)
    draft_errors = tuple(error for error in draft.errors if error != "Remediation tracker cannot be empty")
    errors.extend(draft_errors)
    warnings.extend(draft.warnings)

    expected = expected_remediation_rows(assessment)
    by_key = {(row.get("workload_id", ""), row.get("finding_code", "")): row for row in rows}
    if len(by_key) != len(rows):
        errors.append("remediation-tracker.csv contains duplicate workload_id/finding_code rows")

    missing = sorted(set(expected).difference(by_key))
    extra = sorted(set(by_key).difference(expected))
    for workload_id, finding_code in missing:
        errors.append(f"Missing remediation tracker row: {workload_id}/{finding_code}")
    for workload_id, finding_code in extra:
        errors.append(f"Unexpected remediation tracker row: {workload_id}/{finding_code}")

    for key, expected_row in expected.items():
        row = by_key.get(key)
        if not row:
            continue
        label = f"{key[0]}/{key[1]}"
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{label}: {field} expected {expected_value!r}, got {actual!r}")

    if expected and not rows:
        errors.append("remediation-tracker.csv cannot be empty when assessment findings exist")
    if not expected and rows:
        errors.append("remediation-tracker.csv must be empty except header when assessment has no findings")

    return RemediationTrackerContractValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def read_remediation_rows(path: Path, errors: list[str], warnings: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in REMEDIATION_COLUMNS if column not in fieldnames]
            extra = [column for column in fieldnames if column not in REMEDIATION_COLUMNS]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            if extra:
                warnings.append(f"Unexpected columns ignored by nmrcp validator: {', '.join(extra)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read remediation tracker: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_remediation_rows(assessment: dict[str, Any]) -> dict[tuple[str, str], dict[str, str]]:
    wave_by_workload = {
        workload_id: str(wave.get("name") or "Unassigned")
        for wave in assessment.get("waves", [])
        if isinstance(wave, dict)
        for workload_id in wave.get("workload_ids", [])
        if isinstance(workload_id, str)
    }

    expected: dict[tuple[str, str], dict[str, str]] = {}
    for row in assessment.get("assessments", []):
        if not isinstance(row, dict):
            continue
        workload_id = str(row.get("workload_id") or "")
        findings = row.get("findings") if isinstance(row.get("findings"), list) else []
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            finding_code = str(finding.get("code") or "")
            expected[(workload_id, finding_code)] = {
                "status": "open",
                "owner": str(row.get("owner") or "Unassigned"),
                "wave": wave_by_workload.get(workload_id, "Unassigned"),
                "workload_id": workload_id,
                "workload_name": str(row.get("name") or ""),
                "target": str(row.get("target") or ""),
                "readiness": str(row.get("readiness") or ""),
                "risk_score": str(int(row.get("risk_score") or 0)),
                "severity": str(finding.get("severity") or ""),
                "finding_code": finding_code,
                "recommended_action": str(finding.get("recommended_action") or ""),
                "evidence_ref": f"assessment.json#{workload_id}/{finding_code}",
                "closure_ref": "",
                "closed_by": "",
                "closed_at": "",
                "notes": "",
            }
    return expected


def validate_closure_fields(
    index: int,
    closure_ref: str,
    closed_by: str,
    closed_at: str,
    errors: list[str],
) -> None:
    if not closure_ref:
        errors.append(f"Row {index}: closure_ref is required when status is closed, accepted, or waived")
    if not closed_by:
        errors.append(f"Row {index}: closed_by is required when status is closed, accepted, or waived")
    if not closed_at:
        errors.append(f"Row {index}: closed_at is required when status is closed, accepted, or waived")
