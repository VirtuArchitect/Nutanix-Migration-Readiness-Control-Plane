from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


RISK_REGISTER_COLUMNS = (
    "finding_code",
    "highest_severity",
    "affected_workloads",
    "ready",
    "research",
    "prepare",
    "blocked",
    "max_risk_score",
    "owners",
    "waves",
    "workloads",
    "move_staging_blocker",
    "recommended_action",
)


@dataclass(frozen=True)
class RiskRegisterValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_risk_register(register_path: Path, assessment_path: Path) -> RiskRegisterValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(register_path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return RiskRegisterValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_risk_rows(assessment, errors)
    by_code = {row.get("finding_code", ""): row for row in rows}
    if len(by_code) != len(rows):
        errors.append("migration-risk-register.csv contains duplicate finding_code rows")

    missing = sorted(set(expected).difference(by_code))
    extra = sorted(set(by_code).difference(expected))
    for code in missing:
        errors.append(f"Missing risk register row: {code}")
    for code in extra:
        errors.append(f"Unexpected risk register row: {code}")

    for code, expected_row in expected.items():
        row = by_code.get(code)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{code}: {field} expected {expected_value!r}, got {actual!r}")

    if expected and not rows:
        errors.append("migration-risk-register.csv cannot be empty when assessment findings exist")
    if not expected and rows:
        errors.append("migration-risk-register.csv must be empty except header when assessment has no findings")

    return RiskRegisterValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in RISK_REGISTER_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read migration risk register: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_risk_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    assessments = [item for item in assessment.get("assessments", []) if isinstance(item, dict)]
    if not assessments:
        errors.append("assessment.json assessments must contain workload assessment rows")
    workload_ids = {str(row.get("workload_id") or "") for row in assessments}
    wave_by_workload = wave_membership_by_workload(assessment, workload_ids, errors)
    grouped: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = {}
    for row in assessments:
        findings = row.get("findings") if isinstance(row.get("findings"), list) else []
        for finding in findings:
            if isinstance(finding, dict):
                grouped.setdefault(str(finding.get("code") or ""), []).append((row, finding))

    expected: dict[str, dict[str, str]] = {}
    for code in grouped:
        grouped_rows = grouped[code]
        assessment_rows = [row for row, _finding in grouped_rows]
        finding_rows = [finding for _row, finding in grouped_rows]
        summary = summarize_rows(assessment_rows)
        highest = highest_severity(finding_rows)
        expected[code] = {
            "finding_code": code,
            "highest_severity": highest,
            "affected_workloads": str(len({str(row.get("workload_id") or "") for row in assessment_rows})),
            "ready": str(summary["ready"]),
            "research": str(summary["research"]),
            "prepare": str(summary["prepare"]),
            "blocked": str(summary["blocked"]),
            "max_risk_score": str(max(int(row.get("risk_score") or 0) for row in assessment_rows)),
            "owners": ";".join(sorted({str(row.get("owner") or "Unassigned") for row in assessment_rows})),
            "waves": ";".join(sorted({wave_by_workload.get(str(row.get("workload_id") or ""), "Unassigned") for row in assessment_rows})),
            "workloads": ";".join(sorted({str(row.get("name") or "") for row in assessment_rows})),
            "move_staging_blocker": "yes" if blocks_move(assessment_rows, highest) else "no",
            "recommended_action": str(finding_rows[0].get("recommended_action") or ""),
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


def highest_severity(findings: list[dict[str, Any]]) -> str:
    severities = [str(finding.get("severity") or "") for finding in findings]
    if not severities:
        return "none"
    return max(severities, key=severity_rank)


def severity_rank(severity: str) -> int:
    return {"critical": 4, "high": 3, "medium": 2, "low": 1}.get(severity.lower(), 0)


def blocks_move(rows: list[dict[str, Any]], highest: str) -> bool:
    return any(row.get("readiness") in {"prepare", "blocked"} for row in rows) or severity_rank(highest) >= 3
