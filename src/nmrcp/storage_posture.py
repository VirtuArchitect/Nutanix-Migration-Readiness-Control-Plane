from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import WorkloadAssessment


STORAGE_POSTURE_SCHEMA_VERSION = "nmrcp_storage_posture_v1"
STORAGE_POSTURE_COLUMNS = (
    "schema_version",
    "workload_id",
    "name",
    "owner",
    "target",
    "readiness",
    "disk_count",
    "disk_gib",
    "thin_provisioned",
    "raw_device_mapping",
    "shared_disk",
    "independent_disk",
    "encrypted",
    "datastores",
    "min_datastore_free_percent",
    "storage_status",
    "blocking_findings",
    "required_action",
    "evidence_refs",
)
STORAGE_FINDINGS = {
    "storage_rdm_mapping_required",
    "shared_disk_cluster_review",
    "independent_disk_review",
    "encrypted_disk_review",
    "datastore_free_space_low",
}


@dataclass(frozen=True)
class StoragePostureValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def storage_posture_context(inventory: dict[str, Any], assessments: list[WorkloadAssessment]) -> dict[str, Any]:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    return {
        "schema_version": STORAGE_POSTURE_SCHEMA_VERSION,
        "workloads": [storage_posture_row(workloads.get(assessment.workload_id, {}), assessment) for assessment in assessments],
    }


def write_storage_posture_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    path: Path,
) -> None:
    rows = storage_posture_context(inventory, assessments)["workloads"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STORAGE_POSTURE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_storage_posture(path: Path, assessment_path: Path) -> StoragePostureValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return StoragePostureValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_storage_posture_rows(assessment, errors)
    by_workload = {row.get("workload_id", ""): row for row in rows}
    if len(by_workload) != len(rows):
        errors.append("storage-posture.csv contains duplicate workload_id rows")

    missing = sorted(set(expected).difference(by_workload))
    extra = sorted(set(by_workload).difference(expected))
    for workload_id in missing:
        errors.append(f"Missing storage posture row: {workload_id}")
    for workload_id in extra:
        errors.append(f"Unexpected storage posture row: {workload_id}")

    for workload_id, expected_row in expected.items():
        row = by_workload.get(workload_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{workload_id}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("storage-posture.csv cannot be empty")

    return StoragePostureValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def storage_posture_row(workload: dict[str, Any], assessment: WorkloadAssessment) -> dict[str, str]:
    storage = workload.get("storage") if isinstance(workload.get("storage"), dict) else {}
    finding_codes = [finding.code for finding in assessment.findings if finding.code in STORAGE_FINDINGS]
    status = storage_status(finding_codes)
    return {
        "schema_version": STORAGE_POSTURE_SCHEMA_VERSION,
        "workload_id": assessment.workload_id,
        "name": assessment.name,
        "owner": assessment.owner,
        "target": assessment.target,
        "readiness": assessment.readiness,
        "disk_count": text_value(storage.get("disk_count")),
        "disk_gib": text_value(workload.get("disk_gib")),
        "thin_provisioned": bool_text(storage.get("thin_provisioned")),
        "raw_device_mapping": bool_text(storage.get("raw_device_mapping")),
        "shared_disk": bool_text(storage.get("shared_disk")),
        "independent_disk": bool_text(storage.get("independent_disk")),
        "encrypted": bool_text(storage.get("encrypted")),
        "datastores": join_list(storage.get("datastores") or storage.get("storage_containers")),
        "min_datastore_free_percent": text_value(storage.get("min_datastore_free_percent")),
        "storage_status": status,
        "blocking_findings": "; ".join(finding_codes),
        "required_action": required_action(status, finding_codes),
        "evidence_refs": f"assessment.json#{assessment.workload_id};nutanix-move-plan.csv#{assessment.workload_id}",
    }


def storage_status(finding_codes: list[str]) -> str:
    if "storage_rdm_mapping_required" in finding_codes:
        return "blocked"
    if any(code in finding_codes for code in ("shared_disk_cluster_review", "independent_disk_review", "datastore_free_space_low")):
        return "remediate"
    if "encrypted_disk_review" in finding_codes:
        return "review"
    return "ready"


def required_action(status: str, finding_codes: list[str]) -> str:
    actions: list[str] = []
    if "storage_rdm_mapping_required" in finding_codes:
        actions.append("Convert or redesign raw device mappings before Move staging.")
    if "shared_disk_cluster_review" in finding_codes:
        actions.append("Validate clustered or multi-writer disk semantics with the application and storage owners.")
    if "independent_disk_review" in finding_codes:
        actions.append("Confirm disk inclusion, backup state, and Move behavior before staging.")
    if "encrypted_disk_review" in finding_codes:
        actions.append("Verify encryption key ownership and target-platform support.")
    if "datastore_free_space_low" in finding_codes:
        actions.append("Increase datastore free space or capture storage-owner approval before migration activity.")
    if actions:
        return " ".join(actions)
    if status == "ready":
        return "Confirm storage posture during pre-change review."
    return "Collect missing storage posture evidence before Move staging."


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


def join_list(value: Any) -> str:
    if isinstance(value, list):
        return "; ".join(str(item) for item in value)
    return str(value or "")


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in STORAGE_POSTURE_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read storage posture CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_storage_posture_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("storage_posture_context") if isinstance(assessment.get("storage_posture_context"), dict) else {}
    rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != STORAGE_POSTURE_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {STORAGE_POSTURE_SCHEMA_VERSION} storage posture context")
    expected: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        workload_id = str(row.get("workload_id") or "")
        expected[workload_id] = {column: str(row.get(column) or "") for column in STORAGE_POSTURE_COLUMNS}
    return expected
