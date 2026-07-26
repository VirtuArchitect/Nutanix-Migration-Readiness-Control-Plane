from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


BUSINESS_IMPACT_COLUMNS = (
    "tier",
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
    "affected_owners",
    "held_workloads",
    "waves",
    "executive_summary",
)


@dataclass(frozen=True)
class BusinessImpactValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_business_impact_summary(summary_path: Path, assessment_path: Path) -> BusinessImpactValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(summary_path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return BusinessImpactValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_business_rows(assessment, errors)
    by_tier = {row.get("tier", ""): row for row in rows}
    if len(by_tier) != len(rows):
        errors.append("business-impact-summary.csv contains duplicate tier rows")

    missing = sorted(set(expected).difference(by_tier))
    extra = sorted(set(by_tier).difference(expected))
    for tier in missing:
        errors.append(f"Missing business impact summary row: {tier}")
    for tier in extra:
        errors.append(f"Unexpected business impact summary row: {tier}")

    for tier, expected_row in expected.items():
        row = by_tier.get(tier)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{tier}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("business-impact-summary.csv cannot be empty")

    return BusinessImpactValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in BUSINESS_IMPACT_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read business impact summary: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_business_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("business_context") if isinstance(assessment.get("business_context"), dict) else {}
    context_rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != "nmrcp_business_context_v1":
        errors.append("assessment.json missing nmrcp_business_context_v1 business context")

    assessments = {
        str(item.get("workload_id") or ""): item
        for item in assessment.get("assessments", [])
        if isinstance(item, dict)
    }
    if not assessments:
        errors.append("assessment.json assessments must contain workload assessment rows")
    tiers_by_workload = bind_business_context_to_assessments(context_rows, assessments, errors)
    wave_by_workload = wave_membership_by_workload(assessment, set(assessments), errors)

    by_tier: dict[str, list[dict[str, Any]]] = {}
    for workload_id, row in assessments.items():
        tier = tiers_by_workload.get(workload_id, "unknown")
        by_tier.setdefault(tier, []).append(row)

    expected: dict[str, dict[str, str]] = {}
    for tier in sorted(by_tier, key=tier_sort_key):
        tier_assessments = by_tier[tier]
        summary = summarize_rows(tier_assessments)
        findings = [finding for row in tier_assessments for finding in row.get("findings", []) if isinstance(finding, dict)]
        held = [str(row.get("name") or "") for row in tier_assessments if row.get("readiness") in {"prepare", "blocked"}]
        owners = sorted({str(row.get("owner") or "Unassigned") for row in tier_assessments})
        waves = sorted({wave_by_workload.get(str(row.get("workload_id") or ""), "Unassigned") for row in tier_assessments})
        expected[tier] = {
            "tier": tier,
            "total_workloads": str(summary["total"]),
            "ready": str(summary["ready"]),
            "research": str(summary["research"]),
            "prepare": str(summary["prepare"]),
            "blocked": str(summary["blocked"]),
            "average_risk_score": str(average_risk(tier_assessments)),
            "max_risk_score": str(max((int(row.get("risk_score") or 0) for row in tier_assessments), default=0)),
            "open_findings": str(len(findings)),
            "critical_findings": str(severity_count(findings, "critical")),
            "high_findings": str(severity_count(findings, "high")),
            "move_staging_status": business_status(summary, findings),
            "affected_owners": ";".join(owners),
            "held_workloads": ";".join(held),
            "waves": ";".join(waves),
            "executive_summary": business_summary(tier, summary, held, findings),
        }
    return expected


def bind_business_context_to_assessments(
    context_rows: list[Any],
    assessments: dict[str, Any],
    errors: list[str],
) -> dict[str, str]:
    tiers_by_workload: dict[str, str] = {}
    for index, row in enumerate(context_rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json business_context workload row {index} must be an object")
            continue
        workload_id = str(row.get("workload_id") or "")
        if not workload_id:
            errors.append(f"assessment.json business_context workload row {index} missing workload_id")
            continue
        if workload_id in tiers_by_workload:
            errors.append(f"assessment.json business_context duplicate workload_id {workload_id!r}")
        tiers_by_workload[workload_id] = str(row.get("tier") or "unknown")
        assessment_row = assessments.get(workload_id)
        if not assessment_row:
            errors.append(f"assessment.json business_context references unknown workload_id {workload_id!r}")
            continue
        expected_name = str(assessment_row.get("name") or "")
        expected_owner = str(assessment_row.get("owner") or "Unassigned")
        if str(row.get("name") or "") != expected_name:
            errors.append(
                f"assessment.json business_context {workload_id!r} name expected "
                f"{expected_name!r}, got {str(row.get('name') or '')!r}"
            )
        if str(row.get("owner") or "Unassigned") != expected_owner:
            errors.append(
                f"assessment.json business_context {workload_id!r} owner expected "
                f"{expected_owner!r}, got {str(row.get('owner') or 'Unassigned')!r}"
            )

    for workload_id in sorted(set(assessments).difference(tiers_by_workload)):
        errors.append(f"assessment.json business_context missing workload_id {workload_id!r}")
    return tiers_by_workload


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


def business_status(summary: dict[str, int], findings: list[dict[str, Any]]) -> str:
    if summary["blocked"] or severity_count(findings, "critical"):
        return "blocked"
    if summary["prepare"] or severity_count(findings, "high"):
        return "remediate"
    if summary["research"]:
        return "review"
    return "ready"


def business_summary(tier: str, summary: dict[str, int], held_workloads: list[str], findings: list[dict[str, Any]]) -> str:
    if summary["blocked"]:
        return f"{tier} tier has blocked workloads; clear {', '.join(held_workloads)} before executive migration approval."
    if summary["prepare"]:
        return f"{tier} tier requires remediation before Move staging."
    if severity_count(findings, "high") or severity_count(findings, "critical"):
        return f"{tier} tier has high-severity readiness findings requiring owner acceptance."
    if summary["research"]:
        return f"{tier} tier requires compatibility research before scheduling."
    return f"{tier} tier is ready for owner signoff and controlled staging."


def tier_sort_key(tier: str) -> tuple[int, str]:
    return (
        {
            "critical": 0,
            "tier-0": 1,
            "tier-1": 2,
            "high": 3,
            "medium": 4,
            "noncritical": 5,
            "low": 6,
            "unknown": 99,
        }.get(tier, 50),
        tier,
    )
