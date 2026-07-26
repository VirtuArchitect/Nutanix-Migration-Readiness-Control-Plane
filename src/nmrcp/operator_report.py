from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_TEXT = (
    "<!doctype html>",
    "<title>NMRCP Operator Report</title>",
    "Nutanix Migration Readiness Operator Report",
    "Executive Summary",
    "Migration Waves",
    "Collection Audit Proof",
    "Workload Readiness",
    "Redacted Source",
    "Local, redacted readiness evidence",
)

REQUIRED_AUDIT_TEXT = (
    "nmrcp_collection_audit_v1",
    "Mode",
    "read-only",
    "Credential storage",
    "Mutating calls",
    "0",
)


@dataclass(frozen=True)
class OperatorReportValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_operator_report(report_path: Path, assessment_path: Path) -> OperatorReportValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0

    try:
        raw_text = report_path.read_text(encoding="utf-8")
    except OSError as exc:
        return OperatorReportValidation("fail", 1, (f"{report_path}: could not read operator report: {exc}",), ())

    try:
        assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return OperatorReportValidation("fail", 1, (f"{assessment_path}: could not read assessment JSON: {exc}",), ())

    text = html.unescape(raw_text)

    for required in REQUIRED_TEXT:
        checks += 1
        if required not in text:
            errors.append(f"Operator report missing required text: {required}")

    summary = assessment.get("summary") if isinstance(assessment.get("summary"), dict) else {}
    expected_metrics = (
        ("Total", int(summary.get("total") or 0)),
        ("Ready", int(summary.get("ready") or 0)),
        ("Research", int(summary.get("research") or 0)),
        ("Prepare", int(summary.get("prepare") or 0)),
        ("Blocked", int(summary.get("blocked") or 0)),
        ("Unmatched Dependencies", source_int(assessment, "dependency_unmatched_records")),
    )
    for label, expected_count in expected_metrics:
        checks += 1
        if expected_metric_fragment(label, expected_count) not in text:
            errors.append(f"Operator report missing summary metric card: {label}={expected_count}")

    for audit_text in REQUIRED_AUDIT_TEXT:
        checks += 1
        if audit_text not in text:
            errors.append(f"Operator report missing collection audit proof: {audit_text}")

    source = assessment.get("source") if isinstance(assessment.get("source"), dict) else {}
    audit = source.get("collection_audit") if isinstance(source.get("collection_audit"), dict) else {}
    for api_path in audit.get("api_paths") or []:
        if not isinstance(api_path, str):
            continue
        checks += 1
        if api_path not in text:
            errors.append(f"Operator report missing read-only API path: {api_path}")

    wave_by_workload = wave_assignments(assessment)
    for wave in assessment.get("waves", []):
        if not isinstance(wave, dict):
            continue
        wave_name = str(wave.get("name") or "")
        wave_description = str(wave.get("description") or "")
        for fragment in (wave_name, wave_description):
            checks += 1
            if fragment not in text:
                errors.append(f"Operator report missing wave text: {fragment}")

    assessments = [item for item in assessment.get("assessments", []) if isinstance(item, dict)]
    if not assessments:
        errors.append("assessment.json contains no workload assessments for operator report validation")

    for workload in assessments:
        workload_id = str(workload.get("workload_id") or "")
        name = str(workload.get("name") or "")
        owner = str(workload.get("owner") or "Unassigned")
        target = str(workload.get("target") or "")
        readiness = str(workload.get("readiness") or "")
        risk_score = str(int(workload.get("risk_score") or 0))
        wave = wave_by_workload.get(workload_id, "Unassigned")

        for fragment in (workload_id, name, owner, wave, "Readiness", readiness, "Target", target, risk_score):
            checks += 1
            if fragment not in text:
                errors.append(f"Operator report missing expected workload text for {workload_id}: {fragment}")

        findings = workload.get("findings") if isinstance(workload.get("findings"), list) else []
        if findings:
            for finding in findings:
                if not isinstance(finding, dict):
                    continue
                for fragment in (
                    str(finding.get("severity") or ""),
                    str(finding.get("code") or ""),
                    str(finding.get("message") or ""),
                    str(finding.get("recommended_action") or ""),
                ):
                    checks += 1
                    if fragment and fragment not in text:
                        errors.append(f"Operator report missing finding text for {workload_id}: {fragment}")
        else:
            checks += 1
            if "No readiness findings." not in text:
                errors.append(f"Operator report missing no-findings statement for {workload_id}")

    checks += 1
    if "[REDACTED" not in text:
        errors.append("Operator report must include redacted source metadata")

    checks += 1
    if "vcenter01.corp.local" in text:
        errors.append("Operator report leaked sample vCenter hostname")

    checks += 1
    if "migration.owner@example.com" in text:
        errors.append("Operator report leaked sample operator email")

    return OperatorReportValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def wave_assignments(assessment: dict[str, Any]) -> dict[str, str]:
    return {
        str(workload_id): str(wave.get("name") or "Unassigned")
        for wave in assessment.get("waves", [])
        if isinstance(wave, dict)
        for workload_id in wave.get("workload_ids", [])
        if isinstance(workload_id, str)
    }


def expected_metric_fragment(label: str, value: int) -> str:
    return f'<div class="metric"><strong>{value}</strong><span>{label}</span></div>'


def source_int(assessment: dict[str, Any], key: str) -> int:
    source = assessment.get("source")
    if not isinstance(source, dict):
        return 0
    return int(source.get(key) or 0)
