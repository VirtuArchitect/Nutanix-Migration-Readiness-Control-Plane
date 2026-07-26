from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .evidence import MOVE_PLAN_SCHEMA_VERSION


MOVE_PLAN_COLUMNS = [
    "schema_version",
    "include_in_move_plan",
    "wave",
    "source_vm_id",
    "source_vm_name",
    "owner",
    "target",
    "readiness",
    "risk_score",
    "target_networks",
    "dependency_count",
    "application_owner_approval",
    "rollback_owner",
    "precheck_status",
    "required_actions",
]

ALLOWED_READINESS = {"ready", "research", "prepare", "blocked"}
ALLOWED_TARGETS = {"ahv", "nc2"}


@dataclass(frozen=True)
class MovePlanValidation:
    path: Path
    row_count: int
    included_count: int
    hold_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return (
            f"{status}: rows={self.row_count}, included={self.included_count}, "
            f"held={self.hold_count}, errors={len(self.errors)}, warnings={len(self.warnings)}"
        )


def validate_move_plan(path: Path, assessment_path: Path | None = None) -> MovePlanValidation:
    errors: list[str] = []
    warnings: list[str] = []
    included_count = 0
    hold_count = 0

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [column for column in MOVE_PLAN_COLUMNS if column not in fieldnames]
        extra = [column for column in fieldnames if column not in MOVE_PLAN_COLUMNS]
        if missing:
            errors.append(f"Missing required columns: {', '.join(missing)}")
        if extra:
            warnings.append(f"Unexpected columns ignored by nmrcp validator: {', '.join(extra)}")

        rows = list(reader)

    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=2):
        source_vm_id = (row.get("source_vm_id") or "").strip()
        source_vm_name = (row.get("source_vm_name") or "").strip()
        readiness = (row.get("readiness") or "").strip()
        include = (row.get("include_in_move_plan") or "").strip()
        precheck = (row.get("precheck_status") or "").strip()
        schema_version = (row.get("schema_version") or "").strip()
        target = (row.get("target") or "").strip()
        owner_approval = (row.get("application_owner_approval") or "").strip()
        rollback_owner = (row.get("rollback_owner") or "").strip()

        if schema_version != MOVE_PLAN_SCHEMA_VERSION:
            errors.append(f"Row {index}: unsupported schema_version {schema_version!r}")
        if not source_vm_id:
            errors.append(f"Row {index}: source_vm_id is required")
        if source_vm_id in seen_ids:
            errors.append(f"Row {index}: duplicate source_vm_id {source_vm_id!r}")
        seen_ids.add(source_vm_id)
        if not source_vm_name:
            errors.append(f"Row {index}: source_vm_name is required")
        if target not in ALLOWED_TARGETS:
            errors.append(f"Row {index}: target must be one of {', '.join(sorted(ALLOWED_TARGETS))}")
        if readiness not in ALLOWED_READINESS:
            errors.append(f"Row {index}: readiness must be one of {', '.join(sorted(ALLOWED_READINESS))}")
        if include not in {"yes", "no"}:
            errors.append(f"Row {index}: include_in_move_plan must be yes or no")
        if include == "yes":
            included_count += 1
        else:
            hold_count += 1
        if readiness in {"prepare", "blocked"} and include == "yes":
            errors.append(f"Row {index}: {readiness} workload cannot be included in Move staging")
        if include == "yes" and precheck != "ready_for_move_staging":
            errors.append(f"Row {index}: included workload must have ready_for_move_staging precheck")
        if include == "no" and precheck != "hold_until_remediated":
            errors.append(f"Row {index}: held workload must have hold_until_remediated precheck")
        if owner_approval not in {"confirmed", "not confirmed", "not supplied"}:
            errors.append(
                "Row "
                f"{index}: application_owner_approval must be confirmed, not confirmed, or not supplied"
            )
        if include == "yes" and owner_approval != "confirmed":
            warnings.append(f"Row {index}: included workload does not have confirmed application owner approval")
        if include == "yes" and rollback_owner in {"", "not confirmed"}:
            warnings.append(f"Row {index}: included workload does not have confirmed rollback owner")
        try:
            risk_score = int(row.get("risk_score") or "")
        except ValueError:
            errors.append(f"Row {index}: risk_score must be an integer")
        else:
            if risk_score < 0 or risk_score > 100:
                errors.append(f"Row {index}: risk_score must be between 0 and 100")
            if include == "yes" and risk_score >= 25:
                warnings.append(f"Row {index}: included workload has risk score {risk_score}")
        try:
            dependency_count = int(row.get("dependency_count") or "")
        except ValueError:
            errors.append(f"Row {index}: dependency_count must be an integer")
        else:
            if dependency_count < 0:
                errors.append(f"Row {index}: dependency_count cannot be negative")

    if assessment_path is not None:
        validate_against_assessment(rows, assessment_path, errors)

    return MovePlanValidation(
        path=path,
        row_count=len(rows),
        included_count=included_count,
        hold_count=hold_count,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_against_assessment(rows: list[dict[str, str]], assessment_path: Path, errors: list[str]) -> None:
    assessment = read_assessment(assessment_path, errors)
    if not assessment:
        return
    expected = expected_assessment_rows(assessment, errors)
    by_id = {(row.get("source_vm_id") or "").strip(): row for row in rows}

    missing = sorted(set(expected).difference(by_id))
    extra = sorted(set(by_id).difference(expected))
    for workload_id in missing:
        errors.append(f"Move plan missing assessment workload: {workload_id}")
    for workload_id in extra:
        errors.append(f"Move plan contains workload not present in assessment: {workload_id}")

    for workload_id, expected_row in expected.items():
        row = by_id.get(workload_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{workload_id}: {field} expected {expected_value!r}, got {actual!r}")


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_assessment_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    assessments = {
        str(item.get("workload_id") or ""): item
        for item in assessment.get("assessments", [])
        if isinstance(item, dict)
    }
    wave_by_workload: dict[str, str] = {}
    for wave in assessment.get("waves", []):
        if not isinstance(wave, dict):
            continue
        wave_name = str(wave.get("name") or "Unassigned")
        workload_ids = wave.get("workload_ids") if isinstance(wave.get("workload_ids"), list) else []
        for workload_id in workload_ids:
            if not isinstance(workload_id, str):
                continue
            if workload_id not in assessments:
                errors.append(f"assessment.json wave {wave_name!r} references unknown workload_id {workload_id!r}")
            previous_wave = wave_by_workload.get(workload_id)
            if previous_wave:
                errors.append(
                    f"assessment.json workload_id {workload_id!r} appears in multiple waves: "
                    f"{previous_wave!r} and {wave_name!r}"
                )
            wave_by_workload[workload_id] = wave_name

    expected: dict[str, dict[str, str]] = {}
    for workload_id, row in assessments.items():
        readiness = str(row.get("readiness") or "")
        include = "yes" if readiness in {"ready", "research"} else "no"
        findings = row.get("findings") if isinstance(row.get("findings"), list) else []
        required_actions = "; ".join(
            str(finding.get("code") or "")
            for finding in findings
            if isinstance(finding, dict)
        )
        expected[workload_id] = {
            "schema_version": MOVE_PLAN_SCHEMA_VERSION,
            "include_in_move_plan": include,
            "wave": wave_by_workload.get(workload_id, "Unassigned"),
            "source_vm_id": workload_id,
            "source_vm_name": str(row.get("name") or ""),
            "owner": str(row.get("owner") or "Unassigned"),
            "target": str(row.get("target") or ""),
            "readiness": readiness,
            "risk_score": str(int(row.get("risk_score") or 0)),
            "precheck_status": "ready_for_move_staging" if include == "yes" else "hold_until_remediated",
            "required_actions": required_actions,
        }
    return expected
