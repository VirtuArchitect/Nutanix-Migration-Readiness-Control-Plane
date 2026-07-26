from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import WorkloadAssessment


CONNECTIVITY_CHECKLIST_SCHEMA_VERSION = "nmrcp_connectivity_checklist_v1"
CONNECTIVITY_CHECKLIST_COLUMNS = (
    "schema_version",
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
    "direction",
    "protocol",
    "ports",
    "validation_method",
    "connectivity_status",
    "required_action",
    "evidence_refs",
    "notes",
)


@dataclass(frozen=True)
class ConnectivityChecklistValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def connectivity_checklist_context(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
) -> dict[str, Any]:
    workloads = [workload for workload in inventory.get("workloads", []) if isinstance(workload, dict)]
    assessments_by_id = {assessment.workload_id: assessment for assessment in assessments}
    assessments_by_name = {assessment.name: assessment for assessment in assessments}
    rows: list[dict[str, str]] = []
    for workload in workloads:
        workload_id = str(workload.get("id") or workload.get("name") or "")
        assessment = assessments_by_id.get(workload_id) or assessments_by_name.get(str(workload.get("name") or ""))
        dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
        for dependency in dependencies:
            if isinstance(dependency, dict):
                rows.append(connectivity_row(workload, dependency, assessment))
    return {
        "schema_version": CONNECTIVITY_CHECKLIST_SCHEMA_VERSION,
        "connections": rows,
    }


def write_connectivity_checklist_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    path: Path,
) -> None:
    rows = connectivity_checklist_context(inventory, assessments)["connections"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CONNECTIVITY_CHECKLIST_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_connectivity_checklist(path: Path, assessment_path: Path) -> ConnectivityChecklistValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return ConnectivityChecklistValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_connectivity_rows(assessment, errors)
    keyed_rows = {row_key(row): row for row in rows}
    if len(keyed_rows) != len(rows):
        errors.append("connectivity-checklist.csv contains duplicate connection rows")

    missing = sorted(set(expected).difference(keyed_rows))
    extra = sorted(set(keyed_rows).difference(expected))
    for key in missing:
        errors.append(f"Missing connectivity checklist row: {key}")
    for key in extra:
        errors.append(f"Unexpected connectivity checklist row: {key}")

    for key, expected_row in expected.items():
        row = keyed_rows.get(key)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{key}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows and expected:
        errors.append("connectivity-checklist.csv cannot be empty when assessment connectivity context exists")

    unknowns = sum(1 for row in rows if row.get("connectivity_status") == "needs_discovery")
    if unknowns:
        warnings.append(f"{unknowns} connection rows need port/protocol discovery")
    return ConnectivityChecklistValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def connectivity_row(
    workload: dict[str, Any],
    dependency: dict[str, Any],
    assessment: WorkloadAssessment | None,
) -> dict[str, str]:
    source_id = str(workload.get("id") or workload.get("name") or "").strip()
    dependency_name = str(dependency.get("name") or dependency.get("dependency_name") or "").strip()
    dependency_id = str(dependency.get("id") or dependency.get("dependency_id") or "").strip()
    protocol = str(dependency.get("protocol") or "").strip().lower()
    ports = str(dependency.get("ports") or dependency.get("port") or "").strip()
    owner = str(dependency.get("owner") or "").strip()
    validation_method = str(dependency.get("validation_method") or "").strip()
    status = connectivity_status(owner=owner, protocol=protocol, ports=ports, validation_method=validation_method)
    return {
        "schema_version": CONNECTIVITY_CHECKLIST_SCHEMA_VERSION,
        "source_workload_id": source_id,
        "source_name": str(workload.get("name") or source_id).strip(),
        "source_owner": str(workload.get("owner") or "Unassigned").strip() or "Unassigned",
        "target": assessment.target if assessment else "",
        "source_readiness": assessment.readiness if assessment else "not assessed",
        "dependency_name": dependency_name,
        "dependency_id": dependency_id,
        "dependency_type": str(dependency.get("type") or dependency.get("dependency_type") or "application").strip() or "application",
        "dependency_owner": owner or "not assigned",
        "criticality": str(dependency.get("criticality") or "unspecified").strip() or "unspecified",
        "direction": str(dependency.get("direction") or "egress").strip() or "egress",
        "protocol": protocol or "unknown",
        "ports": ports or "unknown",
        "validation_method": validation_method or "application_owner_test",
        "connectivity_status": status,
        "required_action": required_action(status),
        "evidence_refs": f"assessment.json#{source_id};connectivity-checklist.csv#{source_id};dependency-review.csv#{source_id}",
        "notes": str(dependency.get("notes") or "").strip(),
    }


def connectivity_status(*, owner: str, protocol: str, ports: str, validation_method: str) -> str:
    if not owner:
        return "blocked"
    if not protocol or not ports:
        return "needs_discovery"
    if not validation_method:
        return "needs_validation_plan"
    return "ready"


def required_action(status: str) -> str:
    if status == "blocked":
        return "Assign dependency or service owner before firewall and application validation planning."
    if status == "needs_discovery":
        return "Capture protocol, port, and direction before Move staging or firewall change review."
    if status == "needs_validation_plan":
        return "Define the application or network validation method before cutover approval."
    return "Confirm firewall, routing, DNS, and application reachability during pre/post validation."


def row_key(row: dict[str, str]) -> str:
    return "|".join(
        [
            row.get("source_workload_id", ""),
            row.get("dependency_name", ""),
            row.get("dependency_id", ""),
            row.get("direction", ""),
            row.get("protocol", ""),
            row.get("ports", ""),
        ]
    )


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in CONNECTIVITY_CHECKLIST_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read connectivity checklist CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_connectivity_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("connectivity_checklist_context") if isinstance(assessment.get("connectivity_checklist_context"), dict) else {}
    rows = context.get("connections") if isinstance(context.get("connections"), list) else []
    if context.get("schema_version") != CONNECTIVITY_CHECKLIST_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {CONNECTIVITY_CHECKLIST_SCHEMA_VERSION} connectivity checklist context")
    expected: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = {key: str(row.get(key) or "") for key in CONNECTIVITY_CHECKLIST_COLUMNS}
        expected[row_key(normalized)] = normalized
    return expected
