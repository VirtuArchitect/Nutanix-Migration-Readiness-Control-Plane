from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


DASHBOARD_SCHEMA_VERSION = "nmrcp_operator_dashboard_v1"
REQUIRED_TEXT = (
    "<!doctype html>",
    "<title>NMRCP Operator Dashboard</title>",
    "Nutanix Migration Readiness Dashboard",
    "Readiness Summary",
    "Operator Work Queue",
    "Workload filters",
    "Do not stage prepare or blocked workloads in Nutanix Move.",
    "Confirm owner approval, backup proof, rollback owner, and network mapping before cutover.",
    "Re-run assessment after remediation and verify the readiness state changes.",
)


@dataclass(frozen=True)
class OperatorDashboardValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_operator_dashboard(dashboard_path: Path, assessment_path: Path) -> OperatorDashboardValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0

    try:
        raw_text = dashboard_path.read_text(encoding="utf-8")
    except OSError as exc:
        return OperatorDashboardValidation("fail", 1, (f"{dashboard_path}: could not read operator dashboard: {exc}",), ())

    try:
        assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return OperatorDashboardValidation("fail", 1, (f"{assessment_path}: could not read assessment JSON: {exc}",), ())

    text = html.unescape(raw_text)

    for required in REQUIRED_TEXT:
        checks += 1
        if required not in text:
            errors.append(f"Operator dashboard missing required text: {required}")

    payload = extract_dashboard_payload(raw_text, errors)
    checks += 1
    if not payload:
        return OperatorDashboardValidation("fail", checks, tuple(errors), tuple(warnings))

    checks += 1
    if payload.get("schema_version") != DASHBOARD_SCHEMA_VERSION:
        errors.append(f"Operator dashboard schema_version must be {DASHBOARD_SCHEMA_VERSION}")

    summary = assessment.get("summary") if isinstance(assessment.get("summary"), dict) else {}
    dashboard_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    for key in ("total", "ready", "research", "prepare", "blocked"):
        checks += 1
        expected = int(summary.get(key) or 0)
        actual = int(dashboard_summary.get(key) or 0)
        if actual != expected:
            errors.append(f"Operator dashboard summary {key} expected {expected}, got {actual}")

    checks += 1
    expected_unmatched_dependencies = source_int(assessment, "dependency_unmatched_records")
    actual_unmatched_dependencies = int(payload.get("unmatched_dependencies") or 0)
    if actual_unmatched_dependencies != expected_unmatched_dependencies:
        errors.append(
            "Operator dashboard unmatched_dependencies expected "
            f"{expected_unmatched_dependencies}, got {actual_unmatched_dependencies}"
        )

    expected_rows = expected_workload_rows(assessment)
    rows = payload.get("workloads") if isinstance(payload.get("workloads"), list) else []
    rows_by_id = {str(row.get("id") or ""): row for row in rows if isinstance(row, dict)}

    checks += 1
    if len(rows_by_id) != len(rows):
        errors.append("Operator dashboard contains duplicate workload ids")

    for workload_id in sorted(set(expected_rows).difference(rows_by_id)):
        errors.append(f"Operator dashboard missing workload row: {workload_id}")
    for workload_id in sorted(set(rows_by_id).difference(expected_rows)):
        errors.append(f"Operator dashboard has unexpected workload row: {workload_id}")

    for workload_id, expected in expected_rows.items():
        row = rows_by_id.get(workload_id)
        if not row:
            continue
        for field in (
            "id",
            "name",
            "owner",
            "target",
            "readiness",
            "risk_score",
            "wave",
            "move_staging",
            "dependency_count",
        ):
            checks += 1
            actual = row.get(field)
            expected_value = expected[field]
            if actual != expected_value:
                errors.append(f"Operator dashboard {workload_id}: {field} expected {expected_value!r}, got {actual!r}")

        expected_findings = expected["findings"]
        actual_findings = row.get("findings") if isinstance(row.get("findings"), list) else []
        checks += 1
        if len(actual_findings) != len(expected_findings):
            errors.append(
                f"Operator dashboard {workload_id}: findings expected {len(expected_findings)}, got {len(actual_findings)}"
            )
        for index, expected_finding in enumerate(expected_findings):
            if index >= len(actual_findings) or not isinstance(actual_findings[index], dict):
                continue
            for field, expected_value in expected_finding.items():
                checks += 1
                actual = actual_findings[index].get(field)
                if actual != expected_value:
                    errors.append(
                        f"Operator dashboard {workload_id}: finding {index + 1} {field} expected {expected_value!r}, got {actual!r}"
                    )

    checks += 1
    if "vcenter01.corp.local" in text:
        errors.append("Operator dashboard leaked sample vCenter hostname")

    checks += 1
    if "migration.owner@example.com" in text:
        errors.append("Operator dashboard leaked sample operator email")

    return OperatorDashboardValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def extract_dashboard_payload(raw_text: str, errors: list[str]) -> dict[str, Any]:
    match = re.search(
        r'<script id="dashboard-data" type="application/json">(.*?)</script>',
        raw_text,
        flags=re.DOTALL,
    )
    if not match:
        errors.append("Operator dashboard missing dashboard-data JSON script")
        return {}
    try:
        payload = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError as exc:
        errors.append(f"Operator dashboard dashboard-data JSON is invalid: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append("Operator dashboard dashboard-data JSON must be an object")
        return {}
    return payload


def expected_workload_rows(assessment: dict[str, Any]) -> dict[str, dict[str, Any]]:
    wave_by_workload = {
        str(workload_id): str(wave.get("name") or "Unassigned")
        for wave in assessment.get("waves", [])
        if isinstance(wave, dict)
        for workload_id in wave.get("workload_ids", [])
        if isinstance(workload_id, str)
    }
    dependency_counts = expected_dependency_counts(assessment)
    rows: dict[str, dict[str, Any]] = {}
    for item in assessment.get("assessments", []):
        if not isinstance(item, dict):
            continue
        workload_id = str(item.get("workload_id") or "")
        readiness = str(item.get("readiness") or "")
        findings = item.get("findings") if isinstance(item.get("findings"), list) else []
        rows[workload_id] = {
            "id": workload_id,
            "name": str(item.get("name") or ""),
            "owner": str(item.get("owner") or "Unassigned"),
            "target": str(item.get("target") or ""),
            "readiness": readiness,
            "risk_score": int(item.get("risk_score") or 0),
            "wave": wave_by_workload.get(workload_id, "Unassigned"),
            "move_staging": "include after review" if readiness in {"ready", "research"} else "hold until remediated",
            "dependency_count": dependency_counts.get(workload_id, 0),
            "findings": [
                {
                    "severity": str(finding.get("severity") or ""),
                    "code": str(finding.get("code") or ""),
                    "message": str(finding.get("message") or ""),
                    "action": str(finding.get("recommended_action") or ""),
                }
                for finding in findings
                if isinstance(finding, dict)
            ],
        }
    return rows


def expected_dependency_counts(assessment: dict[str, Any]) -> dict[str, int]:
    context = assessment.get("dependency_review_context")
    if not isinstance(context, dict):
        return {}
    dependencies = context.get("dependencies") if isinstance(context.get("dependencies"), list) else []
    counts: dict[str, int] = {}
    for row in dependencies:
        if not isinstance(row, dict):
            continue
        if str(row.get("row_type") or "") != "dependency":
            continue
        workload_id = str(row.get("source_workload_id") or "")
        if workload_id:
            counts[workload_id] = counts.get(workload_id, 0) + 1
    return counts


def source_int(assessment: dict[str, Any], key: str) -> int:
    source = assessment.get("source")
    if not isinstance(source, dict):
        return 0
    return int(source.get(key) or 0)
