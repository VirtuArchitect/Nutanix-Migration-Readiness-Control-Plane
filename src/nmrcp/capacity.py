from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


CAPACITY_SCHEMA_VERSION = "nmrcp_target_capacity_v1"
CAPACITY_FIT_SCHEMA_VERSION = "nmrcp_target_capacity_fit_v1"


@dataclass(frozen=True)
class CapacityFitValidation:
    target_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    rows: tuple[dict[str, Any], ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return (
            f"{status}: targets={self.target_count}, errors={len(self.errors)}, "
            f"warnings={len(self.warnings)}"
        )


def validate_capacity_fit(
    inventory_path: Path,
    move_plan_path: Path,
    capacity_path: Path,
) -> CapacityFitValidation:
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    capacity = json.loads(capacity_path.read_text(encoding="utf-8"))
    plan_rows = _read_move_plan(move_plan_path)
    return validate_capacity_fit_payload(inventory, plan_rows, capacity)


def normalize_prism_capacity(
    clusters: list[dict[str, Any]],
    target: str = "ahv",
    cpu_reserved_percent: float = 20,
    memory_reserved_percent: float = 25,
    storage_reserved_percent: float = 30,
    cpu_overcommit_ratio: float = 1.0,
) -> dict[str, Any]:
    names: list[str] = []
    total_cpu = 0.0
    total_memory_gib = 0.0
    total_storage_gib = 0.0
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        name = _cluster_name(cluster)
        if name:
            names.append(name)
        total_cpu += _cluster_cpu_cores(cluster)
        total_memory_gib += _cluster_memory_gib(cluster)
        total_storage_gib += _cluster_storage_gib(cluster)

    return {
        "schema_version": CAPACITY_SCHEMA_VERSION,
        "source": {
            "system": "prism-central-v3",
            "mode": "read-only",
            "api_paths": ["/api/nutanix/v3/clusters/list"],
            "cluster_count": len(clusters),
            "mutating_calls": 0,
            "capacity_source": "prism_cluster_list",
        },
        "targets": [
            {
                "target": target.lower(),
                "cluster_name": ";".join(names) or "prism-cluster-capacity",
                "usable_cpu_cores": round(total_cpu, 2),
                "cpu_overcommit_ratio": cpu_overcommit_ratio,
                "cpu_reserved_percent": cpu_reserved_percent,
                "usable_memory_gib": round(total_memory_gib, 2),
                "memory_reserved_percent": memory_reserved_percent,
                "usable_storage_gib": round(total_storage_gib, 2),
                "storage_reserved_percent": storage_reserved_percent,
            }
        ],
    }


def validate_capacity_fit_payload(
    inventory: dict[str, Any],
    move_plan_rows: list[dict[str, str]],
    capacity: dict[str, Any],
) -> CapacityFitValidation:
    errors: list[str] = []
    warnings: list[str] = []

    if capacity.get("schema_version") != CAPACITY_SCHEMA_VERSION:
        errors.append(f"Capacity file schema_version must be {CAPACITY_SCHEMA_VERSION}")
    targets = capacity.get("targets")
    if not isinstance(targets, list) or not targets:
        return CapacityFitValidation(0, tuple(errors + ["Capacity file must contain a non-empty targets list"]), (), ())

    target_by_name: dict[str, dict[str, Any]] = {}
    for index, target in enumerate(targets):
        if not isinstance(target, dict):
            errors.append(f"targets[{index}] must be an object")
            continue
        name = str(target.get("target") or "").lower()
        if name not in {"ahv", "nc2"}:
            errors.append(f"targets[{index}].target must be ahv or nc2")
            continue
        if name in target_by_name:
            errors.append(f"Duplicate capacity target {name!r}")
        target_by_name[name] = target
        _validate_capacity_numbers(index, target, errors)

    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    included_by_target: dict[str, list[dict[str, str]]] = {}
    for row in move_plan_rows:
        if (row.get("include_in_move_plan") or "").strip().lower() != "yes":
            continue
        target = (row.get("target") or "").strip().lower()
        included_by_target.setdefault(target, []).append(row)
        if target not in target_by_name:
            errors.append(f"Move plan includes target {target!r} with no target capacity record")
        source_id = (row.get("source_vm_id") or "").strip()
        if source_id not in workloads:
            errors.append(f"Move plan workload {source_id!r} is missing from inventory")

    rows: list[dict[str, Any]] = []
    for target_name, target in sorted(target_by_name.items()):
        included = included_by_target.get(target_name, [])
        totals = _included_totals(included, workloads)
        available_cpu = _available(target, "usable_cpu_cores", "cpu_reserved_percent", multiplier_key="cpu_overcommit_ratio")
        available_memory = _available(target, "usable_memory_gib", "memory_reserved_percent")
        available_storage = _available(target, "usable_storage_gib", "storage_reserved_percent")
        row = {
            "schema_version": CAPACITY_FIT_SCHEMA_VERSION,
            "target": target_name,
            "cluster_name": str(target.get("cluster_name") or target.get("name") or "unknown"),
            "included_workloads": len(included),
            "required_cpu": totals["cpu"],
            "available_cpu": round(available_cpu, 2),
            "required_memory_gib": round(totals["memory_gib"], 2),
            "available_memory_gib": round(available_memory, 2),
            "required_storage_gib": round(totals["disk_gib"], 2),
            "available_storage_gib": round(available_storage, 2),
            "cpu_fit": totals["cpu"] <= available_cpu,
            "memory_fit": totals["memory_gib"] <= available_memory,
            "storage_fit": totals["disk_gib"] <= available_storage,
        }
        row["status"] = "pass" if row["cpu_fit"] and row["memory_fit"] and row["storage_fit"] else "fail"
        row["notes"] = _capacity_notes(row)
        rows.append(row)
        if row["status"] == "fail":
            errors.append(f"Target {target_name} capacity fit failed: {row['notes']}")
        warnings.extend(_headroom_warnings(row))

    return CapacityFitValidation(len(target_by_name), tuple(errors), tuple(warnings), tuple(rows))


def write_capacity_fit_csv(result: CapacityFitValidation, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "schema_version",
        "target",
        "cluster_name",
        "included_workloads",
        "required_cpu",
        "available_cpu",
        "required_memory_gib",
        "available_memory_gib",
        "required_storage_gib",
        "available_storage_gib",
        "cpu_fit",
        "memory_fit",
        "storage_fit",
        "status",
        "notes",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(result.rows)
    return path


def validate_capacity_fit_csv(path: Path) -> CapacityFitValidation:
    errors: list[str] = []
    warnings: list[str] = []
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return CapacityFitValidation(0, ("target-capacity-fit.csv must contain at least one row",), (), ())
    for index, row in enumerate(rows, start=2):
        if row.get("schema_version") != CAPACITY_FIT_SCHEMA_VERSION:
            errors.append(f"Row {index}: schema_version must be {CAPACITY_FIT_SCHEMA_VERSION}")
        target = (row.get("target") or "").strip()
        if not target:
            errors.append(f"Row {index}: target is required")
        status = (row.get("status") or "").strip().lower()
        if status not in {"pass", "fail"}:
            errors.append(f"Row {index}: status must be pass or fail")
        if status == "fail":
            errors.append(f"Row {index}: target {target} capacity fit failed: {row.get('notes') or 'no notes'}")
        if status == "pass":
            for label, required_key, available_key in (
                ("cpu", "required_cpu", "available_cpu"),
                ("memory", "required_memory_gib", "available_memory_gib"),
                ("storage", "required_storage_gib", "available_storage_gib"),
            ):
                required = _float(row.get(required_key))
                available = _float(row.get(available_key))
                if available and required / available >= 0.8:
                    warnings.append(f"Row {index}: target {target} {label} usage is at or above 80 percent")
    return CapacityFitValidation(len(rows), tuple(errors), tuple(warnings), tuple(rows))


def _read_move_plan(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _validate_capacity_numbers(index: int, target: dict[str, Any], errors: list[str]) -> None:
    for key in ("usable_cpu_cores", "usable_memory_gib", "usable_storage_gib"):
        if _float(target.get(key)) <= 0:
            errors.append(f"targets[{index}].{key} must be a positive number")
    for key in ("cpu_reserved_percent", "memory_reserved_percent", "storage_reserved_percent"):
        value = _float(target.get(key))
        if value < 0 or value >= 100:
            errors.append(f"targets[{index}].{key} must be between 0 and 99")
    if _float(target.get("cpu_overcommit_ratio"), default=1.0) <= 0:
        errors.append(f"targets[{index}].cpu_overcommit_ratio must be a positive number")


def _included_totals(rows: list[dict[str, str]], workloads: dict[str, dict[str, Any]]) -> dict[str, float]:
    totals = {"cpu": 0.0, "memory_gib": 0.0, "disk_gib": 0.0}
    for row in rows:
        workload = workloads.get((row.get("source_vm_id") or "").strip())
        if not workload:
            continue
        totals["cpu"] += _float(workload.get("cpu"))
        totals["memory_gib"] += _float(workload.get("memory_gib"))
        totals["disk_gib"] += _float(workload.get("disk_gib"))
    return totals


def _available(
    target: dict[str, Any],
    usable_key: str,
    reserved_key: str,
    multiplier_key: str | None = None,
) -> float:
    usable = _float(target.get(usable_key))
    reserved = _float(target.get(reserved_key))
    multiplier = _float(target.get(multiplier_key), default=1.0) if multiplier_key else 1.0
    return usable * multiplier * ((100 - reserved) / 100)


def _capacity_notes(row: dict[str, Any]) -> str:
    failed = []
    if not row["cpu_fit"]:
        failed.append("cpu")
    if not row["memory_fit"]:
        failed.append("memory")
    if not row["storage_fit"]:
        failed.append("storage")
    return "capacity fit passed" if not failed else f"capacity exceeded: {', '.join(failed)}"


def _headroom_warnings(row: dict[str, Any]) -> list[str]:
    warnings = []
    for label, required_key, available_key in (
        ("cpu", "required_cpu", "available_cpu"),
        ("memory", "required_memory_gib", "available_memory_gib"),
        ("storage", "required_storage_gib", "available_storage_gib"),
    ):
        required = _float(row[required_key])
        available = _float(row[available_key])
        if available and required / available >= 0.8 and required <= available:
            warnings.append(f"Target {row['target']} {label} usage is at or above 80 percent of planned capacity")
    return warnings


def _float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _cluster_name(cluster: dict[str, Any]) -> str:
    metadata = cluster.get("metadata") if isinstance(cluster.get("metadata"), dict) else {}
    spec = cluster.get("spec") if isinstance(cluster.get("spec"), dict) else {}
    status = cluster.get("status") if isinstance(cluster.get("status"), dict) else {}
    return str(
        status.get("name")
        or spec.get("name")
        or metadata.get("name")
        or metadata.get("uuid")
        or status.get("uuid")
        or ""
    )


def _cluster_cpu_cores(cluster: dict[str, Any]) -> float:
    return _first_number_recursive(
        cluster,
        {
            "num_cpu_cores",
            "cpu_cores",
            "num_cores",
            "total_cpu_cores",
            "logical_cpu_cores",
            "effective_cpu_cores",
        },
    )


def _cluster_memory_gib(cluster: dict[str, Any]) -> float:
    mib = _first_number_recursive(
        cluster,
        {
            "memory_capacity_mib",
            "cluster_memory_capacity_mib",
            "memory_size_mib",
            "total_memory_mib",
            "effective_memory_capacity_mib",
        },
    )
    if mib:
        return round(mib / 1024, 2)
    bytes_value = _first_number_recursive(
        cluster,
        {
            "memory_capacity_bytes",
            "cluster_memory_capacity_bytes",
            "total_memory_bytes",
        },
    )
    return round(bytes_value / (1024**3), 2) if bytes_value else 0.0


def _cluster_storage_gib(cluster: dict[str, Any]) -> float:
    bytes_value = _first_number_recursive(
        cluster,
        {
            "storage_capacity_bytes",
            "logical_storage_capacity_bytes",
            "cluster_storage_capacity_bytes",
            "total_storage_capacity_bytes",
            "total_capacity_bytes",
        },
    )
    if bytes_value:
        return round(bytes_value / (1024**3), 2)
    mib = _first_number_recursive(
        cluster,
        {
            "storage_capacity_mib",
            "logical_storage_capacity_mib",
            "cluster_storage_capacity_mib",
            "total_storage_capacity_mib",
        },
    )
    return round(mib / 1024, 2) if mib else 0.0


def _first_number_recursive(value: Any, keys: set[str]) -> float:
    if isinstance(value, dict):
        for key, nested in value.items():
            if str(key) in keys:
                number = _float(nested)
                if number:
                    return number
        for nested in value.values():
            number = _first_number_recursive(nested, keys)
            if number:
                return number
    elif isinstance(value, list):
        for nested in value:
            number = _first_number_recursive(nested, keys)
            if number:
                return number
    return 0.0
