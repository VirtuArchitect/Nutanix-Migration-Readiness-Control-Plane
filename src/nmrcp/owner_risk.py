from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


OWNER_RISK_COLUMNS = (
    "owner",
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
    "medium_findings",
    "blocked_workloads",
    "waves",
    "next_action",
)


@dataclass(frozen=True)
class OwnerRiskValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_owner_risk_summary(summary_path: Path, assessment_path: Path) -> OwnerRiskValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(summary_path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return OwnerRiskValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_owner_rows(assessment, errors)
    by_owner = {row.get("owner", ""): row for row in rows}
    if len(by_owner) != len(rows):
        errors.append("owner-risk-summary.csv contains duplicate owner rows")

    missing = sorted(set(expected).difference(by_owner))
    extra = sorted(set(by_owner).difference(expected))
    for owner in missing:
        errors.append(f"Missing owner risk summary row: {owner}")
    for owner in extra:
        errors.append(f"Unexpected owner risk summary row: {owner}")

    for owner, expected_row in expected.items():
        row = by_owner.get(owner)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{owner}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("owner-risk-summary.csv cannot be empty")

    return OwnerRiskValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in OWNER_RISK_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read owner risk summary: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_owner_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    assessments = [item for item in assessment.get("assessments", []) if isinstance(item, dict)]
    if not assessments:
        errors.append("assessment.json assessments must contain workload assessment rows")
    workload_ids = {str(row.get("workload_id") or "") for row in assessments}
    wave_by_workload = wave_membership_by_workload(assessment, workload_ids, errors)

    by_owner: dict[str, list[dict[str, Any]]] = {}
    for row in assessments:
        by_owner.setdefault(str(row.get("owner") or "Unassigned"), []).append(row)

    expected: dict[str, dict[str, str]] = {}
    for owner in sorted(by_owner):
        owner_assessments = by_owner[owner]
        summary = summarize_rows(owner_assessments)
        findings = [finding for row in owner_assessments for finding in row.get("findings", []) if isinstance(finding, dict)]
        blocked_names = [
            str(row.get("name") or "")
            for row in owner_assessments
            if row.get("readiness") in {"prepare", "blocked"}
        ]
        waves = sorted({wave_by_workload.get(str(row.get("workload_id") or ""), "Unassigned") for row in owner_assessments})
        expected[owner] = {
            "owner": owner,
            "total_workloads": str(summary["total"]),
            "ready": str(summary["ready"]),
            "research": str(summary["research"]),
            "prepare": str(summary["prepare"]),
            "blocked": str(summary["blocked"]),
            "average_risk_score": str(average_risk(owner_assessments)),
            "max_risk_score": str(max((int(row.get("risk_score") or 0) for row in owner_assessments), default=0)),
            "open_findings": str(len(findings)),
            "critical_findings": str(severity_count(findings, "critical")),
            "high_findings": str(severity_count(findings, "high")),
            "medium_findings": str(severity_count(findings, "medium")),
            "blocked_workloads": ";".join(blocked_names),
            "waves": ";".join(waves),
            "next_action": owner_next_action(summary, findings),
        }
    return expected


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


def severity_count(findings: list[dict[str, Any]], severity: str) -> int:
    return sum(1 for finding in findings if finding.get("severity") == severity)


def owner_next_action(summary: dict[str, int], findings: list[dict[str, Any]]) -> str:
    if summary["blocked"]:
        return "Clear blocked workload findings before Move staging."
    if summary["prepare"]:
        return "Close remediation tracker rows and re-run assessment."
    if findings:
        return "Review research findings with application owner."
    return "Confirm owner approval, backup proof, and validation plan."
