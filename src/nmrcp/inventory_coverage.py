from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


INVENTORY_COVERAGE_COLUMNS = [
    "workload_id",
    "name",
    "coverage_percent",
    "present_fields",
    "partial_fields",
    "missing_fields",
]
INVENTORY_COVERAGE_CONTEXT_SCHEMA_VERSION = "nmrcp_inventory_coverage_context_v1"
CRITICAL_INCLUDED_FIELDS = {
    "owner",
    "guest_os",
    "networking",
    "guest_identity",
    "tools",
    "backup",
    "storage",
    "application_owner_approval",
    "rollback_owner",
}


@dataclass(frozen=True)
class InventoryCoverageValidation:
    path: Path
    row_count: int
    low_coverage_count: int
    included_gap_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return (
            f"{status}: rows={self.row_count}, low_coverage={self.low_coverage_count}, "
            f"included_gaps={self.included_gap_count}, errors={len(self.errors)}, warnings={len(self.warnings)}"
        )


def validate_inventory_coverage_csv(
    coverage_path: Path,
    move_plan_path: Path | None = None,
    *,
    minimum_coverage_percent: int = 90,
) -> InventoryCoverageValidation:
    errors: list[str] = []
    warnings: list[str] = []
    low_coverage_count = 0
    included_gap_count = 0
    included_ids = included_move_plan_ids(move_plan_path, errors) if move_plan_path else set()

    with coverage_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [column for column in INVENTORY_COVERAGE_COLUMNS if column not in fieldnames]
        extra = [column for column in fieldnames if column not in INVENTORY_COVERAGE_COLUMNS]
        if missing:
            errors.append(f"Missing required columns: {', '.join(missing)}")
        if extra:
            warnings.append(f"Unexpected columns ignored by nmrcp validator: {', '.join(extra)}")
        rows = list(reader)

    if not rows:
        errors.append("inventory-coverage.csv must contain at least one workload row")

    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=2):
        workload_id = (row.get("workload_id") or "").strip()
        name = (row.get("name") or "").strip()
        if not workload_id:
            errors.append(f"Row {index}: workload_id is required")
        elif workload_id in seen_ids:
            errors.append(f"Row {index}: duplicate workload_id {workload_id!r}")
        seen_ids.add(workload_id)
        if not name:
            errors.append(f"Row {index}: name is required")

        try:
            coverage_percent = int(row.get("coverage_percent") or "")
        except ValueError:
            errors.append(f"Row {index}: coverage_percent must be an integer")
            coverage_percent = -1
        if coverage_percent < 0 or coverage_percent > 100:
            errors.append(f"Row {index}: coverage_percent must be between 0 and 100")
        elif coverage_percent < minimum_coverage_percent:
            low_coverage_count += 1
            warnings.append(f"Row {index}: coverage {coverage_percent}% is below {minimum_coverage_percent}%")

        missing_fields = field_set(row.get("missing_fields"))
        partial_fields = field_set(row.get("partial_fields"))
        if not missing_fields and not partial_fields and coverage_percent < 100:
            warnings.append(f"Row {index}: coverage below 100% but missing/partial fields are empty")

        if workload_id in included_ids:
            critical_gaps = sorted(CRITICAL_INCLUDED_FIELDS.intersection(missing_fields.union(partial_fields)))
            if critical_gaps:
                included_gap_count += 1
                errors.append(
                    f"Row {index}: included workload {workload_id} has critical inventory coverage gaps: "
                    + ", ".join(critical_gaps)
                )

    missing_coverage = sorted(included_ids.difference(seen_ids))
    for workload_id in missing_coverage:
        errors.append(f"Move plan includes workload {workload_id} but inventory coverage row is missing")

    return InventoryCoverageValidation(
        path=coverage_path,
        row_count=len(rows),
        low_coverage_count=low_coverage_count,
        included_gap_count=included_gap_count,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def included_move_plan_ids(move_plan_path: Path | None, errors: list[str]) -> set[str]:
    if not move_plan_path:
        return set()
    included: set[str] = set()
    try:
        with move_plan_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for index, row in enumerate(reader, start=2):
                if (row.get("include_in_move_plan") or "").strip().lower() != "yes":
                    continue
                workload_id = (row.get("source_vm_id") or "").strip()
                if workload_id:
                    included.add(workload_id)
                else:
                    errors.append(f"Move plan row {index}: included workload missing source_vm_id")
    except OSError as exc:
        errors.append(f"Move plan could not be read for inventory coverage validation: {exc}")
    return included


def field_set(value: str | None) -> set[str]:
    return {item.strip() for item in (value or "").split(";") if item.strip()}
