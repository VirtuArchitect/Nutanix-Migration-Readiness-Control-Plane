from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DEPENDENCY_SEQUENCE_COLUMNS = (
    "sequence",
    "workload_id",
    "name",
    "owner",
    "readiness",
    "dependency_count",
    "notes",
)


@dataclass(frozen=True)
class DependencySequenceValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_dependency_sequence(sequence_path: Path, assessment_path: Path) -> DependencySequenceValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(sequence_path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return DependencySequenceValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_sequence_rows(assessment, errors)
    by_workload = {row.get("workload_id", ""): row for row in rows}
    if len(by_workload) != len(rows):
        errors.append("dependency-sequence.csv contains duplicate workload_id rows")

    missing = sorted(set(expected).difference(by_workload))
    extra = sorted(set(by_workload).difference(expected))
    for workload_id in missing:
        errors.append(f"Missing dependency sequence row: {workload_id}")
    for workload_id in extra:
        errors.append(f"Unexpected dependency sequence row: {workload_id}")

    for workload_id, expected_row in expected.items():
        row = by_workload.get(workload_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{workload_id}: {field} expected {expected_value!r}, got {actual!r}")

    expected_order = list(expected)
    actual_order = [row.get("workload_id", "") for row in rows]
    if actual_order != expected_order:
        errors.append(f"dependency sequence order expected {expected_order!r}, got {actual_order!r}")

    return DependencySequenceValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in DEPENDENCY_SEQUENCE_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read dependency sequence CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_sequence_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("dependency_sequence_context") if isinstance(assessment.get("dependency_sequence_context"), dict) else {}
    rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != "nmrcp_dependency_sequence_context_v1":
        errors.append("assessment.json missing nmrcp_dependency_sequence_context_v1 dependency sequence context")

    assessments = assessment_rows_by_id(assessment, errors)
    expected: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        workload_id = str(row.get("workload_id") or "")
        assessment_row = assessments.get(workload_id)
        if not assessment_row:
            errors.append(f"dependency sequence context references unknown assessment workload: {workload_id}")
        else:
            for field in ("name", "owner", "readiness"):
                actual = str(row.get(field) or "")
                expected_value = str(assessment_row.get(field) or ("Unassigned" if field == "owner" else ""))
                if actual != expected_value:
                    errors.append(
                        f"dependency sequence context {workload_id}: {field} does not match assessment row "
                        f"{expected_value!r}"
                    )
        expected[workload_id] = {
            "sequence": str(row.get("sequence") if row.get("sequence") is not None else ""),
            "workload_id": workload_id,
            "name": str(row.get("name") or ""),
            "owner": str(row.get("owner") or "Unassigned"),
            "readiness": str(row.get("readiness") or ""),
            "dependency_count": str(row.get("dependency_count") if row.get("dependency_count") is not None else ""),
            "notes": "dependency-aware included workload order",
        }
    return expected


def assessment_rows_by_id(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, Any]]:
    rows = assessment.get("assessments")
    if not isinstance(rows, list) or not rows:
        errors.append("assessment.json assessments must contain workload assessment rows")
        return {}
    by_id: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json assessments row {index} must be an object")
            continue
        workload_id = str(row.get("workload_id") or "")
        if not workload_id:
            errors.append(f"assessment.json assessments row {index} missing workload_id")
            continue
        by_id[workload_id] = row
    return by_id
