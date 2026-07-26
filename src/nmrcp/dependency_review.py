from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import WorkloadAssessment


DEPENDENCY_REVIEW_SCHEMA_VERSION = "nmrcp_dependency_review_v1"
DEPENDENCY_REVIEW_COLUMNS = (
    "schema_version",
    "row_type",
    "source_workload_id",
    "source_name",
    "source_owner",
    "target",
    "source_readiness",
    "dependency_name",
    "dependency_id",
    "dependency_type",
    "dependency_owner",
    "criticality",
    "dependency_scope",
    "dependency_readiness",
    "stage_impact",
    "blocking_findings",
    "required_action",
    "evidence_refs",
    "notes",
)


@dataclass(frozen=True)
class DependencyReviewValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def dependency_review_context(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
) -> dict[str, Any]:
    workloads = [
        workload for workload in inventory.get("workloads", []) if isinstance(workload, dict)
    ]
    assessments_by_id = {assessment.workload_id: assessment for assessment in assessments}
    assessments_by_name = {assessment.name: assessment for assessment in assessments}
    rows: list[dict[str, str]] = []
    for workload in workloads:
        workload_id = str(workload.get("id") or workload.get("name") or "")
        assessment = assessments_by_id.get(workload_id) or assessments_by_name.get(str(workload.get("name") or ""))
        dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
        for dependency in dependencies:
            if isinstance(dependency, dict):
                rows.append(dependency_review_row(workload, dependency, assessment, assessments_by_id, assessments_by_name))

    unmatched = inventory.get("unmatched_dependencies") if isinstance(inventory.get("unmatched_dependencies"), list) else []
    for dependency in unmatched:
        if isinstance(dependency, dict):
            rows.append(unmatched_dependency_row(dependency))

    return {
        "schema_version": DEPENDENCY_REVIEW_SCHEMA_VERSION,
        "dependencies": rows,
    }


def write_dependency_review_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    path: Path,
) -> None:
    rows = dependency_review_context(inventory, assessments)["dependencies"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=DEPENDENCY_REVIEW_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_dependency_review(path: Path, assessment_path: Path) -> DependencyReviewValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return DependencyReviewValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_dependency_review_rows(assessment, errors)
    keyed_rows = {row_key(row): row for row in rows}
    if len(keyed_rows) != len(rows):
        errors.append("dependency-review.csv contains duplicate dependency rows")

    missing = sorted(set(expected).difference(keyed_rows))
    extra = sorted(set(keyed_rows).difference(expected))
    for key in missing:
        errors.append(f"Missing dependency review row: {key}")
    for key in extra:
        errors.append(f"Unexpected dependency review row: {key}")

    for key, expected_row in expected.items():
        row = keyed_rows.get(key)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{key}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows and expected:
        errors.append("dependency-review.csv cannot be empty when assessment dependency context exists")

    return DependencyReviewValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def dependency_review_row(
    workload: dict[str, Any],
    dependency: dict[str, Any],
    assessment: WorkloadAssessment | None,
    assessments_by_id: dict[str, WorkloadAssessment],
    assessments_by_name: dict[str, WorkloadAssessment],
) -> dict[str, str]:
    dependency_name = str(dependency.get("name") or dependency.get("dependency_name") or "").strip()
    dependency_id = str(dependency.get("id") or dependency.get("dependency_id") or "").strip()
    dependency_assessment = assessments_by_id.get(dependency_id) or assessments_by_name.get(dependency_name)
    dependency_type = str(dependency.get("type") or dependency.get("dependency_type") or "application").strip() or "application"
    owner = str(dependency.get("owner") or "").strip()
    criticality = str(dependency.get("criticality") or "unspecified").strip() or "unspecified"
    scope = "internal" if dependency_assessment else "external"
    dependency_readiness = dependency_assessment.readiness if dependency_assessment else "not assessed"
    blockers = dependency_blockers(owner, dependency_assessment)
    impact = dependency_stage_impact(blockers, scope, criticality)
    source_id = str(workload.get("id") or workload.get("name") or "").strip()
    source_name = str(workload.get("name") or source_id).strip()
    return {
        "schema_version": DEPENDENCY_REVIEW_SCHEMA_VERSION,
        "row_type": "dependency",
        "source_workload_id": source_id,
        "source_name": source_name,
        "source_owner": str(workload.get("owner") or "Unassigned").strip() or "Unassigned",
        "target": assessment.target if assessment else "",
        "source_readiness": assessment.readiness if assessment else "not assessed",
        "dependency_name": dependency_name,
        "dependency_id": dependency_id,
        "dependency_type": dependency_type,
        "dependency_owner": owner or "not assigned",
        "criticality": criticality,
        "dependency_scope": scope,
        "dependency_readiness": dependency_readiness,
        "stage_impact": impact,
        "blocking_findings": "; ".join(blockers),
        "required_action": dependency_required_action(impact, blockers, scope),
        "evidence_refs": f"assessment.json#{source_id};dependency-review.csv#{source_id}",
        "notes": str(dependency.get("notes") or "").strip(),
    }


def unmatched_dependency_row(dependency: dict[str, Any]) -> dict[str, str]:
    dependency_name = str(dependency.get("dependency_name") or dependency.get("name") or "").strip()
    source_id = str(dependency.get("source_id") or "").strip()
    source_name = str(dependency.get("source_name") or "").strip()
    owner = str(dependency.get("owner") or "").strip()
    blockers = ["unmatched_dependency_source"]
    if not owner:
        blockers.append("dependency_owner_missing")
    return {
        "schema_version": DEPENDENCY_REVIEW_SCHEMA_VERSION,
        "row_type": "unmatched_dependency",
        "source_workload_id": source_id,
        "source_name": source_name,
        "source_owner": "not matched",
        "target": "",
        "source_readiness": "unmatched",
        "dependency_name": dependency_name,
        "dependency_id": str(dependency.get("dependency_id") or "").strip(),
        "dependency_type": str(dependency.get("dependency_type") or dependency.get("type") or "application").strip() or "application",
        "dependency_owner": owner or "not assigned",
        "criticality": str(dependency.get("criticality") or "unspecified").strip() or "unspecified",
        "dependency_scope": "unmatched",
        "dependency_readiness": "not assessed",
        "stage_impact": "cleanup",
        "blocking_findings": "; ".join(blockers),
        "required_action": "Resolve unmatched dependency source before relying on dependency sequencing.",
        "evidence_refs": "assessment.json#unmatched_dependencies",
        "notes": str(dependency.get("notes") or "").strip(),
    }


def dependency_blockers(owner: str, dependency_assessment: WorkloadAssessment | None) -> list[str]:
    blockers: list[str] = []
    if not owner:
        blockers.append("dependency_owner_missing")
    if dependency_assessment and dependency_assessment.readiness in {"prepare", "blocked"}:
        blockers.append("dependency_not_ready")
    return blockers


def dependency_stage_impact(blockers: list[str], scope: str, criticality: str) -> str:
    if blockers:
        return "blocks_staging"
    if scope == "external" or criticality.lower() in {"high", "critical"}:
        return "review"
    return "ready"


def dependency_required_action(impact: str, blockers: list[str], scope: str) -> str:
    actions: list[str] = []
    if "dependency_owner_missing" in blockers:
        actions.append("Assign dependency owner before Move staging.")
    if "dependency_not_ready" in blockers:
        actions.append("Migrate or remediate internal dependency before dependent workload.")
    if actions:
        return " ".join(actions)
    if impact == "review" and scope == "external":
        return "Confirm external dependency connectivity, owner, and validation plan before staging."
    if impact == "review":
        return "Confirm high-criticality dependency order and validation plan before staging."
    return "Confirm dependency remains reachable during pre/post validation."


def row_key(row: dict[str, str]) -> str:
    return "|".join(
        [
            row.get("row_type", ""),
            row.get("source_workload_id", ""),
            row.get("dependency_name", ""),
            row.get("dependency_id", ""),
        ]
    )


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in DEPENDENCY_REVIEW_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read dependency review CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_dependency_review_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("dependency_review_context") if isinstance(assessment.get("dependency_review_context"), dict) else {}
    rows = context.get("dependencies") if isinstance(context.get("dependencies"), list) else []
    if context.get("schema_version") != DEPENDENCY_REVIEW_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {DEPENDENCY_REVIEW_SCHEMA_VERSION} dependency review context")
    expected: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        expected[row_key({key: str(row.get(key) or "") for key in DEPENDENCY_REVIEW_COLUMNS})] = {
            column: str(row.get(column) or "") for column in DEPENDENCY_REVIEW_COLUMNS
        }
    return expected
