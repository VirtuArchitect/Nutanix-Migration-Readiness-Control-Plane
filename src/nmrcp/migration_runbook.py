from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_SECTIONS = (
    "# Migration Runbook",
    "## Purpose",
    "## Universal Stop Conditions",
    "## Wave Execution Plan",
    "## Evidence Handoff",
)

REQUIRED_STOP_CONDITIONS = (
    "- Stop if a workload marked `prepare` or `blocked` appears in a Move execution list.",
    "- Stop if backup proof, rollback owner, or application owner approval is missing.",
    "- Stop if NSX, firewall, DNS, IPAM, load-balancer, or dependency mapping is unresolved.",
    "- Stop if the operator cannot verify the generated evidence bundle checksum.",
)

REQUIRED_HANDOFF_REFS = (
    "`assessment.json`",
    "`migration-waves.csv`",
    "`wave-readiness-summary.csv`",
    "`dependency-sequence.csv`",
    "`remediation-tracker.csv`",
    "`migration-risk-register.csv`",
    "`owner-risk-summary.csv`",
    "`business-impact-summary.csv`",
    "`owner-signoff-matrix.csv`",
    "`nutanix-move-plan.csv`",
    "`executive-readiness-brief.md`",
    "`change-board-evidence.md`",
    "`migration-runbook.md`",
    "`operator-report.html`",
    "`operator-dashboard.html`",
    "`pre-post-validation-checklist.md`",
    "`move-lab-closure-checklist.md`",
    "`evidence-manifest.json`",
)


@dataclass(frozen=True)
class MigrationRunbookValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_migration_runbook(runbook_path: Path, assessment_path: Path) -> MigrationRunbookValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0

    try:
        text = runbook_path.read_text(encoding="utf-8")
    except OSError as exc:
        return MigrationRunbookValidation("fail", 1, (f"{runbook_path}: could not read migration runbook: {exc}",), ())

    try:
        assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return MigrationRunbookValidation("fail", 1, (f"{assessment_path}: could not read assessment JSON: {exc}",), ())

    for section in REQUIRED_SECTIONS:
        checks += 1
        if section not in text:
            errors.append(f"Migration runbook missing required section: {section}")

    for stop_condition in REQUIRED_STOP_CONDITIONS:
        checks += 1
        if stop_condition not in text:
            errors.append(f"Migration runbook missing universal stop condition: {stop_condition}")

    for evidence_ref in REQUIRED_HANDOFF_REFS:
        checks += 1
        if evidence_ref not in text:
            errors.append(f"Migration runbook missing evidence handoff reference: {evidence_ref}")

    wave_by_workload = wave_assignments(assessment)
    position_by_workload = wave_positions(assessment)
    assessments = [item for item in assessment.get("assessments", []) if isinstance(item, dict)]
    if not assessments:
        errors.append("assessment.json contains no workload assessments for runbook validation")

    for workload in assessments:
        workload_id = str(workload.get("workload_id") or "")
        name = str(workload.get("name") or "")
        owner = str(workload.get("owner") or "Unassigned")
        target = str(workload.get("target") or "")
        readiness = str(workload.get("readiness") or "")
        risk_score = str(int(workload.get("risk_score") or 0))
        wave = wave_by_workload.get(workload_id, "Unassigned")
        position = position_by_workload.get(workload_id, 1)

        expected_fragments = (
            f"### {wave}",
            f"#### {position}. {name}",
            f"- Source VM ID: `{workload_id}`",
            f"- Owner: {owner}",
            f"- Target: {target}",
            f"- Readiness: `{readiness}`",
            f"- Risk score: {risk_score}",
            f"- Move staging: {expected_staging_intent(readiness)}",
            "- Confirm this workload is in the approved wave.",
        )
        for fragment in expected_fragments:
            checks += 1
            if fragment not in text:
                errors.append(f"Migration runbook missing expected workload text for {workload_id}: {fragment}")

        if readiness in {"ready", "research"}:
            checks += 1
            if "- Confirm final sync/precheck status in Nutanix Move before cutover." not in text:
                errors.append(f"Migration runbook missing Nutanix Move precheck instruction for included workload {workload_id}")
        else:
            checks += 1
            if "- Do not stage this workload in Nutanix Move until all required actions are cleared." not in text:
                errors.append(f"Migration runbook missing hold instruction for held workload {workload_id}")
            checks += 1
            if "- Re-run assessment after remediation and verify the workload leaves hold state." not in text:
                errors.append(f"Migration runbook missing reassessment instruction for held workload {workload_id}")

        findings = workload.get("findings") if isinstance(workload.get("findings"), list) else []
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            checks += 1
            expected_action = (
                f"- [{str(finding.get('severity') or '')}] {str(finding.get('code') or '')}: "
                f"{str(finding.get('recommended_action') or '')}"
            )
            if expected_action not in text:
                errors.append(f"Migration runbook missing finding action for {workload_id}: {expected_action}")

    checks += 1
    if "Nutanix Move" not in text:
        errors.append("Migration runbook must include Nutanix Move operator instructions")

    checks += 1
    if "Record pre-cutover and post-cutover evidence in the change workspace." not in text:
        errors.append("Migration runbook must require pre-cutover and post-cutover evidence recording")

    return MigrationRunbookValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def wave_assignments(assessment: dict[str, Any]) -> dict[str, str]:
    return {
        str(workload_id): str(wave.get("name") or "Unassigned")
        for wave in assessment.get("waves", [])
        if isinstance(wave, dict)
        for workload_id in wave.get("workload_ids", [])
        if isinstance(workload_id, str)
    }


def wave_positions(assessment: dict[str, Any]) -> dict[str, int]:
    positions: dict[str, int] = {}
    for wave in assessment.get("waves", []):
        if not isinstance(wave, dict):
            continue
        workload_ids = [workload_id for workload_id in wave.get("workload_ids", []) if isinstance(workload_id, str)]
        for position, workload_id in enumerate(workload_ids, start=1):
            positions[workload_id] = position
    return positions


def expected_staging_intent(readiness: str) -> str:
    if readiness in {"ready", "research"}:
        return "include after review"
    return "hold until remediated"
