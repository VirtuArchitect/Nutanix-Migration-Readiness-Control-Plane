from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


VALIDATION_RESULTS_SCHEMA_VERSION = "nmrcp_validation_results_v1"
VALIDATION_COLUMNS = [
    "schema_version",
    "source_vm_id",
    "source_vm_name",
    "phase",
    "check_name",
    "status",
    "evidence_ref",
    "validated_by",
    "validated_at",
    "notes",
]
ALLOWED_PHASES = {"pre", "post"}
ALLOWED_STATUSES = {"pass", "fail", "not_checked", "na"}
DEFAULT_CHECKS = {
    "pre": [
        "owner_approval",
        "backup_restore_point",
        "snapshot_removed_or_approved",
        "network_mapping_approved",
        "rollback_owner_confirmed",
    ],
    "post": [
        "power_state",
        "ip_dns_connectivity",
        "tools_driver_state",
        "application_health",
        "target_backup_policy",
        "monitoring_logging",
    ],
}


@dataclass(frozen=True)
class ValidationResultsValidation:
    path: Path
    row_count: int
    pass_count: int
    fail_count: int
    open_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return (
            f"{status}: rows={self.row_count}, passed={self.pass_count}, failed={self.fail_count}, "
            f"open={self.open_count}, errors={len(self.errors)}, warnings={len(self.warnings)}"
        )


def write_validation_template(move_plan_path: Path, out_path: Path) -> Path:
    workloads = included_move_plan_workloads(move_plan_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=VALIDATION_COLUMNS)
        writer.writeheader()
        for workload in workloads:
            for phase, checks in DEFAULT_CHECKS.items():
                for check in checks:
                    writer.writerow(
                        {
                            "schema_version": VALIDATION_RESULTS_SCHEMA_VERSION,
                            "source_vm_id": workload["source_vm_id"],
                            "source_vm_name": workload["source_vm_name"],
                            "phase": phase,
                            "check_name": check,
                            "status": "not_checked",
                            "evidence_ref": "",
                            "validated_by": "",
                            "validated_at": "",
                            "notes": "",
                        }
                    )
    return out_path


def included_move_plan_workloads(move_plan_path: Path) -> list[dict[str, str]]:
    with move_plan_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            if (row.get("include_in_move_plan") or "").strip().lower() == "yes":
                rows.append(
                    {
                        "source_vm_id": (row.get("source_vm_id") or "").strip(),
                        "source_vm_name": (row.get("source_vm_name") or "").strip(),
                    }
                )
        return rows


def validate_validation_results(path: Path, allow_open: bool = False) -> ValidationResultsValidation:
    errors: list[str] = []
    warnings: list[str] = []
    pass_count = 0
    fail_count = 0
    open_count = 0

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing = [column for column in VALIDATION_COLUMNS if column not in fieldnames]
        extra = [column for column in fieldnames if column not in VALIDATION_COLUMNS]
        if missing:
            errors.append(f"Missing required columns: {', '.join(missing)}")
        if extra:
            warnings.append(f"Unexpected columns ignored by nmrcp validator: {', '.join(extra)}")
        rows = list(reader)

    seen: set[tuple[str, str, str]] = set()
    for index, row in enumerate(rows, start=2):
        source_vm_id = (row.get("source_vm_id") or "").strip()
        source_vm_name = (row.get("source_vm_name") or "").strip()
        phase = (row.get("phase") or "").strip().lower()
        check_name = (row.get("check_name") or "").strip()
        status = (row.get("status") or "").strip().lower()
        schema_version = (row.get("schema_version") or "").strip()
        notes = (row.get("notes") or "").strip()
        evidence_ref = (row.get("evidence_ref") or "").strip()

        if schema_version != VALIDATION_RESULTS_SCHEMA_VERSION:
            errors.append(f"Row {index}: unsupported schema_version {schema_version!r}")
        if not source_vm_id:
            errors.append(f"Row {index}: source_vm_id is required")
        if not source_vm_name:
            errors.append(f"Row {index}: source_vm_name is required")
        if phase not in ALLOWED_PHASES:
            errors.append(f"Row {index}: phase must be one of {', '.join(sorted(ALLOWED_PHASES))}")
        if not check_name:
            errors.append(f"Row {index}: check_name is required")
        if status not in ALLOWED_STATUSES:
            errors.append(f"Row {index}: status must be one of {', '.join(sorted(ALLOWED_STATUSES))}")
        key = (source_vm_id, phase, check_name)
        if key in seen:
            errors.append(f"Row {index}: duplicate validation check {source_vm_id}/{phase}/{check_name}")
        seen.add(key)

        if status == "pass":
            pass_count += 1
            if not evidence_ref:
                warnings.append(f"Row {index}: passed check should include evidence_ref")
        elif status == "fail":
            fail_count += 1
            if not notes:
                errors.append(f"Row {index}: failed check must include notes")
            if not allow_open:
                errors.append(f"Row {index}: failed check blocks validation results approval")
        elif status == "not_checked":
            open_count += 1
            if not allow_open:
                errors.append(f"Row {index}: not_checked blocks validation results approval")

    if not rows:
        errors.append("Validation results cannot be empty")

    return ValidationResultsValidation(
        path=path,
        row_count=len(rows),
        pass_count=pass_count,
        fail_count=fail_count,
        open_count=open_count,
        errors=tuple(errors),
        warnings=tuple(warnings),
    )
