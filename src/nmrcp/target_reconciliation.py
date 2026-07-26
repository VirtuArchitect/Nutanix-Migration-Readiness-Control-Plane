from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TARGET_RECONCILIATION_SCHEMA_VERSION = "nmrcp_target_reconciliation_v1"

FIELDNAMES = [
    "schema_version",
    "source_vm_id",
    "source_vm_name",
    "move_decision",
    "target_vm_id",
    "target_vm_name",
    "match_type",
    "status",
    "notes",
]


@dataclass(frozen=True)
class TargetReconciliation:
    checked: int
    matched: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    rows: tuple[dict[str, str], ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"{status}: checked={self.checked}, matched={self.matched}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def reconcile_target_inventory(
    source_inventory_path: Path,
    target_inventory_path: Path,
    move_plan_path: Path,
) -> TargetReconciliation:
    source_inventory = json.loads(source_inventory_path.read_text(encoding="utf-8"))
    target_inventory = json.loads(target_inventory_path.read_text(encoding="utf-8"))
    move_rows = _read_move_plan(move_plan_path)
    return reconcile_target_inventory_payload(source_inventory, target_inventory, move_rows)


def reconcile_target_inventory_payload(
    source_inventory: dict[str, Any],
    target_inventory: dict[str, Any],
    move_rows: list[dict[str, str]],
) -> TargetReconciliation:
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, str]] = []
    source_workloads = {
        str(workload.get("id") or workload.get("name") or ""): workload
        for workload in source_inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    target_by_name = _target_by_name(target_inventory)

    for move_row in move_rows:
        source_id = (move_row.get("source_vm_id") or "").strip()
        source_name = (move_row.get("source_vm_name") or "").strip()
        decision = _move_decision(move_row)
        workload = source_workloads.get(source_id)
        if workload and not source_name:
            source_name = str(workload.get("name") or source_id)
        match = target_by_name.get(source_name.lower())
        if match:
            target_id = str(match.get("id") or "")
            target_name = str(match.get("name") or source_name)
            if decision == "include":
                status = "fail"
                notes = "included source workload name already exists in Prism inventory"
                errors.append(f"{source_id}: included workload name already exists in Prism inventory: {source_name}")
            else:
                status = "warn"
                notes = "held source workload name already exists in Prism inventory"
                warnings.append(f"{source_id}: held workload name already exists in Prism inventory: {source_name}")
            match_type = "name"
        else:
            target_id = ""
            target_name = ""
            match_type = "none"
            status = "pass"
            notes = "no Prism inventory name collision found"
        rows.append(
            {
                "schema_version": TARGET_RECONCILIATION_SCHEMA_VERSION,
                "source_vm_id": source_id,
                "source_vm_name": source_name,
                "move_decision": decision,
                "target_vm_id": target_id,
                "target_vm_name": target_name,
                "match_type": match_type,
                "status": status,
                "notes": notes,
            }
        )
    return TargetReconciliation(
        checked=len(rows),
        matched=sum(1 for row in rows if row["match_type"] != "none"),
        errors=tuple(errors),
        warnings=tuple(warnings),
        rows=tuple(rows),
    )


def write_target_reconciliation_csv(result: TargetReconciliation, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(result.rows)
    return path


def validate_target_reconciliation_csv(path: Path) -> TargetReconciliation:
    errors: list[str] = []
    warnings: list[str] = []
    rows: list[dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = [field for field in FIELDNAMES if field not in (reader.fieldnames or [])]
        if missing:
            return TargetReconciliation(0, 0, (f"Target reconciliation CSV missing required columns: {', '.join(missing)}",), (), ())
        for index, row in enumerate(reader, start=2):
            rows.append({field: (row.get(field) or "").strip() for field in FIELDNAMES})
            if row.get("schema_version") != TARGET_RECONCILIATION_SCHEMA_VERSION:
                errors.append(f"Row {index}: schema_version must be {TARGET_RECONCILIATION_SCHEMA_VERSION}")
            status = (row.get("status") or "").strip().lower()
            if status not in {"pass", "warn", "fail"}:
                errors.append(f"Row {index}: status must be pass, warn, or fail")
            if status == "fail":
                errors.append(f"Row {index}: target reconciliation failed for {row.get('source_vm_id')}: {row.get('notes')}")
            if status == "warn":
                warnings.append(f"Row {index}: target reconciliation warning for {row.get('source_vm_id')}: {row.get('notes')}")
    return TargetReconciliation(
        checked=len(rows),
        matched=sum(1 for row in rows if row["match_type"] != "none"),
        errors=tuple(errors),
        warnings=tuple(warnings),
        rows=tuple(rows),
    )


def _read_move_plan(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _move_decision(row: dict[str, str]) -> str:
    raw = (row.get("include_decision") or row.get("include_in_move_plan") or "").strip().lower()
    if raw in {"yes", "true", "include", "included"}:
        return "include"
    if raw in {"no", "false", "hold", "held", "exclude", "excluded"}:
        return "hold"
    return raw or "unknown"


def _target_by_name(target_inventory: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_name: dict[str, dict[str, Any]] = {}
    for workload in target_inventory.get("workloads", []):
        if not isinstance(workload, dict):
            continue
        name = str(workload.get("name") or "").strip().lower()
        if name and name not in by_name:
            by_name[name] = workload
    return by_name
