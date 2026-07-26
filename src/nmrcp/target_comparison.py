from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TARGET_COMPARISON_COLUMNS = (
    "workload_id",
    "name",
    "owner",
    "ahv_readiness",
    "ahv_risk_score",
    "ahv_findings",
    "nc2_readiness",
    "nc2_risk_score",
    "nc2_findings",
    "preferred_target",
    "decision_reason",
)


@dataclass(frozen=True)
class TargetComparisonValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_target_readiness_comparison(comparison_path: Path, assessment_path: Path) -> TargetComparisonValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(comparison_path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return TargetComparisonValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_comparison_rows(assessment, errors)
    by_workload = {row.get("workload_id", ""): row for row in rows}
    if len(by_workload) != len(rows):
        errors.append("target-readiness-comparison.csv contains duplicate workload_id rows")

    missing = sorted(set(expected).difference(by_workload))
    extra = sorted(set(by_workload).difference(expected))
    for workload_id in missing:
        errors.append(f"Missing target readiness comparison row: {workload_id}")
    for workload_id in extra:
        errors.append(f"Unexpected target readiness comparison row: {workload_id}")

    for workload_id, expected_row in expected.items():
        row = by_workload.get(workload_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{workload_id}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("target-readiness-comparison.csv cannot be empty")

    return TargetComparisonValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in TARGET_COMPARISON_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read target readiness comparison CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_comparison_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("target_comparison_context") if isinstance(assessment.get("target_comparison_context"), dict) else {}
    rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != "nmrcp_target_comparison_context_v1":
        errors.append("assessment.json missing nmrcp_target_comparison_context_v1 target comparison context")
    assessments = {
        str(item.get("workload_id") or ""): item
        for item in assessment.get("assessments", [])
        if isinstance(item, dict)
    }
    if not assessments:
        errors.append("assessment.json assessments must contain workload assessment rows")

    expected: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json target_comparison_context workload row {index} must be an object")
            continue
        workload_id = str(row.get("workload_id") or "")
        if not workload_id:
            errors.append(f"assessment.json target_comparison_context workload row {index} missing workload_id")
        if workload_id in expected:
            errors.append(f"assessment.json target_comparison_context duplicate workload_id {workload_id!r}")
        assessment_row = assessments.get(workload_id)
        if not assessment_row:
            errors.append(f"assessment.json target_comparison_context references unknown workload_id {workload_id!r}")
        else:
            expected_name = str(assessment_row.get("name") or "")
            expected_owner = str(assessment_row.get("owner") or "Unassigned")
            if str(row.get("name") or "") != expected_name:
                errors.append(
                    f"assessment.json target_comparison_context {workload_id!r} name expected "
                    f"{expected_name!r}, got {str(row.get('name') or '')!r}"
                )
            if str(row.get("owner") or "Unassigned") != expected_owner:
                errors.append(
                    f"assessment.json target_comparison_context {workload_id!r} owner expected "
                    f"{expected_owner!r}, got {str(row.get('owner') or 'Unassigned')!r}"
                )
        expected[workload_id] = {
            "workload_id": workload_id,
            "name": str(row.get("name") or ""),
            "owner": str(row.get("owner") or "Unassigned"),
            "ahv_readiness": str(row.get("ahv_readiness") or ""),
            "ahv_risk_score": text_value(row.get("ahv_risk_score")),
            "ahv_findings": join_list(row.get("ahv_findings")),
            "nc2_readiness": str(row.get("nc2_readiness") or ""),
            "nc2_risk_score": text_value(row.get("nc2_risk_score")),
            "nc2_findings": join_list(row.get("nc2_findings")),
            "preferred_target": str(row.get("preferred_target") or ""),
            "decision_reason": str(row.get("decision_reason") or ""),
        }
    for workload_id in sorted(set(assessments).difference(expected)):
        errors.append(f"assessment.json target_comparison_context missing workload_id {workload_id!r}")
    return expected


def join_list(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value or "")


def text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)
