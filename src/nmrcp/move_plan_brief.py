from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MOVE_PLAN_BRIEF_SCHEMA_VERSION = "nmrcp_move_plan_brief_v1"
MOVE_PLAN_SCHEMA_VERSION = "nmrcp_move_plan_v1"
REQUIRED_SECTIONS = (
    "# Nutanix Move Plan Brief",
    "## Decision Summary",
    "## Include For Move Staging",
    "## Hold Until Remediated",
    "## Governance Warnings",
    "## Evidence To Inspect",
    "## Stop Conditions",
)
REQUIRED_FRAGMENTS = (
    MOVE_PLAN_BRIEF_SCHEMA_VERSION,
    MOVE_PLAN_SCHEMA_VERSION,
    "`nutanix-move-plan.csv`",
    "`move-staging-readiness.csv`",
    "`workload-validation-checklist.csv`",
    "Do not submit this plan to Nutanix Move",
)
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
SECRET_ASSIGNMENT_RE = re.compile(r"(?i)\b(password|token|secret|api[_-]?key)\s*[:=]\s*\S+")


@dataclass(frozen=True)
class MovePlanBriefValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def write_move_plan_brief(plan_path: Path, assessment_path: Path, out_path: Path) -> MovePlanBriefValidation:
    rows = read_move_plan_rows(plan_path)
    assessment = read_assessment(assessment_path)
    text = render_move_plan_brief(rows, assessment)
    out_path.write_text(text, encoding="utf-8")
    return validate_move_plan_brief(out_path, plan_path, assessment_path)


def validate_move_plan_brief(brief_path: Path, plan_path: Path, assessment_path: Path) -> MovePlanBriefValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    try:
        actual = brief_path.read_text(encoding="utf-8")
    except OSError as exc:
        return MovePlanBriefValidation("fail", 1, (f"{brief_path}: could not read Move plan brief: {exc}",), ())
    try:
        rows = read_move_plan_rows(plan_path)
        assessment = read_assessment(assessment_path)
    except (OSError, json.JSONDecodeError) as exc:
        return MovePlanBriefValidation("fail", 1, (f"Could not read Move plan brief inputs: {exc}",), ())

    findings = scan_sensitive_text(actual)
    checks += 1
    errors.extend(f"Move plan brief leak: {finding}" for finding in findings)

    for section in REQUIRED_SECTIONS:
        checks += 1
        if section not in actual:
            errors.append(f"Move plan brief missing required section: {section}")
    for fragment in REQUIRED_FRAGMENTS:
        checks += 1
        if fragment not in actual:
            errors.append(f"Move plan brief missing required text: {fragment}")

    input_errors, input_warnings, input_checks = validate_inputs(rows, assessment)
    checks += input_checks
    errors.extend(input_errors)
    warnings.extend(input_warnings)

    expected = render_move_plan_brief(rows, assessment)
    checks += 1
    if normalize_markdown(actual) != normalize_markdown(expected):
        errors.append("Move plan brief does not match nutanix-move-plan.csv and assessment.json")

    checks += 1
    if "vcenter01.corp.local" in actual or "migration.owner@example.com" in actual:
        errors.append("Move plan brief leaked sample endpoint or operator identity")

    return MovePlanBriefValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def render_move_plan_brief(rows: list[dict[str, str]], assessment: dict[str, Any]) -> str:
    summary = summarize_rows(rows)
    include_rows = [row for row in sorted(rows, key=sort_key) if row.get("include_in_move_plan") == "yes"]
    hold_rows = [row for row in sorted(rows, key=sort_key) if row.get("include_in_move_plan") != "yes"]
    lines = [
        "# Nutanix Move Plan Brief",
        "",
        f"Schema: `{MOVE_PLAN_BRIEF_SCHEMA_VERSION}`",
        f"Move plan schema: `{MOVE_PLAN_SCHEMA_VERSION}`",
        "",
        "## Decision Summary",
        "",
        f"- Decision signal: {decision_signal(summary)}",
        f"- Workloads represented: {summary['total']}",
        f"- Include for Move staging review: {summary['include']}",
        f"- Hold until remediated: {summary['hold']}",
        f"- Ready prechecks: {summary['ready_precheck']}",
        f"- Held prechecks: {summary['held_precheck']}",
        f"- Blocked readiness rows: {summary['blocked']}",
        "",
        "## Include For Move Staging",
        "",
        *row_lines(include_rows, include=True),
        "",
        "## Hold Until Remediated",
        "",
        *row_lines(hold_rows, include=False),
        "",
        "## Governance Warnings",
        "",
        *governance_warning_lines(include_rows),
        "",
        "## Evidence To Inspect",
        "",
        "- `nutanix-move-plan.csv`: machine-readable Move staging plan contract.",
        "- `move-staging-readiness.csv`: include, hold, and blocker rationale.",
        "- `move-staging-brief.md`: reviewer summary of staging decisions.",
        "- `what-will-break-report.csv`: workload-level breakage scenarios.",
        "- `workload-validation-checklist.csv`: pre-migration and post-migration validation evidence.",
        "- `owner-signoff-matrix.csv`: required application, migration, rollback, and risk approvals.",
        "",
        "## Stop Conditions",
        "",
        "- Do not submit this plan to Nutanix Move until `validate-move-plan --assessment` passes.",
        "- Do not submit this plan to Nutanix Move for rows with `include_in_move_plan=no` or `precheck_status=hold_until_remediated`.",
        "- Do not submit this plan to Nutanix Move until owner sign-off, rollback ownership, backup proof, and pre/post validation ownership are confirmed.",
        "- Do not treat this brief as appliance proof; approved Nutanix Move lab evidence is still required before production handoff.",
        "",
    ]
    if assessment.get("summary"):
        summary_block = assessment.get("summary") if isinstance(assessment.get("summary"), dict) else {}
        lines.extend(
            [
                "## Assessment Cross-Check",
                "",
                f"- Assessment workloads: {summary_block.get('total', 'missing')}",
                f"- Assessment ready: {summary_block.get('ready', 'missing')}",
                f"- Assessment prepare: {summary_block.get('prepare', 'missing')}",
                f"- Assessment blocked: {summary_block.get('blocked', 'missing')}",
                "",
            ]
        )
    return "\n".join(lines)


def validate_inputs(rows: list[dict[str, str]], assessment: dict[str, Any]) -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    checks += 1
    if not rows:
        errors.append("Move plan brief requires at least one Move plan row")
    expected_by_id = expected_assessment_rows(assessment, errors)
    rows_by_id = {row.get("source_vm_id", ""): row for row in rows}
    checks += 1
    if set(rows_by_id) != set(expected_by_id):
        missing = sorted(set(expected_by_id) - set(rows_by_id))
        extra = sorted(set(rows_by_id) - set(expected_by_id))
        if missing:
            errors.append(f"Move plan brief missing assessment workloads: {', '.join(missing)}")
        if extra:
            errors.append(f"Move plan brief has workloads outside assessment: {', '.join(extra)}")
    for workload_id, row in rows_by_id.items():
        checks += 1
        if row.get("schema_version") != MOVE_PLAN_SCHEMA_VERSION:
            errors.append(f"{workload_id}: schema_version must be {MOVE_PLAN_SCHEMA_VERSION}")
        if row.get("include_in_move_plan") == "yes" and row.get("precheck_status") != "ready_for_move_staging":
            errors.append(f"{workload_id}: included row must have ready_for_move_staging precheck")
        if row.get("include_in_move_plan") != "yes" and row.get("precheck_status") != "hold_until_remediated":
            errors.append(f"{workload_id}: held row must have hold_until_remediated precheck")
        if row.get("include_in_move_plan") == "yes" and row.get("application_owner_approval") != "confirmed":
            warnings.append(f"{workload_id}: included row lacks confirmed application owner approval")
        expected = expected_by_id.get(workload_id)
        if not expected:
            continue
        for field, expected_value in expected.items():
            checks += 1
            if (row.get(field) or "").strip() != expected_value:
                errors.append(f"{workload_id}: {field} expected {expected_value!r}, got {(row.get(field) or '').strip()!r}")
    return errors, warnings, checks


def expected_assessment_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    assessments = {
        str(item.get("workload_id") or ""): item
        for item in assessment.get("assessments", [])
        if isinstance(item, dict)
    }
    wave_by_workload: dict[str, str] = {}
    for wave in assessment.get("waves", []):
        if not isinstance(wave, dict):
            continue
        wave_name = str(wave.get("name") or "Unassigned")
        for workload_id in wave.get("workload_ids") or []:
            if isinstance(workload_id, str):
                wave_by_workload[workload_id] = wave_name
    expected: dict[str, dict[str, str]] = {}
    for workload_id, row in assessments.items():
        readiness = str(row.get("readiness") or "")
        include = "yes" if readiness in {"ready", "research"} else "no"
        expected[workload_id] = {
            "include_in_move_plan": include,
            "wave": wave_by_workload.get(workload_id, "Unassigned"),
            "source_vm_name": str(row.get("name") or ""),
            "owner": str(row.get("owner") or "Unassigned"),
            "target": str(row.get("target") or ""),
            "readiness": readiness,
            "risk_score": str(int(row.get("risk_score") or 0)),
            "precheck_status": "ready_for_move_staging" if include == "yes" else "hold_until_remediated",
        }
    if not expected:
        errors.append("assessment.json does not contain assessment rows")
    return expected


def row_lines(rows: list[dict[str, str]], *, include: bool) -> list[str]:
    if not rows:
        return ["- No workloads in this category."]
    lines: list[str] = []
    for row in rows:
        prefix = "Include" if include else "Hold"
        lines.append(
            f"- {prefix} `{row.get('source_vm_name')}` (`{row.get('source_vm_id')}`): "
            f"owner `{row.get('owner')}`, wave `{row.get('wave')}`, readiness `{row.get('readiness')}`, "
            f"risk `{row.get('risk_score')}`, precheck `{row.get('precheck_status')}`, "
            f"actions `{row.get('required_actions') or 'none'}`."
        )
    return lines


def governance_warning_lines(rows: list[dict[str, str]]) -> list[str]:
    warnings: list[str] = []
    for row in rows:
        if row.get("application_owner_approval") != "confirmed":
            warnings.append(f"- `{row.get('source_vm_id')}`: application owner approval is `{row.get('application_owner_approval')}`.")
        if row.get("rollback_owner") in {"", "not confirmed"}:
            warnings.append(f"- `{row.get('source_vm_id')}`: rollback owner is not confirmed.")
    return warnings or ["- No governance warnings for included rows."]


def summarize_rows(rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        "total": len(rows),
        "include": sum(1 for row in rows if row.get("include_in_move_plan") == "yes"),
        "hold": sum(1 for row in rows if row.get("include_in_move_plan") != "yes"),
        "ready_precheck": sum(1 for row in rows if row.get("precheck_status") == "ready_for_move_staging"),
        "held_precheck": sum(1 for row in rows if row.get("precheck_status") == "hold_until_remediated"),
        "blocked": sum(1 for row in rows if row.get("readiness") == "blocked"),
    }


def decision_signal(summary: dict[str, int]) -> str:
    if summary["blocked"] or summary["hold"]:
        return "Review included rows only; hold blocked or remediation-required workloads out of Nutanix Move."
    if summary["include"]:
        return "All represented workloads are eligible for controlled Move staging review after validation."
    return "No workloads are eligible for Nutanix Move staging."


def sort_key(row: dict[str, str]) -> tuple[int, str, str]:
    try:
        risk = int(row.get("risk_score") or 0)
    except ValueError:
        risk = 0
    return (-risk, row.get("wave") or "", row.get("source_vm_name") or "")


def read_move_plan_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def read_assessment(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: assessment JSON root must be an object")
    return payload


def normalize_markdown(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def scan_sensitive_text(text: str) -> list[str]:
    findings: list[str] = []
    if "://" in text:
        findings.append("URLs are not allowed in Move plan brief")
    if EMAIL_RE.search(text):
        findings.append("email addresses are not allowed in Move plan brief")
    if IPV4_RE.search(text):
        findings.append("IP addresses are not allowed in Move plan brief")
    if SECRET_ASSIGNMENT_RE.search(text):
        findings.append("secret-like assignments are not allowed in Move plan brief")
    return findings
