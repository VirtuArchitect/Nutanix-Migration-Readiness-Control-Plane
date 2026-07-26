from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import WorkloadAssessment
from .scoring import SUPPORTED_GUEST_FAMILIES


COMPATIBILITY_RESEARCH_SCHEMA_VERSION = "nmrcp_compatibility_research_v1"
COMPATIBILITY_RESEARCH_COLUMNS = (
    "schema_version",
    "workload_id",
    "name",
    "owner",
    "target",
    "readiness",
    "tier",
    "guest_os",
    "guest_os_status",
    "vendor_support",
    "target_support_status",
    "compatibility_status",
    "blocking_findings",
    "required_action",
    "evidence_refs",
)


@dataclass(frozen=True)
class CompatibilityResearchValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def compatibility_research_context(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
) -> dict[str, Any]:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    return {
        "schema_version": COMPATIBILITY_RESEARCH_SCHEMA_VERSION,
        "workloads": [
            compatibility_row(workloads.get(assessment.workload_id, {}), assessment)
            for assessment in assessments
        ],
    }


def write_compatibility_research_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    path: Path,
) -> None:
    rows = compatibility_research_context(inventory, assessments)["workloads"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=COMPATIBILITY_RESEARCH_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_compatibility_research(path: Path, assessment_path: Path) -> CompatibilityResearchValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return CompatibilityResearchValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_compatibility_rows(assessment, errors)
    keyed_rows = {row.get("workload_id", ""): row for row in rows}
    if len(keyed_rows) != len(rows):
        errors.append("compatibility-research.csv contains duplicate workload rows")

    missing = sorted(set(expected).difference(keyed_rows))
    extra = sorted(set(keyed_rows).difference(expected))
    for key in missing:
        errors.append(f"Missing compatibility research row: {key}")
    for key in extra:
        errors.append(f"Unexpected compatibility research row: {key}")

    for key, expected_row in expected.items():
        row = keyed_rows.get(key)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{key}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("compatibility-research.csv cannot be empty")

    return CompatibilityResearchValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def compatibility_row(workload: dict[str, Any], assessment: WorkloadAssessment) -> dict[str, str]:
    tier = str(workload.get("tier") or "unspecified").strip() or "unspecified"
    guest_os = str(workload.get("guest_os") or "").strip()
    vendor_support = [str(item).strip().lower() for item in workload.get("vendor_support", []) if str(item).strip()]
    finding_codes = [
        finding.code
        for finding in assessment.findings
        if finding.code in {"guest_os_missing", "guest_os_research_required", "vendor_support_unconfirmed"}
    ]
    guest_status = guest_os_status(guest_os)
    target_status = target_support_status(tier, assessment.target, vendor_support)
    status = compatibility_status(guest_status, target_status)
    return {
        "schema_version": COMPATIBILITY_RESEARCH_SCHEMA_VERSION,
        "workload_id": assessment.workload_id,
        "name": assessment.name,
        "owner": assessment.owner,
        "target": assessment.target,
        "readiness": assessment.readiness,
        "tier": tier,
        "guest_os": guest_os or "not captured",
        "guest_os_status": guest_status,
        "vendor_support": "; ".join(vendor_support) if vendor_support else "not declared",
        "target_support_status": target_status,
        "compatibility_status": status,
        "blocking_findings": "; ".join(finding_codes),
        "required_action": required_action(status, guest_status, target_status),
        "evidence_refs": f"assessment.json#{assessment.workload_id};target-readiness-comparison.csv#{assessment.workload_id};readiness-policy.md#{assessment.workload_id}",
    }


def guest_os_status(guest_os: str) -> str:
    normalized = guest_os.lower()
    if not normalized:
        return "missing"
    if any(family in normalized for family in SUPPORTED_GUEST_FAMILIES):
        return "known_good"
    return "research_required"


def target_support_status(tier: str, target: str, vendor_support: list[str]) -> str:
    if target in vendor_support:
        return "confirmed"
    if tier.lower() == "critical":
        return "unconfirmed"
    if vendor_support:
        return "review"
    return "not_declared"


def compatibility_status(guest_status: str, support_status: str) -> str:
    if guest_status == "missing":
        return "blocked"
    if guest_status == "research_required" or support_status in {"unconfirmed", "review", "not_declared"}:
        return "research"
    return "ready"


def required_action(status: str, guest_status: str, support_status: str) -> str:
    actions: list[str] = []
    if guest_status == "missing":
        actions.append("Collect guest OS from vCenter tools, RVTools, CMDB, or application owner.")
    if guest_status == "research_required":
        actions.append("Verify guest OS against the Nutanix support matrix and application owner evidence.")
    if support_status == "unconfirmed":
        actions.append("Obtain target-platform support approval for this critical workload.")
    elif support_status in {"review", "not_declared"}:
        actions.append("Confirm application/vendor target support before production scheduling.")
    if actions:
        return " ".join(actions)
    if status == "ready":
        return "Confirm compatibility evidence during final change review."
    return "Complete compatibility research before Move staging."


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in COMPATIBILITY_RESEARCH_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read compatibility research CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_compatibility_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("compatibility_research_context") if isinstance(assessment.get("compatibility_research_context"), dict) else {}
    rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != COMPATIBILITY_RESEARCH_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {COMPATIBILITY_RESEARCH_SCHEMA_VERSION} compatibility research context")
    expected: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = {key: str(row.get(key) or "") for key in COMPATIBILITY_RESEARCH_COLUMNS}
        expected[normalized["workload_id"]] = normalized
    return expected
