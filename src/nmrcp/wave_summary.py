from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


WAVE_SUMMARY_COLUMNS = (
    "wave",
    "description",
    "total_workloads",
    "ready",
    "research",
    "prepare",
    "blocked",
    "average_risk_score",
    "max_risk_score",
    "open_findings",
    "critical_findings",
    "high_findings",
    "move_staging_status",
    "move_staging_candidates",
    "held_workloads",
    "owners",
    "next_gate",
)


@dataclass(frozen=True)
class WaveSummaryValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_wave_readiness_summary(summary_path: Path, assessment_path: Path) -> WaveSummaryValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(summary_path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return WaveSummaryValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_wave_rows(assessment, errors)
    by_wave = {row.get("wave", ""): row for row in rows}
    if len(by_wave) != len(rows):
        errors.append("wave-readiness-summary.csv contains duplicate wave rows")

    missing = sorted(set(expected).difference(by_wave))
    extra = sorted(set(by_wave).difference(expected))
    for wave in missing:
        errors.append(f"Missing wave summary row: {wave}")
    for wave in extra:
        errors.append(f"Unexpected wave summary row: {wave}")

    for wave, expected_row in expected.items():
        row = by_wave.get(wave)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{wave}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("wave-readiness-summary.csv cannot be empty")

    return WaveSummaryValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in WAVE_SUMMARY_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read wave readiness summary: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_wave_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    assessments = {
        str(item.get("workload_id") or ""): item
        for item in assessment.get("assessments", [])
        if isinstance(item, dict)
    }
    waves = assessment.get("waves") if isinstance(assessment.get("waves"), list) else []
    expected: dict[str, dict[str, str]] = {}
    assigned_workloads: dict[str, str] = {}
    for wave in waves:
        if not isinstance(wave, dict):
            continue
        wave_name = str(wave.get("name") or "")
        workload_ids = [workload_id for workload_id in wave.get("workload_ids", []) if isinstance(workload_id, str)]
        for workload_id in workload_ids:
            if workload_id not in assessments:
                errors.append(f"assessment.json wave {wave_name!r} references unknown workload_id {workload_id!r}")
            previous_wave = assigned_workloads.get(workload_id)
            if previous_wave:
                errors.append(
                    f"assessment.json workload_id {workload_id!r} appears in multiple waves: "
                    f"{previous_wave!r} and {wave_name!r}"
                )
            assigned_workloads[workload_id] = wave_name
        wave_assessments = [
            assessments[workload_id]
            for workload_id in workload_ids
            if workload_id in assessments
        ]
        summary = summarize_rows(wave_assessments)
        findings = [finding for row in wave_assessments for finding in row.get("findings", []) if isinstance(finding, dict)]
        held = [str(row.get("name") or "") for row in wave_assessments if row.get("readiness") in {"prepare", "blocked"}]
        candidates = [str(row.get("name") or "") for row in wave_assessments if row.get("readiness") in {"ready", "research"}]
        owners = sorted({str(row.get("owner") or "Unassigned") for row in wave_assessments})
        expected[wave_name] = {
            "wave": wave_name,
            "description": str(wave.get("description") or ""),
            "total_workloads": str(summary["total"]),
            "ready": str(summary["ready"]),
            "research": str(summary["research"]),
            "prepare": str(summary["prepare"]),
            "blocked": str(summary["blocked"]),
            "average_risk_score": format_float(average_risk(wave_assessments)),
            "max_risk_score": str(max((int(row.get("risk_score") or 0) for row in wave_assessments), default=0)),
            "open_findings": str(len(findings)),
            "critical_findings": str(severity_count(findings, "critical")),
            "high_findings": str(severity_count(findings, "high")),
            "move_staging_status": wave_status(summary, findings),
            "move_staging_candidates": ";".join(candidates),
            "held_workloads": ";".join(held),
            "owners": ";".join(owners),
            "next_gate": wave_next_gate(summary, findings),
        }
    return expected


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"ready": 0, "research": 0, "prepare": 0, "blocked": 0, "total": len(rows)}
    for row in rows:
        readiness = str(row.get("readiness") or "")
        if readiness in summary:
            summary[readiness] += 1
    return summary


def average_risk(rows: list[dict[str, Any]]) -> float:
    if not rows:
        return 0.0
    return round(sum(int(row.get("risk_score") or 0) for row in rows) / len(rows), 2)


def format_float(value: float) -> str:
    return str(value)


def severity_count(findings: list[dict[str, Any]], severity: str) -> int:
    return sum(1 for finding in findings if finding.get("severity") == severity)


def severity_rank(severity: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(severity, 0)


def wave_status(summary: dict[str, int], findings: list[dict[str, Any]]) -> str:
    if summary["prepare"] or summary["blocked"]:
        return "hold"
    if severity_count(findings, "critical") or severity_count(findings, "high"):
        return "hold"
    if summary["research"]:
        return "conditional"
    return "ready"


def wave_next_gate(summary: dict[str, int], findings: list[dict[str, Any]]) -> str:
    if summary["blocked"]:
        return "Clear blocked findings and obtain formal risk acceptance before Move staging."
    if summary["prepare"]:
        return "Close remediation tracker rows and re-run assessment before Move staging."
    if severity_count(findings, "critical") or severity_count(findings, "high"):
        return "Resolve high-severity findings before scheduling the wave."
    if summary["research"]:
        return "Confirm compatibility research, owner approval, backup proof, and rollback criteria."
    return "Confirm owner signoff, backup proof, rollback criteria, and pre/post validation ownership."
