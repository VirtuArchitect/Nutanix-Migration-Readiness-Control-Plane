from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import WorkloadAssessment


PRISM_CATEGORY_SCHEMA_VERSION = "nmrcp_prism_category_mapping_v1"
PRISM_CATEGORY_COLUMNS = (
    "schema_version",
    "workload_id",
    "name",
    "owner",
    "tier",
    "readiness",
    "source_tags",
    "category_assignments",
    "apply_scope",
    "review_status",
    "required_action",
)


@dataclass(frozen=True)
class PrismCategoryValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def prism_category_context(inventory: dict[str, Any], assessments: list[WorkloadAssessment]) -> dict[str, Any]:
    workloads = {
        str(workload.get("id") or workload.get("name") or "unknown"): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    return {
        "schema_version": PRISM_CATEGORY_SCHEMA_VERSION,
        "workloads": [
            prism_category_row(workloads.get(assessment.workload_id, {}), assessment)
            for assessment in assessments
        ],
    }


def write_prism_category_mapping_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    path: Path,
) -> None:
    rows = prism_category_context(inventory, assessments)["workloads"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PRISM_CATEGORY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_prism_category_mapping(mapping_path: Path, assessment_path: Path) -> PrismCategoryValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(mapping_path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return PrismCategoryValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_category_rows(assessment, errors)
    by_workload = {row.get("workload_id", ""): row for row in rows}
    if len(by_workload) != len(rows):
        errors.append("prism-category-mapping.csv contains duplicate workload_id rows")

    missing = sorted(set(expected).difference(by_workload))
    extra = sorted(set(by_workload).difference(expected))
    for workload_id in missing:
        errors.append(f"Missing Prism category mapping row: {workload_id}")
    for workload_id in extra:
        errors.append(f"Unexpected Prism category mapping row: {workload_id}")

    for workload_id, expected_row in expected.items():
        row = by_workload.get(workload_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{workload_id}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("prism-category-mapping.csv cannot be empty")

    return PrismCategoryValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def prism_category_row(workload: dict[str, Any], assessment: WorkloadAssessment) -> dict[str, str]:
    tier = normalize_text(workload.get("tier") or "unknown")
    tags = sorted({normalize_text(tag) for tag in workload.get("tags", []) if str(tag).strip()}) if isinstance(workload.get("tags"), list) else []
    assignments = {
        "NMRCP:Owner": normalize_text(assessment.owner or "Unassigned"),
        "NMRCP:Tier": tier,
        "NMRCP:Readiness": normalize_text(assessment.readiness),
        "NMRCP:WaveIntent": wave_intent(assessment.readiness),
    }
    if tags:
        assignments["NMRCP:SourceTags"] = "|".join(tags)
    return {
        "schema_version": PRISM_CATEGORY_SCHEMA_VERSION,
        "workload_id": assessment.workload_id,
        "name": assessment.name,
        "owner": assessment.owner,
        "tier": tier,
        "readiness": assessment.readiness,
        "source_tags": ";".join(tags),
        "category_assignments": ";".join(f"{key}={value}" for key, value in assignments.items()),
        "apply_scope": "review_only_prism_category_plan",
        "review_status": "required",
        "required_action": required_action(assessment.readiness),
    }


def normalize_text(value: object) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9_.:-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text or "unknown"


def wave_intent(readiness: str) -> str:
    if readiness in {"ready", "research"}:
        return "candidate"
    return "hold"


def required_action(readiness: str) -> str:
    if readiness in {"ready", "research"}:
        return "Review target Prism categories with platform owner before Move staging."
    return "Keep category plan in review until readiness blockers are cleared."


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in PRISM_CATEGORY_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read Prism category mapping CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_category_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("prism_category_context") if isinstance(assessment.get("prism_category_context"), dict) else {}
    rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != PRISM_CATEGORY_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {PRISM_CATEGORY_SCHEMA_VERSION} Prism category context")
    assessments = assessment_rows_by_workload(assessment, errors)
    expected: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json prism_category_context workload row {index} must be an object")
            continue
        workload_id = str(row.get("workload_id") or "")
        if not workload_id:
            errors.append(f"assessment.json prism_category_context workload row {index} missing workload_id")
            continue
        if workload_id in expected:
            errors.append(f"assessment.json prism_category_context duplicate workload_id {workload_id!r}")
        normalized = {column: str(row.get(column) or "") for column in PRISM_CATEGORY_COLUMNS}
        bind_category_row_to_assessment(normalized, assessments, errors)
        expected[workload_id] = normalized
    for workload_id in sorted(set(assessments).difference(expected)):
        errors.append(f"assessment.json prism_category_context missing workload_id {workload_id!r}")
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


def bind_category_row_to_assessment(
    row: dict[str, str],
    assessments: dict[str, dict[str, Any]],
    errors: list[str],
) -> None:
    workload_id = row["workload_id"]
    assessment_row = assessments.get(workload_id)
    if not assessment_row:
        errors.append(f"assessment.json prism_category_context references unknown workload_id {workload_id!r}")
        return
    expected_values = {
        "name": str(assessment_row.get("name") or ""),
        "owner": str(assessment_row.get("owner") or ""),
        "readiness": str(assessment_row.get("readiness") or ""),
    }
    for field, expected_value in expected_values.items():
        actual = row.get(field, "")
        if actual != expected_value:
            errors.append(
                f"assessment.json prism_category_context {workload_id!r} "
                f"{field} expected {expected_value!r}, got {actual!r}"
            )
    assignments = parse_category_assignments(row.get("category_assignments", ""))
    expected_assignment_values = {
        "NMRCP:Owner": normalize_text(expected_values["owner"] or "Unassigned"),
        "NMRCP:Readiness": normalize_text(expected_values["readiness"]),
        "NMRCP:WaveIntent": wave_intent(expected_values["readiness"]),
    }
    for key, expected_value in expected_assignment_values.items():
        actual = assignments.get(key, "")
        if actual != expected_value:
            errors.append(
                f"assessment.json prism_category_context {workload_id!r} "
                f"{key} expected {expected_value!r}, got {actual!r}"
            )


def parse_category_assignments(value: str) -> dict[str, str]:
    assignments: dict[str, str] = {}
    for item in value.split(";"):
        key, separator, raw_value = item.partition("=")
        if separator:
            assignments[key] = raw_value
    return assignments
