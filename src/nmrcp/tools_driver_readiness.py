from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import WorkloadAssessment


TOOLS_DRIVER_SCHEMA_VERSION = "nmrcp_tools_driver_readiness_v1"
TOOLS_DRIVER_COLUMNS = (
    "schema_version",
    "workload_id",
    "name",
    "owner",
    "target",
    "readiness",
    "vmware_tools",
    "tools_status",
    "virtio_ready",
    "driver_status",
    "blocking_findings",
    "required_action",
    "evidence_refs",
)
TOOLS_DRIVER_FINDINGS = {"vmware_tools_missing", "vmware_tools_outdated", "virtio_not_ready"}


@dataclass(frozen=True)
class ToolsDriverReadinessValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def tools_driver_context(inventory: dict[str, Any], assessments: list[WorkloadAssessment]) -> dict[str, Any]:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    return {
        "schema_version": TOOLS_DRIVER_SCHEMA_VERSION,
        "workloads": [tools_driver_row(workloads.get(assessment.workload_id, {}), assessment) for assessment in assessments],
    }


def write_tools_driver_readiness_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    path: Path,
) -> None:
    rows = tools_driver_context(inventory, assessments)["workloads"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=TOOLS_DRIVER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_tools_driver_readiness(path: Path, assessment_path: Path) -> ToolsDriverReadinessValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return ToolsDriverReadinessValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_tools_driver_rows(assessment, errors)
    by_workload = {row.get("workload_id", ""): row for row in rows}
    if len(by_workload) != len(rows):
        errors.append("tools-driver-readiness.csv contains duplicate workload_id rows")

    missing = sorted(set(expected).difference(by_workload))
    extra = sorted(set(by_workload).difference(expected))
    for workload_id in missing:
        errors.append(f"Missing tools driver readiness row: {workload_id}")
    for workload_id in extra:
        errors.append(f"Unexpected tools driver readiness row: {workload_id}")

    for workload_id, expected_row in expected.items():
        row = by_workload.get(workload_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{workload_id}: {field} expected {expected_value!r}, got {actual!r}")
    if not rows:
        errors.append("tools-driver-readiness.csv cannot be empty")

    return ToolsDriverReadinessValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def tools_driver_row(workload: dict[str, Any], assessment: WorkloadAssessment) -> dict[str, str]:
    tools = workload.get("tools") if isinstance(workload.get("tools"), dict) else {}
    finding_codes = [finding.code for finding in assessment.findings if finding.code in TOOLS_DRIVER_FINDINGS]
    status = driver_status(tools, finding_codes)
    return {
        "schema_version": TOOLS_DRIVER_SCHEMA_VERSION,
        "workload_id": assessment.workload_id,
        "name": assessment.name,
        "owner": assessment.owner,
        "target": assessment.target,
        "readiness": assessment.readiness,
        "vmware_tools": bool_text(tools.get("vmware_tools")),
        "tools_status": str(tools.get("status") or "unknown"),
        "virtio_ready": bool_text(tools.get("virtio_ready")),
        "driver_status": status,
        "blocking_findings": "; ".join(finding_codes),
        "required_action": required_action(status, finding_codes),
        "evidence_refs": f"assessment.json#{assessment.workload_id};pre-post-validation-checklist.md#{assessment.workload_id}",
    }


def driver_status(tools: dict[str, Any], finding_codes: list[str]) -> str:
    if "vmware_tools_missing" in finding_codes:
        return "blocked"
    if "virtio_not_ready" in finding_codes or "vmware_tools_outdated" in finding_codes:
        return "remediate"
    if tools.get("vmware_tools") is True and tools.get("virtio_ready") is True:
        return "ready"
    return "research"


def required_action(status: str, finding_codes: list[str]) -> str:
    actions: list[str] = []
    if "vmware_tools_missing" in finding_codes:
        actions.append("Repair guest tools or capture approved alternate guest evidence before staging.")
    if "vmware_tools_outdated" in finding_codes:
        actions.append("Upgrade guest tools or document accepted tooling state before cutover.")
    if "virtio_not_ready" in finding_codes:
        actions.append("Install or validate Nutanix VirtIO drivers before cutover.")
    if actions:
        return " ".join(actions)
    if status == "ready":
        return "Confirm guest tools and driver state during pre/post validation."
    return "Collect guest tools and VirtIO readiness evidence before Move staging."


def bool_text(value: Any) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "unknown"


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in TOOLS_DRIVER_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read tools driver readiness CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_tools_driver_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("tools_driver_context") if isinstance(assessment.get("tools_driver_context"), dict) else {}
    rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != TOOLS_DRIVER_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {TOOLS_DRIVER_SCHEMA_VERSION} tools driver context")
    expected: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        workload_id = str(row.get("workload_id") or "")
        expected[workload_id] = {column: str(row.get(column) or "") for column in TOOLS_DRIVER_COLUMNS}
    return expected
