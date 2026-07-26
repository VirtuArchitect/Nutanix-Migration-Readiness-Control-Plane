from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Wave, WorkloadAssessment
from .redaction import redact_value


IDENTITY_CUTOVER_SCHEMA_VERSION = "nmrcp_identity_cutover_plan_v1"
IDENTITY_CUTOVER_COLUMNS = (
    "schema_version",
    "workload_id",
    "name",
    "owner",
    "target",
    "wave",
    "move_plan_decision",
    "readiness",
    "hostname",
    "dns_name",
    "valid_ip_addresses",
    "invalid_ip_addresses",
    "source_networks",
    "identity_status",
    "required_action",
    "evidence_refs",
)


@dataclass(frozen=True)
class IdentityCutoverPlanValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def identity_cutover_context(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
) -> dict[str, Any]:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    rows = [
        identity_row(assessment, workloads.get(assessment.workload_id, {}), wave_by_workload.get(assessment.workload_id, "Unassigned"))
        for assessment in assessments
    ]
    return {
        "schema_version": IDENTITY_CUTOVER_SCHEMA_VERSION,
        "workloads": rows,
    }


def write_identity_cutover_plan_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    rows = identity_cutover_context(inventory, assessments, waves)["workloads"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=IDENTITY_CUTOVER_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def validate_identity_cutover_plan(path: Path, assessment_path: Path) -> IdentityCutoverPlanValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return IdentityCutoverPlanValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_identity_rows(assessment, errors)
    keyed_rows = {row.get("workload_id", ""): row for row in rows}
    if len(keyed_rows) != len(rows):
        errors.append("identity-cutover-plan.csv contains duplicate workload rows")

    missing = sorted(set(expected).difference(keyed_rows))
    extra = sorted(set(keyed_rows).difference(expected))
    for key in missing:
        errors.append(f"Missing identity cutover row: {key}")
    for key in extra:
        errors.append(f"Unexpected identity cutover row: {key}")

    for key, expected_row in expected.items():
        row = keyed_rows.get(key)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{key}: {field} expected {expected_value!r}, got {actual!r}")

    return IdentityCutoverPlanValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def identity_row(assessment: WorkloadAssessment, workload: dict[str, Any], wave: str) -> dict[str, str]:
    guest_identity = workload.get("guest_identity") if isinstance(workload.get("guest_identity"), dict) else {}
    networking = workload.get("networking") if isinstance(workload.get("networking"), dict) else {}
    hostname = str(guest_identity.get("hostname") or "").strip()
    dns_name = str(guest_identity.get("dns_name") or "").strip()
    valid_ips = string_list(guest_identity.get("valid_ip_addresses"))
    invalid_ips = string_list(guest_identity.get("invalid_ip_addresses"))
    source_networks = string_list(networking.get("vlans") or networking.get("networks") or networking.get("portgroups"))
    decision = "include" if assessment.readiness in {"ready", "research"} else "hold"
    status = identity_status(
        move_plan_decision=decision,
        hostname=hostname,
        dns_name=dns_name,
        valid_ips=valid_ips,
        invalid_ips=invalid_ips,
        source_networks=source_networks,
    )
    return {
        "schema_version": IDENTITY_CUTOVER_SCHEMA_VERSION,
        "workload_id": assessment.workload_id,
        "name": assessment.name,
        "owner": assessment.owner,
        "target": assessment.target,
        "wave": wave,
        "move_plan_decision": decision,
        "readiness": assessment.readiness,
        "hostname": hostname or "not captured",
        "dns_name": dns_name or "not captured",
        "valid_ip_addresses": redacted_list(valid_ips) if valid_ips else "not captured",
        "invalid_ip_addresses": redacted_list(invalid_ips) if invalid_ips else "none",
        "source_networks": "; ".join(source_networks) if source_networks else "not captured",
        "identity_status": status,
        "required_action": required_action(status),
        "evidence_refs": f"assessment.json#{assessment.workload_id};identity-cutover-plan.csv#{assessment.workload_id};source-network-validation.csv#{assessment.workload_id};target-network-mapping.csv#{assessment.workload_id}",
    }


def identity_status(
    *,
    move_plan_decision: str,
    hostname: str,
    dns_name: str,
    valid_ips: list[str],
    invalid_ips: list[str],
    source_networks: list[str],
) -> str:
    if invalid_ips:
        return "blocked"
    if move_plan_decision == "hold":
        return "hold"
    if not valid_ips or not source_networks:
        return "blocked"
    if not hostname or not dns_name:
        return "review"
    return "ready"


def required_action(status: str) -> str:
    if status == "blocked":
        return "Fix source IP, DNS, hostname, or network evidence before Move staging or cutover approval."
    if status == "hold":
        return "Keep identity evidence with remediation work; do not stage until workload readiness clears."
    if status == "review":
        return "Confirm hostname and DNS owner actions before cutover approval."
    return "Confirm DNS, IPAM, hostname, and application identity during pre/post validation."


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    return [text] if text else []


def redacted_list(values: list[str]) -> str:
    return str(redact_value("; ".join(values)))


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in IDENTITY_CUTOVER_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read identity cutover CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_identity_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    context = assessment.get("identity_cutover_context") if isinstance(assessment.get("identity_cutover_context"), dict) else {}
    rows = context.get("workloads") if isinstance(context.get("workloads"), list) else []
    if context.get("schema_version") != IDENTITY_CUTOVER_SCHEMA_VERSION:
        errors.append(f"assessment.json missing {IDENTITY_CUTOVER_SCHEMA_VERSION} identity cutover context")
    expected: dict[str, dict[str, str]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = {key: str(row.get(key) or "") for key in IDENTITY_CUTOVER_COLUMNS}
        expected[normalized["workload_id"]] = normalized
    return expected
