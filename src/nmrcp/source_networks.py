from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .move_payload import included_workloads


SOURCE_NETWORK_VALIDATION_SCHEMA_VERSION = "nmrcp_source_network_validation_v1"
VCENTER_NETWORK_INVENTORY_SCHEMA_VERSION = "nmrcp_vcenter_network_inventory_v1"


@dataclass(frozen=True)
class SourceNetworkValidation:
    checked_count: int
    matched_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return (
            f"{status}: checked={self.checked_count}, matched={self.matched_count}, "
            f"errors={len(self.errors)}, warnings={len(self.warnings)}"
        )


def validate_source_networks(plan_path: Path, networks_path: Path) -> SourceNetworkValidation:
    network_payload = json.loads(networks_path.read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    available = source_network_lookup(network_payload, errors)
    if not available:
        warnings.append("vCenter network inventory contains no source network identifiers")

    for workload in included_workloads(plan_path):
        networks = workload.get("target_networks") if isinstance(workload.get("target_networks"), list) else []
        if not networks:
            errors.append(f"{workload['source_vm_id']}: included workload has no source network hints")
            rows.append(_row(workload, "", "fail", "included workload has no source network hints"))
            continue
        for source_network in networks:
            source_text = str(source_network).strip()
            if source_text in available:
                rows.append(_row(workload, source_text, "pass", "source network found in vCenter network inventory"))
            else:
                errors.append(f"{workload['source_vm_id']}: source network {source_text!r} was not found in vCenter network inventory")
                rows.append(_row(workload, source_text, "fail", "source network missing from vCenter network inventory"))

    matched_count = sum(1 for row in rows if row["status"] == "pass")
    return SourceNetworkValidation(len(rows), matched_count, tuple(errors), tuple(warnings), tuple(rows))


def source_network_lookup(payload: dict[str, Any], errors: list[str]) -> set[str]:
    if payload.get("schema_version") != VCENTER_NETWORK_INVENTORY_SCHEMA_VERSION:
        errors.append(f"vCenter network inventory schema_version must be {VCENTER_NETWORK_INVENTORY_SCHEMA_VERSION}")
        return set()
    source = payload.get("source") if isinstance(payload.get("source"), dict) else {}
    if source.get("mutating_calls") != 0:
        errors.append("vCenter network inventory source.mutating_calls must be 0")
    networks = payload.get("networks")
    if not isinstance(networks, list):
        errors.append("vCenter network inventory must contain a networks list")
        return set()
    identifiers: set[str] = set()
    for item in networks:
        if not isinstance(item, dict):
            continue
        for key in ("network", "name", "vlan", "vlan_id"):
            value = str(item.get(key) or "").strip()
            if value:
                identifiers.add(value)
        vlans = item.get("vlans")
        if isinstance(vlans, list):
            identifiers.update(str(value).strip() for value in vlans if str(value).strip())
    return identifiers


def write_source_network_validation_csv(result: SourceNetworkValidation, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "schema_version",
        "source_vm_id",
        "source_vm_name",
        "wave",
        "owner",
        "target",
        "source_network",
        "status",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(result.rows)
    return path


def validate_source_network_validation_csv(path: Path) -> SourceNetworkValidation:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    errors: list[str] = []
    if not rows:
        return SourceNetworkValidation(0, 0, ("source-network-validation.csv must contain at least one row",), (), ())
    for index, row in enumerate(rows, start=2):
        if row.get("schema_version") != SOURCE_NETWORK_VALIDATION_SCHEMA_VERSION:
            errors.append(f"Row {index}: schema_version must be {SOURCE_NETWORK_VALIDATION_SCHEMA_VERSION}")
        status = (row.get("status") or "").strip().lower()
        if status not in {"pass", "fail"}:
            errors.append(f"Row {index}: status must be pass or fail")
        if status == "fail":
            errors.append(f"Row {index}: source network validation failed for {row.get('source_vm_id')}: {row.get('notes')}")
    matched_count = sum(1 for row in rows if row.get("status") == "pass")
    return SourceNetworkValidation(len(rows), matched_count, tuple(errors), (), tuple(rows))


def _row(workload: dict[str, Any], source_network: str, status: str, notes: str) -> dict[str, Any]:
    return {
        "schema_version": SOURCE_NETWORK_VALIDATION_SCHEMA_VERSION,
        "source_vm_id": workload.get("source_vm_id", ""),
        "source_vm_name": workload.get("source_vm_name", ""),
        "wave": workload.get("wave", ""),
        "owner": workload.get("owner", ""),
        "target": workload.get("target", ""),
        "source_network": source_network,
        "status": status,
        "notes": notes,
    }
