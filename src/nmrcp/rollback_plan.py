from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Wave, WorkloadAssessment
from .move_staging_readiness import move_staging_readiness_row
from .recovery_readiness import RECOVERY_FINDINGS, recovery_readiness_row, recovery_status, required_action as recovery_required_action


ROLLBACK_PLAN_SCHEMA_VERSION = "nmrcp_rollback_plan_v1"
ROLLBACK_PLAN_COLUMNS = (
    "schema_version",
    "workload_id",
    "name",
    "owner",
    "target",
    "wave",
    "move_plan_decision",
    "stage_status",
    "recovery_status",
    "rollback_owner",
    "backup_protected",
    "backup_last_success_hours",
    "snapshot_count",
    "oldest_snapshot_days",
    "rollback_status",
    "rollback_trigger",
    "required_action",
    "evidence_refs",
)


@dataclass(frozen=True)
class RollbackPlanValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def rollback_plan_context(
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
    rows = [
        rollback_row(workloads.get(assessment.workload_id, {}), assessment, wave_by_workload)
        for assessment in assessments
    ]
    return {
        "schema_version": ROLLBACK_PLAN_SCHEMA_VERSION,
        "workloads": rows,
    }


def write_rollback_plan_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    rows = rollback_plan_context(inventory, assessments, waves)["workloads"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ROLLBACK_PLAN_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_rollback_plan(path: Path, assessment_path: Path) -> RollbackPlanValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return RollbackPlanValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_rollback_rows(assessment, errors)
    keyed_rows = {row.get("workload_id", ""): row for row in rows}
    if len(keyed_rows) != len(rows):
        errors.append("rollback-plan.csv contains duplicate workload rows")

    missing = sorted(set(expected).difference(keyed_rows))
    extra = sorted(set(keyed_rows).difference(expected))
    for key in missing:
        errors.append(f"Missing rollback plan row: {key}")
    for key in extra:
        errors.append(f"Unexpected rollback plan row: {key}")

    for key, expected_row in expected.items():
        row = keyed_rows.get(key)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{key}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("rollback-plan.csv cannot be empty")

    return RollbackPlanValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def rollback_row(
    workload: dict[str, Any],
    assessment: WorkloadAssessment,
    wave_by_workload: dict[str, str],
) -> dict[str, str]:
    recovery = recovery_readiness_row(workload, assessment)
    staging = move_staging_readiness_row(workload, assessment, wave_by_workload)
    status = rollback_status(staging["move_plan_decision"], staging["stage_status"], recovery)
    return {
        "schema_version": ROLLBACK_PLAN_SCHEMA_VERSION,
        "workload_id": assessment.workload_id,
        "name": assessment.name,
        "owner": assessment.owner,
        "target": assessment.target,
        "wave": staging["wave"],
        "move_plan_decision": staging["move_plan_decision"],
        "stage_status": staging["stage_status"],
        "recovery_status": recovery["recovery_status"],
        "rollback_owner": recovery["rollback_owner"],
        "backup_protected": recovery["backup_protected"],
        "backup_last_success_hours": recovery["backup_last_success_hours"],
        "snapshot_count": recovery["snapshot_count"],
        "oldest_snapshot_days": recovery["oldest_snapshot_days"],
        "rollback_status": status,
        "rollback_trigger": rollback_trigger(status),
        "required_action": required_action(status, recovery),
        "evidence_refs": ";".join(
            [
                f"assessment.json#{assessment.workload_id}",
                f"recovery-readiness.csv#{assessment.workload_id}",
                f"move-staging-readiness.csv#{assessment.workload_id}",
                f"pre-post-validation-checklist.md#{assessment.workload_id}",
            ]
        ),
    }


def rollback_status(move_plan_decision: str, stage_status: str, recovery: dict[str, str]) -> str:
    if move_plan_decision == "hold":
        return "hold"
    if recovery["rollback_owner"] in {"", "not confirmed"}:
        return "blocked"
    if recovery["recovery_status"] == "blocked":
        return "blocked"
    if stage_status == "ready" and recovery["recovery_status"] == "ready":
        return "ready"
    return "review"


def rollback_trigger(status: str) -> str:
    if status == "ready":
        return "Rollback if post-cutover application health, identity, connectivity, backup, or monitoring validation fails."
    if status == "hold":
        return "Do not stage; rollback trigger is not active until readiness and approval clear."
    return "Stop before cutover until rollback ownership and recovery evidence are approved."


def required_action(status: str, recovery: dict[str, str]) -> str:
    actions: list[str] = []
    if recovery["rollback_owner"] in {"", "not confirmed"}:
        actions.append("Assign rollback owner.")
    if recovery["recovery_status"] != "ready":
        actions.append(recovery["required_action"])
    if status == "ready":
        return "Confirm rollback owner, recovery evidence, and stop criteria during final change review."
    if status == "hold":
        return "Keep rollback evidence with remediation work; do not stage until workload readiness clears."
    return " ".join(actions) if actions else "Review rollback plan before Move staging."


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in ROLLBACK_PLAN_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read rollback plan CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_rollback_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("rollback_plan_context") if isinstance(assessment.get("rollback_plan_context"), dict) else {}
    rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != ROLLBACK_PLAN_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {ROLLBACK_PLAN_SCHEMA_VERSION} rollback plan context")
    assessments = assessment_rows_by_workload(assessment, errors)
    wave_by_workload = wave_membership_by_workload(assessment, set(assessments), errors)
    expected: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json rollback_plan_context workload row {index} must be an object")
            continue
        normalized = {key: str(row.get(key) or "") for key in ROLLBACK_PLAN_COLUMNS}
        workload_id = normalized["workload_id"]
        if not workload_id:
            errors.append(f"assessment.json rollback_plan_context workload row {index} missing workload_id")
            continue
        if workload_id in expected:
            errors.append(f"assessment.json rollback_plan_context duplicate workload_id {workload_id!r}")
        bind_rollback_row_to_assessment(normalized, assessments, wave_by_workload, errors)
        expected[workload_id] = normalized
    for workload_id in sorted(set(assessments).difference(expected)):
        errors.append(f"assessment.json rollback_plan_context missing workload_id {workload_id!r}")
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


def wave_membership_by_workload(
    assessment: dict[str, Any],
    workload_ids: set[str],
    errors: list[str],
) -> dict[str, str]:
    rows = assessment.get("waves") if isinstance(assessment.get("waves"), list) else []
    if not rows:
        errors.append("assessment.json waves must contain wave rows")
        return {}
    wave_by_workload: dict[str, str] = {}
    for index, wave in enumerate(rows, start=1):
        if not isinstance(wave, dict):
            errors.append(f"assessment.json waves row {index} must be an object")
            continue
        wave_name = str(wave.get("name") or "Unassigned")
        ids = wave.get("workload_ids") if isinstance(wave.get("workload_ids"), list) else []
        for workload_id in ids:
            if not isinstance(workload_id, str):
                continue
            if workload_id not in workload_ids:
                errors.append(f"assessment.json wave {wave_name!r} references unknown workload_id {workload_id!r}")
            previous = wave_by_workload.get(workload_id)
            if previous:
                errors.append(
                    f"assessment.json workload_id {workload_id!r} appears in multiple waves: "
                    f"{previous!r} and {wave_name!r}"
                )
            wave_by_workload[workload_id] = wave_name
    return wave_by_workload


def bind_rollback_row_to_assessment(
    row: dict[str, str],
    assessments: dict[str, dict[str, Any]],
    wave_by_workload: dict[str, str],
    errors: list[str],
) -> None:
    workload_id = row["workload_id"]
    assessment_row = assessments.get(workload_id)
    if not assessment_row:
        errors.append(f"assessment.json rollback_plan_context references unknown workload_id {workload_id!r}")
        return
    readiness = str(assessment_row.get("readiness") or "")
    finding_codes = [
        str(finding.get("code") or "")
        for finding in assessment_row.get("findings", [])
        if isinstance(finding, dict) and str(finding.get("code") or "") in RECOVERY_FINDINGS
    ]
    expected_recovery_status = recovery_status(finding_codes)
    expected_recovery_action = recovery_required_action(expected_recovery_status, finding_codes)
    recovery = {
        "recovery_status": expected_recovery_status,
        "rollback_owner": row.get("rollback_owner", ""),
        "required_action": expected_recovery_action,
    }
    expected_rollback_status = rollback_status(row.get("move_plan_decision", ""), row.get("stage_status", ""), recovery)
    expected_values = {
        "name": str(assessment_row.get("name") or ""),
        "owner": str(assessment_row.get("owner") or ""),
        "target": str(assessment_row.get("target") or ""),
        "wave": wave_by_workload.get(workload_id, "Unassigned"),
        "move_plan_decision": "include" if readiness in {"ready", "research"} else "hold",
        "recovery_status": expected_recovery_status,
        "rollback_status": expected_rollback_status,
        "rollback_trigger": rollback_trigger(expected_rollback_status),
        "required_action": required_action(expected_rollback_status, recovery),
        "evidence_refs": ";".join(
            [
                f"assessment.json#{workload_id}",
                f"recovery-readiness.csv#{workload_id}",
                f"move-staging-readiness.csv#{workload_id}",
                f"pre-post-validation-checklist.md#{workload_id}",
            ]
        ),
    }
    for field, expected_value in expected_values.items():
        actual = row.get(field, "")
        if actual != expected_value:
            errors.append(
                f"assessment.json rollback_plan_context {workload_id!r} "
                f"{field} expected {expected_value!r}, got {actual!r}"
            )
