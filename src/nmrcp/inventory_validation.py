from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


REQUIRED_WORKLOAD_KEYS = {"id", "name"}


@dataclass(frozen=True)
class InventoryValidation:
    workload_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return (
            f"{status}: workloads={self.workload_count}, "
            f"errors={len(self.errors)}, warnings={len(self.warnings)}"
        )


def validate_inventory(inventory: dict[str, Any]) -> InventoryValidation:
    errors: list[str] = []
    warnings: list[str] = []
    workloads = inventory.get("workloads")
    if not isinstance(workloads, list):
        return InventoryValidation(0, ("Inventory must contain a workloads list",), ())
    if not workloads:
        errors.append("Inventory workloads list cannot be empty")

    seen_ids: set[str] = set()
    for index, workload in enumerate(workloads):
        path = f"workloads[{index}]"
        if not isinstance(workload, dict):
            errors.append(f"{path}: workload must be an object")
            continue
        missing = [key for key in sorted(REQUIRED_WORKLOAD_KEYS) if not workload.get(key)]
        if missing:
            errors.append(f"{path}: missing required keys: {', '.join(missing)}")
        workload_id = str(workload.get("id") or "")
        if workload_id:
            if workload_id in seen_ids:
                errors.append(f"{path}: duplicate workload id {workload_id!r}")
            seen_ids.add(workload_id)
        warn_if_missing(workload, "owner", path, warnings)
        warn_if_missing(workload, "guest_os", path, warnings)
        validate_nested_object(workload, "networking", path, warnings)
        validate_nested_object(workload, "snapshots", path, warnings)
        validate_nested_object(workload, "tools", path, warnings)
        validate_nested_object(workload, "backup", path, warnings)
        validate_nested_object(workload, "storage", path, warnings)
        validate_number(workload, "cpu", path, warnings)
        validate_number(workload, "memory_gib", path, warnings)
        validate_number(workload, "disk_gib", path, warnings)
        dependencies = workload.get("dependencies", [])
        if dependencies is not None and not isinstance(dependencies, list):
            warnings.append(f"{path}: dependencies should be a list")
        if isinstance(dependencies, list):
            for dep_index, dependency in enumerate(dependencies):
                if not isinstance(dependency, dict):
                    warnings.append(f"{path}.dependencies[{dep_index}]: dependency should be an object")
                    continue
                if not dependency.get("name") and not dependency.get("id"):
                    warnings.append(f"{path}.dependencies[{dep_index}]: dependency should include name or id")
    return InventoryValidation(len(workloads), tuple(errors), tuple(warnings))


def validate_inventory_file(path: Path) -> InventoryValidation:
    import json

    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return InventoryValidation(0, ("Inventory file must contain a JSON object",), ())
    return validate_inventory(payload)


def warn_if_missing(workload: dict[str, Any], key: str, path: str, warnings: list[str]) -> None:
    if workload.get(key) in {None, "", "unknown", "Unassigned"}:
        warnings.append(f"{path}: {key} is missing or unknown")


def validate_nested_object(workload: dict[str, Any], key: str, path: str, warnings: list[str]) -> None:
    value = workload.get(key)
    if not isinstance(value, dict):
        warnings.append(f"{path}: {key} should be an object")


def validate_number(workload: dict[str, Any], key: str, path: str, warnings: list[str]) -> None:
    value = workload.get(key)
    if value is None:
        warnings.append(f"{path}: {key} is missing")
        return
    if not isinstance(value, (int, float)) or value < 0:
        warnings.append(f"{path}: {key} should be a non-negative number")
