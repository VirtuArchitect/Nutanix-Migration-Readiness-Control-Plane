from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_SECTIONS = (
    "# Change Board Evidence",
    "## Executive Summary",
    "## Source",
    "## Collection Audit Proof",
    "## Migration Waves",
    "## Readiness Findings",
)

REQUIRED_AUDIT_TEXT = (
    "- Mode: `read-only`",
    "- Mutating calls: `0`",
)


@dataclass(frozen=True)
class ChangeBoardEvidenceValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_change_board_evidence(evidence_path: Path, assessment_path: Path) -> ChangeBoardEvidenceValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0

    try:
        text = evidence_path.read_text(encoding="utf-8")
    except OSError as exc:
        return ChangeBoardEvidenceValidation("fail", 1, (f"{evidence_path}: could not read change-board evidence: {exc}",), ())

    try:
        assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return ChangeBoardEvidenceValidation("fail", 1, (f"{assessment_path}: could not read assessment JSON: {exc}",), ())

    for section in REQUIRED_SECTIONS:
        checks += 1
        if section not in text:
            errors.append(f"Change-board evidence missing required section: {section}")

    summary = assessment.get("summary") if isinstance(assessment.get("summary"), dict) else {}
    expected_counts = {
        "Total workloads assessed": int(summary.get("total") or 0),
        "Ready": int(summary.get("ready") or 0),
        "Research required": int(summary.get("research") or 0),
        "Remediation required": int(summary.get("prepare") or 0),
        "Blocked": int(summary.get("blocked") or 0),
    }
    for label, expected in expected_counts.items():
        checks += 1
        expected_line = f"- {label}: {expected}"
        if expected_line not in text:
            errors.append(f"Change-board evidence count mismatch or missing line: {expected_line}")

    for audit_text in REQUIRED_AUDIT_TEXT:
        checks += 1
        if audit_text not in text:
            errors.append(f"Change-board evidence missing collection audit proof: {audit_text}")

    checks += 1
    if "nmrcp_collection_audit_v1" not in text:
        errors.append("Change-board evidence missing collection audit schema proof: nmrcp_collection_audit_v1")

    checks += 1
    if "- Credential storage: `" not in text:
        errors.append("Change-board evidence missing credential storage proof")

    source = assessment.get("source") if isinstance(assessment.get("source"), dict) else {}
    audit = source.get("collection_audit") if isinstance(source.get("collection_audit"), dict) else {}
    for api_path in audit.get("api_paths") or []:
        if not isinstance(api_path, str):
            continue
        checks += 1
        if api_path not in text:
            errors.append(f"Change-board evidence missing read-only API path: {api_path}")

    wave_by_workload = wave_assignments(assessment)
    for wave in assessment.get("waves", []):
        if not isinstance(wave, dict):
            continue
        wave_name = str(wave.get("name") or "")
        wave_description = str(wave.get("description") or "")
        for fragment in (f"### {wave_name}", wave_description):
            checks += 1
            if fragment not in text:
                errors.append(f"Change-board evidence missing wave text: {fragment}")

    assessments = [item for item in assessment.get("assessments", []) if isinstance(item, dict)]
    if not assessments:
        errors.append("assessment.json contains no workload assessments for change-board evidence validation")

    for workload in assessments:
        workload_id = str(workload.get("workload_id") or "")
        name = str(workload.get("name") or "")
        owner = str(workload.get("owner") or "Unassigned")
        target = str(workload.get("target") or "")
        readiness = str(workload.get("readiness") or "")
        risk_score = str(int(workload.get("risk_score") or 0))
        wave = wave_by_workload.get(workload_id, "Unassigned")

        expected_fragments = (
            f"- {workload_id}: {name} ({readiness}, risk {risk_score})",
            f"### {workload_id} - {name}",
            f"- Owner: {owner}",
            f"- Target: {target}",
            f"- Readiness: {readiness}",
            f"- Risk score: {risk_score}",
        )
        for fragment in expected_fragments:
            checks += 1
            if fragment not in text:
                errors.append(f"Change-board evidence missing expected workload text for {workload_id}: {fragment}")

        checks += 1
        if f"### {wave}" not in text:
            errors.append(f"Change-board evidence missing wave assignment for {workload_id}: {wave}")

        findings = workload.get("findings") if isinstance(workload.get("findings"), list) else []
        if findings:
            for finding in findings:
                if not isinstance(finding, dict):
                    continue
                finding_line = f"- [{str(finding.get('severity') or '')}] {str(finding.get('code') or '')}: {str(finding.get('message') or '')}"
                action_line = f"  Action: {str(finding.get('recommended_action') or '')}"
                for fragment in (finding_line, action_line):
                    checks += 1
                    if fragment not in text:
                        errors.append(f"Change-board evidence missing finding proof for {workload_id}: {fragment}")
        else:
            checks += 1
            if "- No readiness findings." not in text:
                errors.append(f"Change-board evidence missing no-findings statement for {workload_id}")

    checks += 1
    if "[REDACTED" not in text:
        errors.append("Change-board evidence must include redacted source content")

    checks += 1
    if "Mutating calls: `0`" not in text:
        errors.append("Change-board evidence must prove zero mutating collection calls")

    return ChangeBoardEvidenceValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def wave_assignments(assessment: dict[str, Any]) -> dict[str, str]:
    return {
        str(workload_id): str(wave.get("name") or "Unassigned")
        for wave in assessment.get("waves", [])
        if isinstance(wave, dict)
        for workload_id in wave.get("workload_ids", [])
        if isinstance(workload_id, str)
    }
