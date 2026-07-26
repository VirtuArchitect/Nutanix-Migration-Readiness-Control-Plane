from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .inventory_coverage import (
    CRITICAL_INCLUDED_FIELDS,
    INVENTORY_COVERAGE_COLUMNS,
    INVENTORY_COVERAGE_CONTEXT_SCHEMA_VERSION,
)
from .models import Finding, Wave, WorkloadAssessment


WHAT_WILL_BREAK_SCHEMA_VERSION = "nmrcp_what_will_break_report_v1"
WHAT_WILL_BREAK_BRIEF_SCHEMA_VERSION = "nmrcp_what_will_break_brief_v1"
WHAT_WILL_BREAK_COLUMNS = (
    "schema_version",
    "workload_id",
    "name",
    "owner",
    "target",
    "wave",
    "readiness",
    "risk_score",
    "finding_code",
    "severity",
    "inventory_coverage_percent",
    "inventory_coverage_gaps",
    "coverage_risk",
    "move_staging_decision",
    "breakage_scenario",
    "impact",
    "operator_signal",
    "required_action",
    "evidence_refs",
)


@dataclass(frozen=True)
class WhatWillBreakValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


@dataclass(frozen=True)
class WhatWillBreakBriefValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def what_will_break_context(
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    coverage_rows: list[dict[str, str | int]] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": WHAT_WILL_BREAK_SCHEMA_VERSION,
        "rows": what_will_break_rows(assessments, waves, coverage_rows=coverage_rows),
    }


def write_what_will_break_csv(
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
    coverage_rows: list[dict[str, str | int]] | None = None,
) -> None:
    rows = what_will_break_rows(assessments, waves, coverage_rows=coverage_rows)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=WHAT_WILL_BREAK_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def write_what_will_break_brief(
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
    coverage_rows: list[dict[str, str | int]] | None = None,
) -> None:
    rows = what_will_break_rows(assessments, waves, coverage_rows=coverage_rows)
    path.write_text(render_what_will_break_brief(rows), encoding="utf-8")


def validate_what_will_break(report_path: Path, assessment_path: Path) -> WhatWillBreakValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(report_path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return WhatWillBreakValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_breakage_rows(assessment, errors)
    by_key = {row_key(row): row for row in rows}
    if len(by_key) != len(rows):
        errors.append("what-will-break-report.csv contains duplicate workload/finding rows")

    missing = sorted(set(expected).difference(by_key))
    extra = sorted(set(by_key).difference(expected))
    for key in missing:
        errors.append(f"Missing what-will-break row: {key}")
    for key in extra:
        errors.append(f"Unexpected what-will-break row: {key}")

    for key, expected_row in expected.items():
        row = by_key.get(key)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{key}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("what-will-break-report.csv cannot be empty")

    return WhatWillBreakValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def validate_what_will_break_brief(brief_path: Path, assessment_path: Path) -> WhatWillBreakBriefValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    try:
        actual = brief_path.read_text(encoding="utf-8")
    except OSError as exc:
        return WhatWillBreakBriefValidation("fail", 1, (f"{brief_path}: could not read what-will-break brief: {exc}",), ())
    assessment = read_assessment(assessment_path, errors)
    checks += 1
    if errors:
        return WhatWillBreakBriefValidation("fail", checks, tuple(errors), tuple(warnings))
    expected_rows = expected_breakage_rows(assessment, errors)
    checks += 1
    if errors:
        return WhatWillBreakBriefValidation("fail", checks, tuple(errors), tuple(warnings))
    expected = render_what_will_break_brief(list(expected_rows.values()))

    for required in (
        "# What Will Break Brief",
        WHAT_WILL_BREAK_BRIEF_SCHEMA_VERSION,
        "## Executive Signal",
        "## Breakage Summary",
        "## Top Breakage Scenarios",
        "## Owner And Wave Holds",
        "Do not stage workloads with `operator_signal=do_not_schedule` in Nutanix Move.",
        "`what-will-break-report.csv`",
        "`remediation-tracker.csv`",
    ):
        checks += 1
        if required not in actual:
            errors.append(f"What-will-break brief missing required text: {required}")

    checks += 1
    if normalize_markdown(actual) != normalize_markdown(expected):
        errors.append("What-will-break brief does not match assessment.json what-will-break context")
    checks += 1
    if "vcenter01.corp.local" in actual:
        errors.append("What-will-break brief leaked sample vCenter hostname")
    checks += 1
    if "migration.owner@example.com" in actual:
        errors.append("What-will-break brief leaked sample operator email")

    return WhatWillBreakBriefValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def what_will_break_rows(
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    coverage_rows: list[dict[str, str | int]] | None = None,
) -> list[dict[str, str]]:
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    coverage_by_workload = {
        str(row.get("workload_id") or ""): row
        for row in coverage_rows or []
        if isinstance(row, dict)
    }
    rows: list[dict[str, str]] = []
    for assessment in assessments:
        coverage_row = coverage_by_workload.get(assessment.workload_id)
        findings = assessment.findings or (
            Finding(
                code="no_open_readiness_breakage",
                severity="none",
                message="No open readiness breakage was detected from the supplied evidence.",
                recommended_action="Confirm owner sign-off and run pre-migration validation before staging.",
            ),
        )
        for finding in findings:
            rows.append(breakage_row(assessment, finding, wave_by_workload, coverage_row))
    return rows


def render_what_will_break_brief(rows: list[dict[str, str]]) -> str:
    sorted_rows = sorted(rows, key=brief_row_sort_key)
    summary = brief_summary(rows)
    top_breakages = [row for row in sorted_rows if row.get("finding_code") != "no_open_readiness_breakage"][:8]
    clean_rows = [row for row in sorted_rows if row.get("finding_code") == "no_open_readiness_breakage"]
    lines = [
        "# What Will Break Brief",
        "",
        f"Schema: `{WHAT_WILL_BREAK_BRIEF_SCHEMA_VERSION}`",
        "",
        "## Executive Signal",
        "",
        f"- Decision signal: {executive_signal(summary)}",
        f"- Workloads represented: {summary['workloads']}",
        f"- Breakage rows: {summary['rows']}",
        f"- Do-not-schedule signals: {summary['do_not_schedule']}",
        f"- Critical coverage gaps: {summary['critical_coverage_gap']}",
        f"- Move holds: {summary['hold']}",
        f"- Conditional reviews: {summary['conditional_review']}",
        f"- Include-after-validation rows: {summary['include_after_validation']}",
        "",
        "## Breakage Summary",
        "",
        *breakage_summary_lines(rows),
        "",
        "## Top Breakage Scenarios",
        "",
        *top_breakage_lines(top_breakages),
        "",
        "## Owner And Wave Holds",
        "",
        *owner_wave_hold_lines(rows),
        "",
        "## Clean Signals",
        "",
        *clean_signal_lines(clean_rows),
        "",
        "## Evidence To Inspect",
        "",
        "- `what-will-break-report.csv`: source row for every scenario in this brief.",
        "- `remediation-tracker.csv`: closure path for each open finding.",
        "- `move-staging-readiness.csv`: include or hold decision before Nutanix Move staging.",
        "- `owner-risk-summary.csv`: owner-level concentration of held workloads.",
        "- `workload-validation-checklist.csv`: pre/post validation evidence for workloads with no open findings.",
        "",
        "## Stop Conditions",
        "",
        "- Do not stage workloads with `operator_signal=do_not_schedule` in Nutanix Move.",
        "- Do not treat no-breakage rows as clean if `coverage_risk=critical_coverage_gap` or `coverage_risk=coverage_followup`.",
        "- Re-run the assessment after remediation and confirm the brief no longer lists the workload under top breakage scenarios.",
    ]
    return "\n".join(lines) + "\n"


def brief_summary(rows: list[dict[str, str]]) -> dict[str, int]:
    return {
        "rows": len(rows),
        "workloads": len({row.get("workload_id", "") for row in rows if row.get("workload_id")}),
        "do_not_schedule": count_rows(rows, "operator_signal", "do_not_schedule"),
        "critical_coverage_gap": count_rows(rows, "coverage_risk", "critical_coverage_gap"),
        "hold": count_rows(rows, "move_staging_decision", "hold"),
        "conditional_review": count_rows(rows, "move_staging_decision", "conditional_review"),
        "include_after_validation": count_rows(rows, "move_staging_decision", "include_after_validation"),
    }


def count_rows(rows: list[dict[str, str]], field: str, value: str) -> int:
    return sum(1 for row in rows if row.get(field) == value)


def executive_signal(summary: dict[str, int]) -> str:
    if summary["do_not_schedule"]:
        return "Hold blocked workloads out of Nutanix Move until remediation or formal risk acceptance closes the listed breakages."
    if summary["critical_coverage_gap"]:
        return "Complete missing source inventory before treating the no-breakage signal as reliable."
    if summary["conditional_review"]:
        return "Proceed with planning only after compatibility and dependency review."
    return "Proceed with controlled staging only after owner sign-off and pre-migration validation."


def breakage_summary_lines(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- No breakage rows were generated."]
    by_code: dict[str, dict[str, Any]] = {}
    for row in rows:
        code = row.get("finding_code") or "unknown"
        entry = by_code.setdefault(
            code,
            {
                "count": 0,
                "severity": row.get("severity") or "unknown",
                "owners": set(),
                "waves": set(),
                "signals": set(),
            },
        )
        entry["count"] += 1
        entry["owners"].add(row.get("owner") or "Unassigned")
        entry["waves"].add(row.get("wave") or "Unassigned")
        entry["signals"].add(row.get("operator_signal") or "unknown")
    lines = []
    for code, entry in sorted(by_code.items(), key=lambda item: (-int(item[1]["count"]), severity_rank(str(item[1]["severity"])), item[0])):
        lines.append(
            f"- `{code}`: {entry['count']} row(s), severity `{entry['severity']}`, "
            f"owners `{'; '.join(sorted(entry['owners']))}`, waves `{'; '.join(sorted(entry['waves']))}`, "
            f"signals `{'; '.join(sorted(entry['signals']))}`."
        )
    return lines


def top_breakage_lines(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- No open readiness breakage scenarios were detected from the supplied evidence."]
    lines = []
    for row in rows:
        lines.append(
            f"- [{row.get('severity') or 'unknown'}] {row.get('name') or 'unknown'} "
            f"(`{row.get('workload_id') or 'unknown'}`), owner `{row.get('owner') or 'Unassigned'}`, "
            f"wave `{row.get('wave') or 'Unassigned'}`: `{row.get('finding_code') or 'unknown'}`. "
            f"Impact: {row.get('impact') or 'unknown'} Action: {row.get('required_action') or 'unknown'} "
            f"Evidence: `{row.get('evidence_refs') or 'none'}`."
        )
    return lines


def owner_wave_hold_lines(rows: list[dict[str, str]]) -> list[str]:
    held = [row for row in rows if row.get("move_staging_decision") == "hold"]
    if not held:
        return ["- No held workload rows were generated."]
    by_owner_wave: dict[tuple[str, str], set[str]] = {}
    for row in held:
        key = (row.get("owner") or "Unassigned", row.get("wave") or "Unassigned")
        by_owner_wave.setdefault(key, set()).add(row.get("name") or row.get("workload_id") or "unknown")
    return [
        f"- Owner `{owner}`, wave `{wave}`: hold `{'; '.join(sorted(workloads))}`."
        for (owner, wave), workloads in sorted(by_owner_wave.items())
    ]


def clean_signal_lines(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return ["- No clean no-breakage rows were generated."]
    return [
        f"- {row.get('name') or 'unknown'} (`{row.get('workload_id') or 'unknown'}`): "
        f"`{row.get('operator_signal') or 'unknown'}`, coverage `{row.get('coverage_risk') or 'unknown'}`, "
        f"evidence `{row.get('evidence_refs') or 'none'}`."
        for row in rows
    ]


def brief_row_sort_key(row: dict[str, str]) -> tuple[int, int, str, str]:
    return (
        severity_rank(row.get("severity") or ""),
        -safe_int(row.get("risk_score")),
        row.get("name") or "",
        row.get("finding_code") or "",
    )


def severity_rank(severity: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3, "none": 4}.get(severity.lower(), 5)


def safe_int(value: str | None) -> int:
    try:
        return int(value or 0)
    except ValueError:
        return 0


def normalize_markdown(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())


def breakage_row(
    assessment: WorkloadAssessment,
    finding: Finding,
    wave_by_workload: dict[str, str],
    coverage_row: dict[str, str | int] | None = None,
) -> dict[str, str]:
    gaps = inventory_coverage_gaps(coverage_row)
    risk = coverage_risk(coverage_row)
    return {
        "schema_version": WHAT_WILL_BREAK_SCHEMA_VERSION,
        "workload_id": assessment.workload_id,
        "name": assessment.name,
        "owner": assessment.owner,
        "target": assessment.target,
        "wave": wave_by_workload.get(assessment.workload_id, "Unassigned"),
        "readiness": assessment.readiness,
        "risk_score": str(assessment.risk_score),
        "finding_code": finding.code,
        "severity": finding.severity,
        "inventory_coverage_percent": inventory_coverage_percent(coverage_row),
        "inventory_coverage_gaps": gaps,
        "coverage_risk": risk,
        "move_staging_decision": move_staging_decision(assessment),
        "breakage_scenario": breakage_scenario(assessment, finding, risk),
        "impact": impact_statement(assessment, finding, risk),
        "operator_signal": operator_signal(assessment, finding, risk),
        "required_action": finding.recommended_action,
        "evidence_refs": evidence_refs(assessment, finding),
    }


def move_staging_decision(assessment: WorkloadAssessment) -> str:
    if assessment.readiness in {"prepare", "blocked"}:
        return "hold"
    if assessment.readiness == "research":
        return "conditional_review"
    return "include_after_validation"


def breakage_scenario(assessment: WorkloadAssessment, finding: Finding, risk: str = "unknown") -> str:
    if finding.code == "no_open_readiness_breakage":
        if risk in {"critical_coverage_gap", "coverage_followup"}:
            return "No detected readiness finding, but incomplete inventory evidence could hide migration breakage."
        return "No detected breakage from current evidence; migration can still fail if validation or owner sign-off is skipped."
    return f"{assessment.name}: {finding.message}"


def impact_statement(assessment: WorkloadAssessment, finding: Finding, risk: str = "unknown") -> str:
    severity = finding.severity.lower()
    if finding.code == "no_open_readiness_breakage":
        if risk == "critical_coverage_gap":
            return "Critical inventory evidence is missing or partial; migration risk may be understated until source data is completed."
        if risk == "coverage_followup":
            return "Inventory evidence has gaps; confirm missing facts before relying on the no-breakage signal."
        return "No readiness blocker detected; residual risk depends on pre/post validation evidence."
    if assessment.readiness == "blocked" or severity == "critical":
        return "Likely migration blocker; staging too early can cause failed cutover, application outage, or rollback."
    if assessment.readiness == "prepare" or severity == "high":
        return "Remediation required before controlled staging; unresolved evidence can delay or fail the wave."
    if assessment.readiness == "research" or severity == "medium":
        return "Compatibility or dependency review required before scheduling."
    return "Low-risk finding; confirm during owner review and pre-migration validation."


def operator_signal(assessment: WorkloadAssessment, finding: Finding, risk: str = "unknown") -> str:
    if finding.code == "no_open_readiness_breakage":
        if risk == "critical_coverage_gap":
            return "complete_inventory_before_schedule"
        if risk == "coverage_followup":
            return "review_inventory_gaps"
        return "confirm_owner_signoff"
    if assessment.readiness in {"prepare", "blocked"}:
        return "do_not_schedule"
    if assessment.readiness == "research":
        return "research_before_schedule"
    if finding.severity in {"critical", "high"}:
        return "risk_acceptance_required"
    return "review_before_schedule"


def evidence_refs(assessment: WorkloadAssessment, finding: Finding) -> str:
    refs = [
        f"assessment.json#{assessment.workload_id}",
        f"migration-risk-register.csv#{finding.code}",
        f"move-staging-readiness.csv#{assessment.workload_id}",
        f"owner-risk-summary.csv#{assessment.owner}",
    ]
    if finding.code == "no_open_readiness_breakage":
        refs.append(f"workload-validation-checklist.csv#{assessment.workload_id}")
    else:
        refs.append(f"remediation-tracker.csv#{assessment.workload_id}:{finding.code}")
    return ";".join(refs)


def inventory_coverage_percent(coverage_row: dict[str, str | int] | None) -> str:
    if not coverage_row:
        return "unknown"
    return str(coverage_row.get("coverage_percent") or "unknown")


def inventory_coverage_gaps(coverage_row: dict[str, str | int] | None) -> str:
    if not coverage_row:
        return "unknown"
    gaps = field_set(coverage_row.get("missing_fields")).union(field_set(coverage_row.get("partial_fields")))
    return ";".join(sorted(gaps)) if gaps else "none"


def coverage_risk(coverage_row: dict[str, str | int] | None) -> str:
    if not coverage_row:
        return "unknown"
    gaps = field_set(coverage_row.get("missing_fields")).union(field_set(coverage_row.get("partial_fields")))
    if CRITICAL_INCLUDED_FIELDS.intersection(gaps):
        return "critical_coverage_gap"
    try:
        coverage_percent = int(coverage_row.get("coverage_percent") or 0)
    except (TypeError, ValueError):
        return "coverage_followup"
    if gaps or coverage_percent < 90:
        return "coverage_followup"
    return "complete"


def field_set(value: str | int | None) -> set[str]:
    return {item.strip() for item in str(value or "").split(";") if item.strip()}


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in WHAT_WILL_BREAK_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read what-will-break report: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_breakage_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("what_will_break_context") if isinstance(assessment.get("what_will_break_context"), dict) else {}
    rows = context.get("rows") if isinstance(context.get("rows"), list) else []
    if context.get("schema_version") != WHAT_WILL_BREAK_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {WHAT_WILL_BREAK_SCHEMA_VERSION} what-will-break context")
    context_rows: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = {column: str(row.get(column) or "") for column in WHAT_WILL_BREAK_COLUMNS}
        context_rows[row_key(normalized)] = normalized

    derived = derive_breakage_rows_from_assessment(assessment, errors)
    if derived and context_rows and derived != context_rows:
        errors.append("assessment.json what_will_break_context does not match assessments, waves, and inventory coverage")
    return derived or context_rows


def derive_breakage_rows_from_assessment(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    assessments = parse_workload_assessments(assessment, errors)
    waves = parse_waves(assessment, {item.workload_id for item in assessments}, errors)
    coverage_rows = parse_inventory_coverage_context(assessment, errors)
    if not assessments:
        return {}
    rows = what_will_break_rows(assessments, waves, coverage_rows=coverage_rows)
    return {row_key(row): row for row in rows}


def parse_workload_assessments(assessment: dict[str, Any], errors: list[str]) -> list[WorkloadAssessment]:
    rows = assessment.get("assessments") if isinstance(assessment.get("assessments"), list) else []
    if not rows:
        errors.append("assessment.json assessments must contain workload assessment rows")
        return []
    assessments: list[WorkloadAssessment] = []
    seen: set[str] = set()
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json assessments row {index} must be an object")
            continue
        workload_id = str(row.get("workload_id") or "")
        if not workload_id:
            errors.append(f"assessment.json assessments row {index} missing workload_id")
        elif workload_id in seen:
            errors.append(f"assessment.json duplicate workload_id {workload_id!r}")
        seen.add(workload_id)
        findings = []
        finding_rows = row.get("findings") if isinstance(row.get("findings"), list) else []
        for finding_index, finding in enumerate(finding_rows, start=1):
            if not isinstance(finding, dict):
                errors.append(f"assessment.json {workload_id} finding row {finding_index} must be an object")
                continue
            findings.append(
                Finding(
                    code=str(finding.get("code") or ""),
                    severity=str(finding.get("severity") or ""),
                    message=str(finding.get("message") or ""),
                    recommended_action=str(finding.get("recommended_action") or ""),
                )
            )
        try:
            risk_score = int(row.get("risk_score") or 0)
        except (TypeError, ValueError):
            errors.append(f"assessment.json {workload_id} risk_score must be an integer")
            risk_score = 0
        assessments.append(
            WorkloadAssessment(
                workload_id=workload_id,
                name=str(row.get("name") or ""),
                owner=str(row.get("owner") or "Unassigned"),
                readiness=str(row.get("readiness") or ""),
                risk_score=risk_score,
                target=str(row.get("target") or ""),
                findings=tuple(findings),
            )
        )
    return assessments


def parse_waves(assessment: dict[str, Any], workload_ids: set[str], errors: list[str]) -> list[Wave]:
    rows = assessment.get("waves") if isinstance(assessment.get("waves"), list) else []
    if not rows:
        errors.append("assessment.json waves must contain wave rows")
        return []
    waves: list[Wave] = []
    assigned: dict[str, str] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json waves row {index} must be an object")
            continue
        name = str(row.get("name") or "Unassigned")
        ids = row.get("workload_ids") if isinstance(row.get("workload_ids"), list) else []
        normalized_ids: list[str] = []
        for workload_id in ids:
            if not isinstance(workload_id, str):
                continue
            if workload_id not in workload_ids:
                errors.append(f"assessment.json wave {name!r} references unknown workload_id {workload_id!r}")
            previous = assigned.get(workload_id)
            if previous:
                errors.append(
                    f"assessment.json workload_id {workload_id!r} appears in multiple waves: "
                    f"{previous!r} and {name!r}"
                )
            assigned[workload_id] = name
            normalized_ids.append(workload_id)
        waves.append(
            Wave(
                name=name,
                description=str(row.get("description") or ""),
                workload_ids=tuple(normalized_ids),
            )
        )
    return waves


def parse_inventory_coverage_context(assessment: dict[str, Any], errors: list[str]) -> list[dict[str, str]]:
    context = assessment.get("inventory_coverage_context") if isinstance(assessment.get("inventory_coverage_context"), dict) else {}
    if context.get("schema_version") != INVENTORY_COVERAGE_CONTEXT_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {INVENTORY_COVERAGE_CONTEXT_SCHEMA_VERSION} inventory coverage context")
    rows = context.get("rows") if isinstance(context.get("rows"), list) else []
    by_workload: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=1):
        if not isinstance(row, dict):
            errors.append(f"assessment.json inventory coverage row {index} must be an object")
            continue
        normalized = {column: str(row.get(column) or "") for column in INVENTORY_COVERAGE_COLUMNS}
        workload_id = normalized["workload_id"]
        if not workload_id:
            errors.append(f"assessment.json inventory coverage row {index} missing workload_id")
        if workload_id in by_workload:
            errors.append(f"assessment.json duplicate inventory coverage workload_id {workload_id!r}")
        by_workload[workload_id] = normalized
    return list(by_workload.values())


def row_key(row: dict[str, str]) -> str:
    return f"{row.get('workload_id', '')}|{row.get('finding_code', '')}"
