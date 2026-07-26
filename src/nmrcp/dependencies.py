from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from .models import Finding, WorkloadAssessment


DEPENDENCY_FIELDS = {
    "source_id",
    "source_name",
    "dependency_name",
    "dependency_id",
    "dependency_type",
    "owner",
    "criticality",
    "protocol",
    "ports",
    "direction",
    "validation_method",
    "notes",
}


def read_dependency_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = {"dependency_name"} - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Dependency CSV missing required columns: {', '.join(sorted(missing))}")
        return [
            {key: (value or "").strip() for key, value in row.items() if key in DEPENDENCY_FIELDS}
            for row in reader
        ]


def merge_dependencies(inventory: dict[str, Any], dependencies: list[dict[str, str]]) -> dict[str, Any]:
    workloads = inventory.get("workloads")
    if not isinstance(workloads, list):
        raise ValueError("Inventory must contain a workloads list")

    by_id = {str(workload.get("id")): workload for workload in workloads if isinstance(workload, dict)}
    by_name = {str(workload.get("name")): workload for workload in workloads if isinstance(workload, dict)}
    unmatched: list[dict[str, str]] = []

    for dependency in dependencies:
        source_id = dependency.get("source_id", "")
        source_name = dependency.get("source_name", "")
        workload = by_id.get(source_id) or by_name.get(source_name)
        if workload is None:
            unmatched.append(dependency)
            continue
        workload_dependencies = workload.setdefault("dependencies", [])
        if not isinstance(workload_dependencies, list):
            workload_dependencies = []
            workload["dependencies"] = workload_dependencies
        dependency_record = {
            "name": dependency.get("dependency_name", ""),
            "id": dependency.get("dependency_id", ""),
            "type": dependency.get("dependency_type", "application"),
            "owner": dependency.get("owner", ""),
            "criticality": dependency.get("criticality", ""),
            "protocol": dependency.get("protocol", ""),
            "ports": dependency.get("ports", ""),
            "direction": dependency.get("direction", ""),
            "validation_method": dependency.get("validation_method", ""),
            "notes": dependency.get("notes", ""),
        }
        existing_dependency = find_matching_dependency(workload_dependencies, dependency_record)
        if existing_dependency is None:
            workload_dependencies.append(dependency_record)
        else:
            merge_dependency_record(existing_dependency, dependency_record)

    source = inventory.setdefault("source", {})
    if isinstance(source, dict):
        source["dependency_records"] = len(dependencies)
        source["dependency_unmatched_records"] = len(unmatched)
    inventory["unmatched_dependencies"] = unmatched
    return inventory


def find_matching_dependency(
    existing_dependencies: list[Any],
    dependency: dict[str, str],
) -> dict[str, Any] | None:
    dependency_id = str(dependency.get("id") or "").strip()
    dependency_name = str(dependency.get("name") or "").strip().lower()
    for existing in existing_dependencies:
        if not isinstance(existing, dict):
            continue
        existing_id = str(existing.get("id") or "").strip()
        existing_name = str(existing.get("name") or "").strip().lower()
        if dependency_id and existing_id and dependency_id == existing_id:
            return existing
        if dependency_name and existing_name and dependency_name == existing_name:
            return existing
    return None


def merge_dependency_record(existing: dict[str, Any], incoming: dict[str, str]) -> None:
    for key, value in incoming.items():
        if value:
            existing[key] = value


def apply_dependency_readiness_gates(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
) -> list[WorkloadAssessment]:
    workload_records = [
        workload for workload in inventory.get("workloads", []) if isinstance(workload, dict)
    ]
    id_to_assessment = {assessment.workload_id: assessment for assessment in assessments}
    name_to_assessment = {assessment.name: assessment for assessment in assessments}
    gated: list[WorkloadAssessment] = []

    for assessment in assessments:
        blockers: list[WorkloadAssessment] = []
        workload = next(
            (
                item
                for item in workload_records
                if str(item.get("id") or item.get("name")) == assessment.workload_id
            ),
            {},
        )
        dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
        for dependency in dependencies:
            if not isinstance(dependency, dict):
                continue
            dependency_assessment = id_to_assessment.get(str(dependency.get("id"))) or name_to_assessment.get(
                str(dependency.get("name"))
            )
            if dependency_assessment and dependency_assessment.readiness in {"prepare", "blocked"}:
                blockers.append(dependency_assessment)

        if blockers and assessment.readiness in {"ready", "research"}:
            blocker_summary = ", ".join(f"{item.workload_id}:{item.readiness}" for item in blockers)
            finding = Finding(
                "dependency_not_ready",
                "high",
                f"One or more internal dependencies are not migration-ready: {blocker_summary}.",
                "Schedule dependency remediation or migrate the dependency before this workload.",
            )
            gated.append(
                WorkloadAssessment(
                    workload_id=assessment.workload_id,
                    name=assessment.name,
                    owner=assessment.owner,
                    readiness="prepare",
                    risk_score=min(assessment.risk_score + 25, 100),
                    target=assessment.target,
                    findings=assessment.findings + (finding,),
                )
            )
        else:
            gated.append(assessment)
    return gated


def dependency_sequence(inventory: dict[str, Any], assessments: list[WorkloadAssessment]) -> list[str]:
    workload_records = [
        workload for workload in inventory.get("workloads", []) if isinstance(workload, dict)
    ]
    ids_by_name = {
        str(workload.get("name")): str(workload.get("id") or workload.get("name"))
        for workload in workload_records
        if isinstance(workload, dict)
    }
    assessment_ids = {assessment.workload_id for assessment in assessments}
    included_ids = {
        assessment.workload_id
        for assessment in assessments
        if assessment.readiness in {"ready", "research"}
    }
    edges: dict[str, set[str]] = {workload_id: set() for workload_id in included_ids}
    for workload in workload_records:
        workload_id = str(workload.get("id") or workload.get("name"))
        if workload_id not in included_ids:
            continue
        dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
        for dependency in dependencies:
            if not isinstance(dependency, dict):
                continue
            dependency_id = str(dependency.get("id") or "")
            dependency_name = str(dependency.get("name") or "")
            normalized_dependency_id = dependency_id if dependency_id in assessment_ids else ids_by_name.get(dependency_name)
            if normalized_dependency_id in included_ids and normalized_dependency_id != workload_id:
                edges[workload_id].add(normalized_dependency_id)

    ordered: list[str] = []
    remaining = {workload_id: set(depends_on) for workload_id, depends_on in edges.items()}
    while remaining:
        ready = sorted(workload_id for workload_id, depends_on in remaining.items() if not depends_on)
        if not ready:
            ordered.extend(sorted(remaining))
            break
        ordered.extend(ready)
        for workload_id in ready:
            remaining.pop(workload_id)
        for depends_on in remaining.values():
            depends_on.difference_update(ready)
    return ordered
