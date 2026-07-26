from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Wave, WorkloadAssessment


STAKEHOLDER_COMMS_SCHEMA_VERSION = "nmrcp_stakeholder_communication_plan_v1"
STAKEHOLDER_COMMS_COLUMNS = (
    "schema_version",
    "owner",
    "wave",
    "audience",
    "workload_ids",
    "workload_names",
    "readiness_summary",
    "communication_stage",
    "message_intent",
    "evidence_refs",
    "required_action",
)


@dataclass(frozen=True)
class StakeholderCommsValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def stakeholder_comms_context(assessments: list[WorkloadAssessment], waves: list[Wave]) -> dict[str, Any]:
    return {
        "schema_version": STAKEHOLDER_COMMS_SCHEMA_VERSION,
        "communications": stakeholder_comms_rows(assessments, waves),
    }


def write_stakeholder_comms_csv(
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    rows = stakeholder_comms_rows(assessments, waves)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=STAKEHOLDER_COMMS_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_stakeholder_comms(plan_path: Path, assessment_path: Path) -> StakeholderCommsValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(plan_path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return StakeholderCommsValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_comms_rows(assessment, errors)
    by_key = {row_key(row): row for row in rows}
    if len(by_key) != len(rows):
        errors.append("stakeholder-communication-plan.csv contains duplicate owner/wave/stage rows")

    missing = sorted(set(expected).difference(by_key))
    extra = sorted(set(by_key).difference(expected))
    for key in missing:
        errors.append(f"Missing stakeholder communication row: {key}")
    for key in extra:
        errors.append(f"Unexpected stakeholder communication row: {key}")

    for key, expected_row in expected.items():
        row = by_key.get(key)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{key}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("stakeholder-communication-plan.csv cannot be empty")

    return StakeholderCommsValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def stakeholder_comms_rows(assessments: list[WorkloadAssessment], waves: list[Wave]) -> list[dict[str, str]]:
    by_id = {assessment.workload_id: assessment for assessment in assessments}
    rows: list[dict[str, str]] = []
    for wave in waves:
        grouped: dict[str, list[WorkloadAssessment]] = {}
        for workload_id in wave.workload_ids:
            assessment = by_id.get(workload_id)
            if assessment:
                grouped.setdefault(assessment.owner or "Unassigned", []).append(assessment)
        for owner in sorted(grouped):
            owner_assessments = sorted(grouped[owner], key=lambda item: item.name)
            rows.append(comms_row(owner, wave, owner_assessments))
    return rows


def comms_row(owner: str, wave: Wave, assessments: list[WorkloadAssessment]) -> dict[str, str]:
    summary = summarize(assessments)
    stage = communication_stage(summary)
    return {
        "schema_version": STAKEHOLDER_COMMS_SCHEMA_VERSION,
        "owner": owner,
        "wave": wave.name,
        "audience": audience(owner, summary),
        "workload_ids": ";".join(assessment.workload_id for assessment in assessments),
        "workload_names": ";".join(assessment.name for assessment in assessments),
        "readiness_summary": readiness_summary(summary),
        "communication_stage": stage,
        "message_intent": message_intent(stage),
        "evidence_refs": evidence_refs(stage),
        "required_action": required_action(stage),
    }


def summarize(assessments: list[WorkloadAssessment]) -> dict[str, int]:
    summary = {"ready": 0, "research": 0, "prepare": 0, "blocked": 0, "total": len(assessments)}
    for assessment in assessments:
        if assessment.readiness in summary:
            summary[assessment.readiness] += 1
    return summary


def communication_stage(summary: dict[str, int]) -> str:
    if summary["blocked"]:
        return "blocked_owner_review"
    if summary["prepare"]:
        return "remediation_owner_review"
    if summary["research"]:
        return "compatibility_owner_review"
    return "ready_owner_signoff"


def audience(owner: str, summary: dict[str, int]) -> str:
    roles = ["application_owner", "migration_lead"]
    if summary["blocked"] or summary["prepare"]:
        roles.extend(["risk_acceptance", "remediation_owner"])
    if summary["ready"] or summary["research"]:
        roles.append("change_board")
    return f"{owner}: " + ";".join(dict.fromkeys(roles))


def readiness_summary(summary: dict[str, int]) -> str:
    return (
        f"total={summary['total']};ready={summary['ready']};research={summary['research']};"
        f"prepare={summary['prepare']};blocked={summary['blocked']}"
    )


def message_intent(stage: str) -> str:
    return {
        "blocked_owner_review": "Confirm blockers, remediation owner, risk acceptance path, and exclusion from Move staging.",
        "remediation_owner_review": "Confirm remediation plan, owner actions, and rerun timing before Move staging.",
        "compatibility_owner_review": "Confirm compatibility research owner and target support evidence before scheduling.",
        "ready_owner_signoff": "Confirm owner sign-off, validation owner, and controlled Move staging window.",
    }[stage]


def evidence_refs(stage: str) -> str:
    refs = ["assessment.json", "owner-risk-summary.csv", "owner-signoff-matrix.csv"]
    if stage in {"blocked_owner_review", "remediation_owner_review"}:
        refs.extend(["remediation-tracker.csv", "approval-exceptions.csv", "migration-risk-register.csv"])
    if stage == "compatibility_owner_review":
        refs.append("compatibility-research.csv")
    if stage == "ready_owner_signoff":
        refs.extend(["nutanix-move-plan.csv", "pre-post-validation-checklist.md"])
    return ";".join(refs)


def required_action(stage: str) -> str:
    return {
        "blocked_owner_review": "Do not schedule until blocker owner response and risk path are recorded.",
        "remediation_owner_review": "Collect owner remediation response and rerun assessment after fixes.",
        "compatibility_owner_review": "Attach target-support evidence or owner acceptance before scheduling.",
        "ready_owner_signoff": "Capture owner sign-off and validation contact before Move staging.",
    }[stage]


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in STAKEHOLDER_COMMS_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read stakeholder communication plan: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_comms_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    derived = derived_comms_rows(assessment, errors)
    context = assessment.get("stakeholder_comms_context") if isinstance(assessment.get("stakeholder_comms_context"), dict) else {}
    rows = context.get("communications") if isinstance(context.get("communications"), list) else []
    if context.get("schema_version") != STAKEHOLDER_COMMS_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {STAKEHOLDER_COMMS_SCHEMA_VERSION} stakeholder communication context")
    context_rows: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = {column: str(row.get(column) or "") for column in STAKEHOLDER_COMMS_COLUMNS}
        context_rows[row_key(normalized)] = normalized
    if derived and context_rows != derived:
        errors.append("assessment.json stakeholder_comms_context does not match assessments and waves")
    return derived or context_rows


def derived_comms_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    assessments = parse_workload_assessments(assessment.get("assessments"), errors)
    assessment_workload_ids = {assessment.workload_id for assessment in assessments}
    waves = parse_waves(assessment.get("waves"), assessment_workload_ids, errors)
    if not assessments or not waves:
        return {}
    return {
        row_key(row): {column: str(row.get(column) or "") for column in STAKEHOLDER_COMMS_COLUMNS}
        for row in stakeholder_comms_rows(assessments, waves)
    }


def parse_workload_assessments(value: Any, errors: list[str]) -> list[WorkloadAssessment]:
    if not isinstance(value, list) or not value:
        errors.append("assessment.json assessments must contain workload assessment rows")
        return []
    assessments: list[WorkloadAssessment] = []
    for index, row in enumerate(value, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json assessments row {index} must be an object")
            continue
        workload_id = str(row.get("workload_id") or "")
        if not workload_id:
            errors.append(f"assessment.json assessments row {index} missing workload_id")
            continue
        assessments.append(
            WorkloadAssessment(
                workload_id=workload_id,
                name=str(row.get("name") or ""),
                owner=str(row.get("owner") or ""),
                readiness=str(row.get("readiness") or ""),
                risk_score=parse_int(row.get("risk_score")),
                target=str(row.get("target") or ""),
                findings=(),
            )
        )
    return assessments


def parse_waves(value: Any, workload_ids: set[str], errors: list[str]) -> list[Wave]:
    if not isinstance(value, list) or not value:
        errors.append("assessment.json waves must contain wave rows")
        return []
    waves: list[Wave] = []
    assigned_workloads: dict[str, str] = {}
    for index, row in enumerate(value, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json waves row {index} must be an object")
            continue
        wave_name = str(row.get("name") or "")
        wave_workload_ids = row.get("workload_ids") if isinstance(row.get("workload_ids"), list) else []
        for workload_id in wave_workload_ids:
            if not isinstance(workload_id, str):
                continue
            if workload_id not in workload_ids:
                errors.append(f"assessment.json wave {wave_name!r} references unknown workload_id {workload_id!r}")
            previous_wave = assigned_workloads.get(workload_id)
            if previous_wave:
                errors.append(
                    f"assessment.json workload_id {workload_id!r} appears in multiple waves: "
                    f"{previous_wave!r} and {wave_name!r}"
                )
            assigned_workloads[workload_id] = wave_name
        waves.append(
            Wave(
                name=wave_name,
                description=str(row.get("description") or ""),
                workload_ids=tuple(str(workload_id) for workload_id in wave_workload_ids),
            )
        )
    return waves


def parse_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def row_key(row: dict[str, str]) -> str:
    return f"{row.get('owner', '')}|{row.get('wave', '')}|{row.get('communication_stage', '')}"
