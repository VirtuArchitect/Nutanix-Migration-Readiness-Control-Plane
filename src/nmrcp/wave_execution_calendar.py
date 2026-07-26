from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Finding, Wave, WorkloadAssessment


WAVE_EXECUTION_CALENDAR_SCHEMA_VERSION = "nmrcp_wave_execution_calendar_v1"
WAVE_EXECUTION_CALENDAR_COLUMNS = (
    "schema_version",
    "execution_sequence",
    "wave",
    "window_type",
    "move_staging_status",
    "total_workloads",
    "candidate_workloads",
    "held_workloads",
    "owners",
    "entry_gate",
    "exit_gate",
    "operator_actions",
    "evidence_refs",
)


@dataclass(frozen=True)
class WaveExecutionCalendarValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def wave_execution_calendar_context(assessments: list[WorkloadAssessment], waves: list[Wave]) -> dict[str, Any]:
    return {
        "schema_version": WAVE_EXECUTION_CALENDAR_SCHEMA_VERSION,
        "waves": wave_execution_calendar_rows(assessments, waves),
    }


def write_wave_execution_calendar_csv(assessments: list[WorkloadAssessment], waves: list[Wave], path: Path) -> None:
    rows = wave_execution_calendar_rows(assessments, waves)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=WAVE_EXECUTION_CALENDAR_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_wave_execution_calendar(calendar_path: Path, assessment_path: Path) -> WaveExecutionCalendarValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(calendar_path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return WaveExecutionCalendarValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_calendar_rows(assessment, errors)
    by_wave = {row.get("wave", ""): row for row in rows}
    if len(by_wave) != len(rows):
        errors.append("wave-execution-calendar.csv contains duplicate wave rows")

    missing = sorted(set(expected).difference(by_wave))
    extra = sorted(set(by_wave).difference(expected))
    for wave in missing:
        errors.append(f"Missing wave execution calendar row: {wave}")
    for wave in extra:
        errors.append(f"Unexpected wave execution calendar row: {wave}")

    for wave, expected_row in expected.items():
        row = by_wave.get(wave)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{wave}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("wave-execution-calendar.csv cannot be empty")

    return WaveExecutionCalendarValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def wave_execution_calendar_rows(assessments: list[WorkloadAssessment], waves: list[Wave]) -> list[dict[str, str]]:
    by_id = {assessment.workload_id: assessment for assessment in assessments}
    rows: list[dict[str, str]] = []
    for index, wave in enumerate(waves, start=1):
        wave_assessments = [by_id[workload_id] for workload_id in wave.workload_ids if workload_id in by_id]
        rows.append(calendar_row(index, wave, wave_assessments))
    return rows


def calendar_row(index: int, wave: Wave, assessments: list[WorkloadAssessment]) -> dict[str, str]:
    summary = summarize(assessments)
    findings = [finding for assessment in assessments for finding in assessment.findings]
    status = staging_status(summary, findings)
    candidates = [assessment.name for assessment in assessments if assessment.readiness in {"ready", "research"}]
    held = [assessment.name for assessment in assessments if assessment.readiness in {"prepare", "blocked"}]
    owners = sorted({assessment.owner or "Unassigned" for assessment in assessments})
    return {
        "schema_version": WAVE_EXECUTION_CALENDAR_SCHEMA_VERSION,
        "execution_sequence": str(index),
        "wave": wave.name,
        "window_type": window_type(wave.name, status),
        "move_staging_status": status,
        "total_workloads": str(len(assessments)),
        "candidate_workloads": ";".join(candidates),
        "held_workloads": ";".join(held),
        "owners": ";".join(owners),
        "entry_gate": entry_gate(status, summary),
        "exit_gate": exit_gate(status, summary),
        "operator_actions": operator_actions(status, summary),
        "evidence_refs": evidence_refs(status),
    }


def summarize(assessments: list[WorkloadAssessment]) -> dict[str, int]:
    summary = {"ready": 0, "research": 0, "prepare": 0, "blocked": 0}
    for assessment in assessments:
        if assessment.readiness in summary:
            summary[assessment.readiness] += 1
    return summary


def staging_status(summary: dict[str, int], findings: list[Any]) -> str:
    if summary["blocked"] or summary["prepare"]:
        return "hold"
    if any(getattr(finding, "severity", "") in {"critical", "high"} for finding in findings):
        return "hold"
    if summary["research"]:
        return "conditional"
    return "ready"


def window_type(wave_name: str, status: str) -> str:
    if status == "ready":
        return "pilot_or_standard_move_window"
    if status == "conditional":
        return "compatibility_review_window"
    if "Excluded" in wave_name:
        return "blocked_no_move_window"
    return "remediation_review_window"


def entry_gate(status: str, summary: dict[str, int]) -> str:
    if status == "ready":
        return "owner_signoff_backup_rollback_and_validation_owner_confirmed"
    if status == "conditional":
        return "compatibility_research_owner_signoff_backup_and_rollback_confirmed"
    if summary["blocked"]:
        return "blocked_findings_cleared_or_risk_acceptance_recorded"
    return "remediation_tracker_closed_and_assessment_rerun"


def exit_gate(status: str, summary: dict[str, int]) -> str:
    if status == "ready":
        return "pre_migration_validation_complete_and_move_payload_reviewed"
    if status == "conditional":
        return "research_evidence_attached_and_wave_reclassified"
    if summary["blocked"]:
        return "workloads_removed_from_exclusion_or_formally_accepted"
    return "remediated_workloads_reassessed_to_ready_or_research"


def operator_actions(status: str, summary: dict[str, int]) -> str:
    if status == "ready":
        return "Schedule controlled lab/staging review; attach validation checklist; confirm rollback owner."
    if status == "conditional":
        return "Hold scheduling until compatibility evidence and owner approval are attached."
    if summary["blocked"]:
        return "Do not schedule; collect blocker owner response, risk path, and remediation evidence."
    return "Do not schedule; close remediation tracker rows and rerun assessment."


def evidence_refs(status: str) -> str:
    refs = [
        "wave-readiness-summary.csv",
        "migration-execution-queue.csv",
        "stakeholder-communication-plan.csv",
        "what-will-break-report.csv",
    ]
    if status == "ready":
        refs.extend(["owner-signoff-matrix.csv", "pre-post-validation-checklist.md", "nutanix-move-plan.csv"])
    elif status == "conditional":
        refs.extend(["compatibility-research.csv", "owner-signoff-matrix.csv", "approval-exceptions.csv"])
    else:
        refs.extend(["remediation-tracker.csv", "approval-exceptions.csv", "migration-risk-register.csv"])
    return ";".join(refs)


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in WAVE_EXECUTION_CALENDAR_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read wave execution calendar: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_calendar_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    derived = derived_calendar_rows(assessment, errors)
    context = assessment.get("wave_execution_calendar_context") if isinstance(assessment.get("wave_execution_calendar_context"), dict) else {}
    if context.get("schema_version") != WAVE_EXECUTION_CALENDAR_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {WAVE_EXECUTION_CALENDAR_SCHEMA_VERSION} wave execution calendar context")
    context_rows = context.get("waves") if isinstance(context.get("waves"), list) else []
    context_by_wave: dict[str, dict[str, str]] = {}
    for row in context_rows:
        if not isinstance(row, dict):
            continue
        normalized = {column: str(row.get(column) or "") for column in WAVE_EXECUTION_CALENDAR_COLUMNS}
        context_by_wave[normalized["wave"]] = normalized
    if derived and context_by_wave != derived:
        errors.append("assessment.json wave_execution_calendar_context does not match assessments and waves")
    return derived or context_by_wave


def derived_calendar_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    assessments = parse_workload_assessments(assessment.get("assessments"), errors)
    assessment_workload_ids = {assessment.workload_id for assessment in assessments}
    waves = parse_waves(assessment.get("waves"), assessment_workload_ids, errors)
    if not assessments or not waves:
        return {}
    return {
        row["wave"]: {column: str(row.get(column) or "") for column in WAVE_EXECUTION_CALENDAR_COLUMNS}
        for row in wave_execution_calendar_rows(assessments, waves)
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
        findings: list[Finding] = []
        raw_findings = row.get("findings") if isinstance(row.get("findings"), list) else []
        for finding in raw_findings:
            if not isinstance(finding, dict):
                continue
            findings.append(
                Finding(
                    code=str(finding.get("code") or ""),
                    severity=str(finding.get("severity") or ""),
                    message=str(finding.get("message") or ""),
                    recommended_action=str(finding.get("recommended_action") or ""),
                )
            )
        assessments.append(
            WorkloadAssessment(
                workload_id=str(row.get("workload_id") or ""),
                name=str(row.get("name") or ""),
                owner=str(row.get("owner") or ""),
                readiness=str(row.get("readiness") or ""),
                risk_score=parse_int(row.get("risk_score")),
                target=str(row.get("target") or ""),
                findings=tuple(findings),
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
