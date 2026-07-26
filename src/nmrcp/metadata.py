from __future__ import annotations

import csv
from pathlib import Path
from typing import Any


METADATA_FIELD_ORDER = (
    "source_id",
    "source_name",
    "owner",
    "tier",
    "tags",
    "backup_protected",
    "backup_last_success_hours",
    "vendor_support",
    "virtio_ready",
    "application_owner_approved",
    "rollback_owner",
    "notes",
)

METADATA_FIELDS = {
    *METADATA_FIELD_ORDER,
}

SECRET_OR_ENDPOINT_MARKERS = (
    "password=",
    "passwd=",
    "secret=",
    "token=",
    "apikey=",
    "api_key=",
    "bearer ",
    "http://",
    "https://",
)

CMDB_COLUMN_ALIASES = {
    "source_id": ("source_id", "vm_id", "vm_uuid", "uuid", "instance_id", "ci_id", "configuration_item_id"),
    "source_name": ("source_name", "vm_name", "name", "hostname", "server_name", "ci_name", "configuration_item"),
    "owner": ("owner", "application_owner", "app_owner", "service_owner", "business_owner", "support_group"),
    "tier": ("tier", "criticality", "business_criticality", "business_tier", "service_tier"),
    "tags": ("tags", "tag", "labels", "environment", "application", "application_name", "service", "service_name"),
    "backup_protected": ("backup_protected", "backup_status", "backup", "protected_by_backup", "backup_required"),
    "backup_last_success_hours": (
        "backup_last_success_hours",
        "backup_age_hours",
        "last_backup_age_hours",
        "hours_since_backup",
    ),
    "vendor_support": ("vendor_support", "target_support", "supported_targets", "nutanix_support"),
    "virtio_ready": ("virtio_ready", "drivers_ready", "nutanix_guest_tools_ready", "ngt_ready"),
    "application_owner_approved": (
        "application_owner_approved",
        "owner_approved",
        "app_owner_approved",
        "migration_approved",
        "change_approved",
    ),
    "rollback_owner": ("rollback_owner", "recovery_owner", "dr_owner", "rollback_group"),
    "notes": ("notes", "comments", "comment", "migration_notes", "assessment_notes"),
}


def read_metadata_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not {"source_id", "source_name"} & set(reader.fieldnames or []):
            raise ValueError("Metadata CSV must include source_id or source_name")
        return [
            {key: (value or "").strip() for key, value in row.items() if key in METADATA_FIELDS}
            for row in reader
        ]


def write_metadata_csv(records: list[dict[str, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=METADATA_FIELD_ORDER)
        writer.writeheader()
        for record in records:
            writer.writerow({field: record.get(field, "") for field in METADATA_FIELD_ORDER})


def import_cmdb_metadata_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = tuple(reader.fieldnames or ())
        if not fieldnames:
            raise ValueError("CMDB metadata CSV must include a header row")
        normalized_lookup = {normalize_header(field): field for field in fieldnames}
        if not any(alias in normalized_lookup for alias in CMDB_COLUMN_ALIASES["source_id"]) and not any(
            alias in normalized_lookup for alias in CMDB_COLUMN_ALIASES["source_name"]
        ):
            raise ValueError("CMDB metadata CSV must include a workload identifier such as source_id, vm_id, uuid, source_name, vm_name, or hostname")

        records: list[dict[str, str]] = []
        for line_number, row in enumerate(reader, start=2):
            sanitized = sanitize_cmdb_row(row, path, line_number)
            record = map_cmdb_row(sanitized, normalized_lookup)
            if record.get("source_id") or record.get("source_name"):
                records.append(record)
        return records


def sanitize_cmdb_row(row: dict[str, str], path: Path, line_number: int) -> dict[str, str]:
    sanitized: dict[str, str] = {}
    for key, value in row.items():
        clean_value = (value or "").strip()
        lowered = clean_value.lower()
        if any(marker in lowered for marker in SECRET_OR_ENDPOINT_MARKERS):
            raise ValueError(f"{path}: row {line_number} column {key} contains a secret-like or endpoint-like value")
        sanitized[key] = clean_value
    return sanitized


def map_cmdb_row(row: dict[str, str], normalized_lookup: dict[str, str]) -> dict[str, str]:
    record = {field: "" for field in METADATA_FIELD_ORDER}
    for target, aliases in CMDB_COLUMN_ALIASES.items():
        values = [row[normalized_lookup[alias]] for alias in aliases if alias in normalized_lookup and row.get(normalized_lookup[alias])]
        if not values:
            continue
        if target == "tags":
            record[target] = merge_tags(values)
        elif target == "tier":
            record[target] = normalize_tier(values[0])
        elif target == "backup_protected":
            record[target] = normalize_bool_text(values[0], protected_words={"protected", "backed_up", "yes", "true", "required"})
        elif target == "vendor_support":
            record[target] = normalize_vendor_support(values)
        elif target in {"virtio_ready", "application_owner_approved"}:
            record[target] = normalize_bool_text(values[0])
        else:
            record[target] = values[0]
    return record


def normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_").replace("-", "_")


def normalize_tier(value: str) -> str:
    lowered = value.strip().lower()
    if lowered in {"critical", "tier_0", "tier_1", "tier 0", "tier 1", "high", "mission_critical", "mission critical"}:
        return "critical"
    if lowered in {"noncritical", "non_critical", "low", "tier_3", "tier 3", "dev", "test"}:
        return "noncritical"
    return value.strip()


def normalize_bool_text(value: str, protected_words: set[str] | None = None) -> str:
    lowered = value.strip().lower()
    yes_values = {"1", "true", "yes", "y", "approved", "ready", *(protected_words or set())}
    no_values = {"0", "false", "no", "n", "not approved", "not_ready", "not ready", "unprotected"}
    if lowered in yes_values:
        return "true"
    if lowered in no_values:
        return "false"
    return value.strip()


def normalize_vendor_support(values: list[str]) -> str:
    supported: list[str] = []
    for value in values:
        lowered = value.lower()
        if "ahv" in lowered:
            supported.append("ahv")
        if "nc2" in lowered:
            supported.append("nc2")
    return ",".join(sorted(set(supported))) if supported else values[0]


def merge_tags(values: list[str]) -> str:
    tags: list[str] = []
    for value in values:
        tags.extend(split_list(value))
    return ";".join(dict.fromkeys(tags))


def merge_metadata(inventory: dict[str, Any], records: list[dict[str, str]]) -> dict[str, Any]:
    workloads = inventory.get("workloads")
    if not isinstance(workloads, list):
        raise ValueError("Inventory must contain a workloads list")

    by_id = {str(workload.get("id")): workload for workload in workloads if isinstance(workload, dict)}
    by_name = {str(workload.get("name")): workload for workload in workloads if isinstance(workload, dict)}
    unmatched: list[dict[str, str]] = []

    for record in records:
        workload = by_id.get(record.get("source_id", "")) or by_name.get(record.get("source_name", ""))
        if workload is None:
            unmatched.append(record)
            continue
        apply_metadata_record(workload, record)

    source = inventory.setdefault("source", {})
    if isinstance(source, dict):
        source["metadata_records"] = len(records)
        source["metadata_unmatched_records"] = len(unmatched)
    inventory["unmatched_metadata"] = unmatched
    return inventory


def apply_metadata_record(workload: dict[str, Any], record: dict[str, str]) -> None:
    for key in ("owner", "tier"):
        if record.get(key):
            workload[key] = record[key]

    tags = split_list(record.get("tags", ""))
    if tags:
        existing_tags = workload.get("tags") if isinstance(workload.get("tags"), list) else []
        workload["tags"] = sorted({str(item) for item in existing_tags if item} | set(tags))

    vendor_support = split_list(record.get("vendor_support", ""))
    if vendor_support:
        workload["vendor_support"] = [item.lower() for item in vendor_support]

    backup = workload.get("backup") if isinstance(workload.get("backup"), dict) else {}
    if record.get("backup_protected"):
        backup["protected"] = truthy(record["backup_protected"])
    if record.get("backup_last_success_hours"):
        backup["last_success_hours"] = safe_int(record["backup_last_success_hours"])
    if backup:
        workload["backup"] = backup

    tools = workload.get("tools") if isinstance(workload.get("tools"), dict) else {}
    if record.get("virtio_ready"):
        tools["virtio_ready"] = truthy(record["virtio_ready"])
    if tools:
        workload["tools"] = tools

    governance = workload.get("governance") if isinstance(workload.get("governance"), dict) else {}
    if "application_owner_approved" in record:
        governance["application_owner_approved"] = truthy(record.get("application_owner_approved", ""))
    if "rollback_owner" in record:
        governance["rollback_owner"] = record.get("rollback_owner", "")
    if governance:
        workload["governance"] = governance

    notes = record.get("notes")
    if notes:
        workload["metadata_notes"] = notes


def split_list(value: str) -> list[str]:
    return [item.strip() for item in value.replace(";", ",").split(",") if item.strip()]


def truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "y", "protected"}


def safe_int(value: str) -> int:
    try:
        return int(value)
    except ValueError:
        return 0
