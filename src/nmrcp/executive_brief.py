from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_SECTIONS = (
    "# Executive Readiness Brief",
    "## Decision Ask",
    "## Migration Posture",
    "## Business Impact",
    "## Wave Decisions",
    "## Top Blockers",
    "## Required Evidence Before Approval",
    "## Generated Evidence",
)
REQUIRED_EVIDENCE_REFS = (
    "`business-impact-summary.csv`",
    "`wave-readiness-summary.csv`",
    "`compatibility-research.csv`",
    "`dependency-review.csv`",
    "`connectivity-checklist.csv`",
    "`identity-cutover-plan.csv`",
    "`tools-driver-readiness.csv`",
    "`storage-posture.csv`",
    "`recovery-readiness.csv`",
    "`rollback-plan.csv`",
    "`move-staging-readiness.csv`",
    "`migration-execution-queue.csv`",
    "`migration-risk-register.csv`",
    "`owner-risk-summary.csv`",
    "`approval-exceptions.csv`",
    "`nutanix-move-plan.csv`",
    "`workload-validation-checklist.csv`",
)


@dataclass(frozen=True)
class ExecutiveBriefValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_executive_brief(brief_path: Path, assessment_path: Path) -> ExecutiveBriefValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0

    try:
        text = brief_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ExecutiveBriefValidation("fail", 1, (f"{brief_path}: could not read executive brief: {exc}",), ())

    try:
        assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ExecutiveBriefValidation("fail", 1, (f"{assessment_path}: could not read assessment JSON: {exc}",), ())

    for section in REQUIRED_SECTIONS:
        checks += 1
        if section not in text:
            errors.append(f"Executive brief missing required section: {section}")

    summary = assessment.get("summary") if isinstance(assessment.get("summary"), dict) else {}
    expected_counts = {
        "Workloads assessed": int(summary.get("total") or 0),
        "Move staging candidates": int(summary.get("ready") or 0) + int(summary.get("research") or 0),
        "Held workloads": int(summary.get("prepare") or 0) + int(summary.get("blocked") or 0),
        "Blocked workloads": int(summary.get("blocked") or 0),
        "Remediation required": int(summary.get("prepare") or 0),
        "Ready": int(summary.get("ready") or 0),
        "Research required": int(summary.get("research") or 0),
        "Prepare/remediate": int(summary.get("prepare") or 0),
        "Blocked": int(summary.get("blocked") or 0),
    }
    for label, expected in expected_counts.items():
        checks += 1
        expected_line = f"- {label}: {expected}"
        if expected_line not in text:
            errors.append(f"Executive brief count mismatch or missing line: {expected_line}")

    checks += 1
    expected_decision = expected_decision_fragment(summary)
    if expected_decision not in text:
        errors.append(f"Executive brief decision does not match assessment state: expected text containing {expected_decision!r}")

    for line in expected_wave_decision_lines(assessment):
        checks += 1
        if line not in text:
            errors.append(f"Executive brief missing wave decision line: {line}")

    checks += 1
    if "Approved Nutanix Move lab appliance proof is supplied" not in text:
        errors.append("Executive brief must state approved Nutanix Move lab appliance proof is required before final production handoff")

    for evidence_ref in REQUIRED_EVIDENCE_REFS:
        checks += 1
        if evidence_ref not in text:
            errors.append(f"Executive brief missing generated evidence reference: {evidence_ref}")

    checks += 1
    if "Move staging candidates: 0" in text:
        warnings.append("Executive brief reports no Move staging candidates")

    return ExecutiveBriefValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def expected_decision_fragment(summary: dict[str, Any]) -> str:
    if int(summary.get("blocked") or 0):
        return "Do not approve broad Move staging"
    if int(summary.get("prepare") or 0):
        return "Approve only ready pilot workloads"
    if int(summary.get("research") or 0):
        return "Approve conditional planning"
    return "Approve controlled Move staging"


def expected_wave_decision_lines(assessment: dict[str, Any]) -> tuple[str, ...]:
    assessments_by_id = {
        str(item.get("workload_id") or ""): item
        for item in assessment.get("assessments", [])
        if isinstance(item, dict)
    }
    lines: list[str] = []
    for wave in assessment.get("waves", []):
        if not isinstance(wave, dict):
            continue
        wave_name = str(wave.get("name") or "")
        wave_workloads = [
            assessments_by_id[str(workload_id)]
            for workload_id in wave.get("workload_ids", [])
            if isinstance(workload_id, str) and str(workload_id) in assessments_by_id
        ]
        summary = summarize_workload_rows(wave_workloads)
        findings = [
            finding
            for workload in wave_workloads
            for finding in (workload.get("findings") if isinstance(workload.get("findings"), list) else [])
            if isinstance(finding, dict)
        ]
        held = [
            str(workload.get("name") or "")
            for workload in wave_workloads
            if str(workload.get("readiness") or "") in {"prepare", "blocked"}
        ]
        lines.append(
            f"- {wave_name}: {summary['total']} workloads, staging `{wave_move_staging_status(summary, findings)}`, "
            f"held `{'; '.join(held) or 'none'}`."
        )
    return tuple(lines or ["- No migration waves were generated."])


def summarize_workload_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"ready": 0, "research": 0, "prepare": 0, "blocked": 0, "total": len(rows)}
    for row in rows:
        readiness = str(row.get("readiness") or "")
        if readiness in summary:
            summary[readiness] += 1
    return summary


def wave_move_staging_status(summary: dict[str, int], findings: list[dict[str, Any]]) -> str:
    if summary["blocked"] or summary["prepare"]:
        return "hold"
    if any(str(finding.get("severity") or "").lower() in {"critical", "high"} for finding in findings):
        return "hold"
    if summary["research"]:
        return "conditional"
    return "ready"
