from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .compatibility_research import compatibility_row
from .connectivity_checklist import connectivity_checklist_context
from .identity_cutover_plan import identity_row
from .models import Wave, WorkloadAssessment
from .move_staging_readiness import move_staging_readiness_row
from .rollback_plan import rollback_row
from .workload_validation_checklist import workload_validation_rows


MIGRATION_EXECUTION_QUEUE_SCHEMA_VERSION = "nmrcp_migration_execution_queue_v1"
MIGRATION_EXECUTION_QUEUE_COLUMNS = (
    "schema_version",
    "execution_order",
    "workload_id",
    "name",
    "owner",
    "target",
    "wave",
    "move_plan_decision",
    "stage_status",
    "readiness",
    "risk_score",
    "compatibility_status",
    "identity_status",
    "connectivity_status",
    "rollback_status",
    "validation_status",
    "execution_status",
    "blocking_findings",
    "required_action",
    "evidence_refs",
)


@dataclass(frozen=True)
class MigrationExecutionQueueValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def migration_execution_queue_context(
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
    wave_order = {
        workload_id: wave_index
        for wave_index, wave in enumerate(waves, start=1)
        for workload_id in wave.workload_ids
    }
    connectivity_by_workload = summarize_connectivity(inventory, assessments)
    ordered = sorted(
        assessments,
        key=lambda assessment: (
            wave_order.get(assessment.workload_id, 999),
            stage_sort(move_staging_readiness_row(workloads.get(assessment.workload_id, {}), assessment, wave_by_workload)["stage_status"]),
            assessment.risk_score,
            assessment.name,
        ),
    )
    return {
        "schema_version": MIGRATION_EXECUTION_QUEUE_SCHEMA_VERSION,
        "workloads": [
            migration_execution_row(
                workloads.get(assessment.workload_id, {}),
                assessment,
                wave_by_workload,
                connectivity_by_workload,
                index,
            )
            for index, assessment in enumerate(ordered, start=1)
        ],
    }


def write_migration_execution_queue_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    rows = migration_execution_queue_context(inventory, assessments, waves)["workloads"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MIGRATION_EXECUTION_QUEUE_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_migration_execution_queue(path: Path, assessment_path: Path) -> MigrationExecutionQueueValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return MigrationExecutionQueueValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_migration_execution_rows(assessment, errors)
    keyed_rows = {row.get("workload_id", ""): row for row in rows}
    if len(keyed_rows) != len(rows):
        errors.append("migration-execution-queue.csv contains duplicate workload rows")

    missing = sorted(set(expected).difference(keyed_rows))
    extra = sorted(set(keyed_rows).difference(expected))
    for workload_id in missing:
        errors.append(f"Missing migration execution queue row: {workload_id}")
    for workload_id in extra:
        errors.append(f"Unexpected migration execution queue row: {workload_id}")

    for workload_id, expected_row in expected.items():
        row = keyed_rows.get(workload_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{workload_id}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("migration-execution-queue.csv cannot be empty")

    return MigrationExecutionQueueValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def migration_execution_row(
    workload: dict[str, Any],
    assessment: WorkloadAssessment,
    wave_by_workload: dict[str, str],
    connectivity_by_workload: dict[str, str],
    execution_order: int,
) -> dict[str, str]:
    staging = move_staging_readiness_row(workload, assessment, wave_by_workload)
    compatibility = compatibility_row(workload, assessment)
    identity = identity_row(assessment, workload, staging["wave"])
    rollback = rollback_row(workload, assessment, wave_by_workload)
    validation = validation_status(workload_validation_rows(assessment, staging))
    connectivity = connectivity_by_workload.get(assessment.workload_id, "none_declared")
    blockers = execution_blockers(staging, compatibility, identity, connectivity, rollback, validation)
    status = execution_status(staging, compatibility, identity, connectivity, rollback, validation, blockers)
    return {
        "schema_version": MIGRATION_EXECUTION_QUEUE_SCHEMA_VERSION,
        "execution_order": str(execution_order),
        "workload_id": assessment.workload_id,
        "name": assessment.name,
        "owner": assessment.owner,
        "target": assessment.target,
        "wave": staging["wave"],
        "move_plan_decision": staging["move_plan_decision"],
        "stage_status": staging["stage_status"],
        "readiness": assessment.readiness,
        "risk_score": str(assessment.risk_score),
        "compatibility_status": compatibility["compatibility_status"],
        "identity_status": identity["identity_status"],
        "connectivity_status": connectivity,
        "rollback_status": rollback["rollback_status"],
        "validation_status": validation,
        "execution_status": status,
        "blocking_findings": "; ".join(blockers),
        "required_action": required_action(status, blockers),
        "evidence_refs": ";".join(
            [
                f"assessment.json#{assessment.workload_id}",
                f"migration-waves.csv#{assessment.workload_id}",
                f"nutanix-move-plan.csv#{assessment.workload_id}",
                f"move-staging-readiness.csv#{assessment.workload_id}",
                f"workload-validation-checklist.csv#{assessment.workload_id}",
                f"rollback-plan.csv#{assessment.workload_id}",
                f"compatibility-research.csv#{assessment.workload_id}",
                f"identity-cutover-plan.csv#{assessment.workload_id}",
                f"connectivity-checklist.csv#{assessment.workload_id}",
            ]
        ),
    }


def summarize_connectivity(inventory: dict[str, Any], assessments: list[WorkloadAssessment]) -> dict[str, str]:
    rows = connectivity_checklist_context(inventory, assessments)["connections"]
    statuses: dict[str, list[str]] = {}
    for row in rows:
        statuses.setdefault(str(row.get("source_workload_id") or ""), []).append(str(row.get("connectivity_status") or ""))
    return {workload_id: aggregate_connectivity(values) for workload_id, values in statuses.items()}


def aggregate_connectivity(statuses: list[str]) -> str:
    if not statuses:
        return "none_declared"
    if "blocked" in statuses:
        return "blocked"
    if "needs_discovery" in statuses:
        return "needs_discovery"
    if "needs_validation_plan" in statuses:
        return "needs_validation_plan"
    if all(status == "ready" for status in statuses):
        return "ready"
    return "review"


def validation_status(rows: list[dict[str, str]]) -> str:
    statuses = {row.get("status", "") for row in rows}
    if "blocked" in statuses:
        return "blocked"
    if statuses == {"ready"}:
        return "ready"
    return "review"


def execution_blockers(
    staging: dict[str, str],
    compatibility: dict[str, str],
    identity: dict[str, str],
    connectivity: str,
    rollback: dict[str, str],
    validation: str,
) -> list[str]:
    blockers: list[str] = []
    if staging["move_plan_decision"] == "hold":
        blockers.append("move_plan_hold")
    if staging["stage_status"] != "ready":
        blockers.append(f"stage_{staging['stage_status']}")
    if compatibility["compatibility_status"] != "ready":
        blockers.append(f"compatibility_{compatibility['compatibility_status']}")
    if identity["identity_status"] != "ready":
        blockers.append(f"identity_{identity['identity_status']}")
    if connectivity not in {"ready", "none_declared"}:
        blockers.append(f"connectivity_{connectivity}")
    if rollback["rollback_status"] != "ready":
        blockers.append(f"rollback_{rollback['rollback_status']}")
    if validation != "ready":
        blockers.append(f"validation_{validation}")
    return blockers


def execution_status(
    staging: dict[str, str],
    compatibility: dict[str, str],
    identity: dict[str, str],
    connectivity: str,
    rollback: dict[str, str],
    validation: str,
    blockers: list[str],
) -> str:
    hard_blockers = {
        "move_plan_hold",
        "stage_hold",
        "compatibility_blocked",
        "identity_blocked",
        "connectivity_blocked",
        "rollback_blocked",
        "validation_blocked",
    }
    if hard_blockers.intersection(blockers):
        return "hold"
    if (
        staging["stage_status"] == "conditional"
        or compatibility["compatibility_status"] == "research"
        or identity["identity_status"] == "review"
        or connectivity in {"needs_discovery", "needs_validation_plan", "review"}
        or rollback["rollback_status"] == "review"
        or validation == "review"
    ):
        return "review"
    return "ready"


def required_action(status: str, blockers: list[str]) -> str:
    if status == "ready":
        return "Ready for Move staging precheck, lab-only payload review, and final operator validation."
    actions: list[str] = []
    if "move_plan_hold" in blockers or any(blocker.startswith("stage_") for blocker in blockers):
        actions.append("Clear staging blockers before assigning this workload to an execution window.")
    if any(blocker.startswith("compatibility_") for blocker in blockers):
        actions.append("Close guest OS and vendor target-support review.")
    if any(blocker.startswith("identity_") for blocker in blockers):
        actions.append("Close hostname, DNS, IPAM, and source-network identity evidence.")
    if any(blocker.startswith("connectivity_") for blocker in blockers):
        actions.append("Close dependency connectivity discovery and validation planning.")
    if any(blocker.startswith("rollback_") for blocker in blockers):
        actions.append("Close rollback owner and recovery evidence.")
    if any(blocker.startswith("validation_") for blocker in blockers):
        actions.append("Close workload pre/post validation checklist blockers.")
    if actions:
        return " ".join(actions)
    return "Review remaining conditional evidence before execution approval."


def stage_sort(status: str) -> int:
    return {"ready": 0, "conditional": 1, "hold": 2}.get(status, 9)


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in MIGRATION_EXECUTION_QUEUE_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read migration execution queue CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_migration_execution_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("migration_execution_queue_context") if isinstance(assessment.get("migration_execution_queue_context"), dict) else {}
    rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != MIGRATION_EXECUTION_QUEUE_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {MIGRATION_EXECUTION_QUEUE_SCHEMA_VERSION} migration execution queue context")
    assessments = assessment_rows_by_workload(assessment, errors)
    wave_by_workload = wave_membership_by_workload(assessment, set(assessments), errors)
    expected: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json migration_execution_queue_context workload row {index} must be an object")
            continue
        normalized = {column: str(row.get(column) or "") for column in MIGRATION_EXECUTION_QUEUE_COLUMNS}
        workload_id = normalized["workload_id"]
        if not workload_id:
            errors.append(f"assessment.json migration_execution_queue_context workload row {index} missing workload_id")
            continue
        if workload_id in expected:
            errors.append(f"assessment.json migration_execution_queue_context duplicate workload_id {workload_id!r}")
        bind_queue_row_to_assessment(normalized, assessments, wave_by_workload, errors)
        expected[workload_id] = normalized
    for workload_id in sorted(set(assessments).difference(expected)):
        errors.append(f"assessment.json migration_execution_queue_context missing workload_id {workload_id!r}")
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


def bind_queue_row_to_assessment(
    row: dict[str, str],
    assessments: dict[str, dict[str, Any]],
    wave_by_workload: dict[str, str],
    errors: list[str],
) -> None:
    workload_id = row["workload_id"]
    assessment_row = assessments.get(workload_id)
    if not assessment_row:
        errors.append(f"assessment.json migration_execution_queue_context references unknown workload_id {workload_id!r}")
        return
    expected_values = {
        "name": str(assessment_row.get("name") or ""),
        "owner": str(assessment_row.get("owner") or ""),
        "target": str(assessment_row.get("target") or ""),
        "readiness": str(assessment_row.get("readiness") or ""),
        "risk_score": str(assessment_row.get("risk_score")) if assessment_row.get("risk_score") is not None else "",
        "wave": wave_by_workload.get(workload_id, "Unassigned"),
    }
    for field, expected_value in expected_values.items():
        actual = row.get(field, "")
        if actual != expected_value:
            errors.append(
                f"assessment.json migration_execution_queue_context {workload_id!r} "
                f"{field} expected {expected_value!r}, got {actual!r}"
            )
