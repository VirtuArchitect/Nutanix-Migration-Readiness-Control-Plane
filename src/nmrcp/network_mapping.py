from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .move_payload import included_workloads, load_move_config


NETWORK_MAPPING_SCHEMA_VERSION = "nmrcp_target_network_mapping_v1"


@dataclass(frozen=True)
class NetworkMappingValidation:
    checked_count: int
    mapped_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return (
            f"{status}: checked={self.checked_count}, mapped={self.mapped_count}, "
            f"errors={len(self.errors)}, warnings={len(self.warnings)}"
        )


def validate_network_mappings(plan_path: Path, config_path: Path) -> NetworkMappingValidation:
    config = load_move_config(config_path)
    mapping_by_source = {
        str(mapping.get("source_network") or "").strip(): str(mapping.get("target_network") or "").strip()
        for mapping in config.get("network_mappings", [])
        if isinstance(mapping, dict)
    }
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, Any]] = []
    for workload in included_workloads(plan_path):
        networks = workload.get("target_networks") if isinstance(workload.get("target_networks"), list) else []
        if not networks:
            errors.append(f"{workload['source_vm_id']}: included workload has no target network hints")
            rows.append(_row(workload, "", "", "fail", "included workload has no target network hints"))
            continue
        for source_network in networks:
            target_network = mapping_by_source.get(str(source_network))
            if target_network:
                rows.append(_row(workload, str(source_network), target_network, "pass", "network mapping found"))
            else:
                errors.append(f"{workload['source_vm_id']}: source network {source_network!r} is not mapped")
                rows.append(_row(workload, str(source_network), "", "fail", "source network is not mapped"))

    for source_network in sorted(set(mapping_by_source) - {str(row["source_network"]) for row in rows}):
        warnings.append(f"Configured network mapping {source_network!r} is not used by included workloads")

    mapped_count = sum(1 for row in rows if row["status"] == "pass")
    return NetworkMappingValidation(len(rows), mapped_count, tuple(errors), tuple(warnings), tuple(rows))


def write_network_mapping_csv(result: NetworkMappingValidation, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "schema_version",
        "source_vm_id",
        "source_vm_name",
        "wave",
        "owner",
        "target",
        "source_network",
        "target_network",
        "status",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(result.rows)
    return path


def validate_network_mapping_csv(path: Path) -> NetworkMappingValidation:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    errors: list[str] = []
    warnings: list[str] = []
    if not rows:
        return NetworkMappingValidation(0, 0, ("target-network-mapping.csv must contain at least one row",), (), ())
    for index, row in enumerate(rows, start=2):
        if row.get("schema_version") != NETWORK_MAPPING_SCHEMA_VERSION:
            errors.append(f"Row {index}: schema_version must be {NETWORK_MAPPING_SCHEMA_VERSION}")
        status = (row.get("status") or "").strip().lower()
        if status not in {"pass", "fail"}:
            errors.append(f"Row {index}: status must be pass or fail")
        if status == "fail":
            errors.append(f"Row {index}: network mapping failed for {row.get('source_vm_id')}: {row.get('notes')}")
        if status == "pass" and not (row.get("target_network") or "").strip():
            errors.append(f"Row {index}: passed network mapping must include target_network")
    mapped_count = sum(1 for row in rows if row.get("status") == "pass")
    return NetworkMappingValidation(len(rows), mapped_count, tuple(errors), tuple(warnings), tuple(rows))


def _row(
    workload: dict[str, Any],
    source_network: str,
    target_network: str,
    status: str,
    notes: str,
) -> dict[str, Any]:
    return {
        "schema_version": NETWORK_MAPPING_SCHEMA_VERSION,
        "source_vm_id": workload.get("source_vm_id", ""),
        "source_vm_name": workload.get("source_vm_name", ""),
        "wave": workload.get("wave", ""),
        "owner": workload.get("owner", ""),
        "target": workload.get("target", ""),
        "source_network": source_network,
        "target_network": target_network,
        "status": status,
        "notes": notes,
    }
