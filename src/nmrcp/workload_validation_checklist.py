from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Wave, WorkloadAssessment
from .move_staging_readiness import move_staging_readiness_row


WORKLOAD_VALIDATION_SCHEMA_VERSION = "nmrcp_workload_validation_checklist_v1"
WORKLOAD_VALIDATION_COLUMNS = (
    "schema_version",
    "workload_id",
    "name",
    "owner",
    "target",
    "wave",
    "move_plan_decision",
    "stage_status",
    "validation_phase",
    "check_name",
    "required_evidence",
    "stop_condition",
    "status",
    "evidence_refs",
)


@dataclass(frozen=True)
class WorkloadValidationChecklistValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def workload_validation_context(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
) -> dict[str, Any]:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    rows: list[dict[str, str]] = []
    for assessment in assessments:
        workload = workloads.get(assessment.workload_id, {})
        staging = move_staging_readiness_row(workload, assessment, wave_by_workload)
        rows.extend(workload_validation_rows(assessment, staging))
    return {
        "schema_version": WORKLOAD_VALIDATION_SCHEMA_VERSION,
        "checks": rows,
    }


def write_workload_validation_checklist_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    rows = workload_validation_context(inventory, assessments, waves)["checks"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=WORKLOAD_VALIDATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_workload_validation_checklist(path: Path, assessment_path: Path) -> WorkloadValidationChecklistValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return WorkloadValidationChecklistValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_workload_validation_rows(assessment, errors)
    keyed_rows = {row_key(row): row for row in rows}
    if len(keyed_rows) != len(rows):
        errors.append("workload-validation-checklist.csv contains duplicate validation rows")

    missing = sorted(set(expected).difference(keyed_rows))
    extra = sorted(set(keyed_rows).difference(expected))
    for key in missing:
        errors.append(f"Missing workload validation row: {key}")
    for key in extra:
        errors.append(f"Unexpected workload validation row: {key}")

    for key, expected_row in expected.items():
        row = keyed_rows.get(key)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{key}: {field} expected {expected_value!r}, got {actual!r}")

    if expected and not rows:
        errors.append("workload-validation-checklist.csv cannot be empty when assessment workloads exist")

    return WorkloadValidationChecklistValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def workload_validation_rows(assessment: WorkloadAssessment, staging: dict[str, str]) -> list[dict[str, str]]:
    base = {
        "schema_version": WORKLOAD_VALIDATION_SCHEMA_VERSION,
        "workload_id": assessment.workload_id,
        "name": assessment.name,
        "owner": assessment.owner,
        "target": assessment.target,
        "wave": staging["wave"],
        "move_plan_decision": staging["move_plan_decision"],
        "stage_status": staging["stage_status"],
    }
    rows = [
        checklist_row(
            base,
            "pre_migration",
            "owner_and_rollback_approval",
            "Confirmed application owner approval and rollback owner.",
            "Stop if application approval or rollback owner is not confirmed.",
        ),
        checklist_row(
            base,
            "pre_migration",
            "backup_snapshot_and_dependency_review",
            "Recent backup proof, snapshot cleanup decision, and dependency review.",
            "Stop if recovery or dependency evidence blocks staging.",
        ),
        checklist_row(
            base,
            "pre_migration",
            "tools_storage_network_precheck",
            "Tools/driver readiness, storage posture, and source-to-target network mapping.",
            "Stop if tools, storage, or network mapping is unresolved.",
        ),
        checklist_row(
            base,
            "cutover",
            "move_execution_guard",
            "Move plan row, selected wave, source VM state, final sync status, and operator run ID.",
            "Stop if workload is not cleared for Move staging.",
        ),
        checklist_row(
            base,
            "post_migration",
            "target_health_and_application_validation",
            "Target VM power, IP, DNS, time sync, tools/drivers, monitoring, backup policy, and application-owner health check.",
            "Roll back or hold closure if application health, backup, or monitoring validation fails.",
        ),
    ]
    return rows


def checklist_row(
    base: dict[str, str],
    phase: str,
    check_name: str,
    evidence: str,
    stop_condition: str,
) -> dict[str, str]:
    status = "ready" if base["stage_status"] == "ready" else "blocked"
    return {
        **base,
        "validation_phase": phase,
        "check_name": check_name,
        "required_evidence": evidence,
        "stop_condition": stop_condition,
        "status": status,
        "evidence_refs": ";".join(
            [
                f"assessment.json#{base['workload_id']}",
                f"move-staging-readiness.csv#{base['workload_id']}",
                f"pre-post-validation-checklist.md#{base['workload_id']}",
            ]
        ),
    }


def row_key(row: dict[str, str]) -> str:
    return "|".join([row.get("workload_id", ""), row.get("validation_phase", ""), row.get("check_name", "")])


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in WORKLOAD_VALIDATION_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read workload validation checklist CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_workload_validation_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("workload_validation_context") if isinstance(assessment.get("workload_validation_context"), dict) else {}
    rows = context.get("checks") if isinstance(context.get("checks"), list) else []
    if context.get("schema_version") != WORKLOAD_VALIDATION_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {WORKLOAD_VALIDATION_SCHEMA_VERSION} workload validation context")
    expected: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = {column: str(row.get(column) or "") for column in WORKLOAD_VALIDATION_COLUMNS}
        expected[row_key(normalized)] = normalized
    return expected
