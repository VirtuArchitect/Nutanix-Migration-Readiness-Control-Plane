from __future__ import annotations

import csv
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .dependency_hints import dependencies_from_metadata
from .guest_identity import guest_identity_from_values


def import_rvtools_directory(directory: Path, source_name: str = "rvtools-export") -> dict[str, Any]:
    rows = _read_optional_csv(directory / "vInfo.csv")
    if not rows:
        raise ValueError(f"Missing or empty RVTools vInfo.csv in {directory}")

    snapshots_by_vm = _snapshot_summary_by_vm(_read_optional_csv(directory / "vSnapshot.csv"))
    networks_by_vm = _networks_by_vm(_read_optional_csv(directory / "vNetwork.csv"))
    disk_rows = _read_optional_csv(directory / "vDisk.csv")
    disk_gib_by_vm = _disk_gib_by_vm(disk_rows)
    storage_by_vm = _storage_by_vm(disk_rows)
    observed_files = sorted(path.name for path in directory.glob("v*.csv") if path.is_file())

    workloads: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for index, row in enumerate(rows, start=1):
        name = _first_value(row, "VM", "Name")
        if not name:
            name = f"rvtools-vm-{index}"
        workload_id = _unique_id(_first_value(row, "VM UUID", "UUID", "Instance UUID", "VM") or name, seen_ids)
        annotation = _first_value(row, "Annotation", "Notes", "Description")
        tags = _annotation_tags(annotation)
        networks = networks_by_vm.get(name.lower(), [])
        disk_gib = disk_gib_by_vm.get(name.lower())
        if disk_gib is None:
            disk_gib = _mib_to_gib(_first_number(row, "Provisioned MiB", "In Use MiB", "Size MiB"))

        workloads.append(
            {
                "id": workload_id,
                "name": name,
                "owner": tags.get("owner") or "Unassigned",
                "tier": tags.get("tier") or "unknown",
                "guest_os": _first_value(
                    row,
                    "OS according to the VMware Tools",
                    "OS according to the configuration file",
                    "Guest OS",
                    "Guest OS Full Name",
                ),
                "cpu": int(_first_number(row, "CPUs", "Num CPU", "vCPUs")),
                "memory_gib": _mib_to_gib(_first_number(row, "Memory", "Memory MiB", "Memory Size MiB")),
                "disk_gib": disk_gib,
                "storage": storage_by_vm.get(name.lower(), {"disk_count": 0}),
                "power_state": _first_value(row, "Powerstate", "Power State"),
                "tags": [f"{key}:{value}" for key, value in tags.items()],
                "networking": {
                    "uses_vds": _uses_vds(networks),
                    "uses_nsx": _uses_nsx(networks, tags),
                    "vlans": _network_values(networks),
                },
                "guest_identity": guest_identity_from_values(
                    hostname=_first_value(row, "Host Name", "Hostname", "Guest Host Name"),
                    dns_name=_first_value(row, "DNS Name", "FQDN", "Guest DNS Name"),
                    ip_addresses=_first_value(row, "Primary IP Address", "IP Address", "IP Addresses", "Guest IP Address"),
                ),
                "snapshots": {
                    **snapshots_by_vm.get(
                        name.lower(),
                        {"count": int(_first_number(row, "Snapshots", "Snapshot Count"))},
                    ),
                },
                "tools": {
                    "vmware_tools": _has_vmware_tools(row),
                    "virtio_ready": tags.get("virtio_ready", "").lower() == "true",
                    "status": _tools_status(row),
                },
                "backup": {
                    "protected": tags.get("backup", "").lower() == "protected",
                    "last_success_hours": int(_parse_number(tags.get("backup_last_success_hours", "0"))),
                },
                "vendor_support": _split_csv(tags.get("vendor_support", "")),
                "dependencies": dependencies_from_metadata(tags, [annotation]),
            }
        )

    return {
        "source": {
            "system": "rvtools-csv",
            "endpoint": source_name,
            "collected_at": datetime.now(UTC).isoformat(),
            "mode": "offline-import",
            "collection_audit": {
                "schema": "nmrcp_collection_audit_v1",
                "mode": "offline-import",
                "credential_storage": "not_used",
                "endpoint_configured": False,
                "files_observed": observed_files,
                "workloads_count": len(workloads),
                "mutating_calls": 0,
            },
        },
        "workloads": workloads,
    }


def _read_optional_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return [
            {str(key).strip(): str(value).strip() for key, value in row.items() if key is not None}
            for row in csv.DictReader(handle)
        ]


def _first_value(row: dict[str, str], *keys: str) -> str:
    lookup = {key.lower(): value for key, value in row.items()}
    for key in keys:
        value = lookup.get(key.lower(), "")
        if value:
            return value
    return ""


def _first_number(row: dict[str, str], *keys: str) -> float:
    for key in keys:
        value = _first_value(row, key)
        if value:
            return _parse_number(value)
    return 0.0


def _parse_number(value: str) -> float:
    cleaned = value.replace(",", "").strip()
    if not cleaned:
        return 0.0
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _mib_to_gib(value: float) -> float:
    return round(value / 1024, 2)


def _annotation_tags(annotation: str) -> dict[str, str]:
    tags: dict[str, str] = {}
    for fragment in annotation.replace("\n", ";").split(";"):
        if ":" not in fragment:
            continue
        key, value = fragment.split(":", 1)
        key = key.strip().lower().replace("-", "_").replace(" ", "_")
        value = value.strip()
        if key and value:
            tags[key] = value
    return tags


def _split_csv(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def _unique_id(candidate: str, seen_ids: set[str]) -> str:
    base = candidate.strip() or "unknown"
    value = base
    suffix = 2
    while value in seen_ids:
        value = f"{base}-{suffix}"
        suffix += 1
    seen_ids.add(value)
    return value


def _count_by_vm(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        name = _first_value(row, "VM", "Name")
        if name:
            key = name.lower()
            counts[key] = counts.get(key, 0) + 1
    return counts


def _snapshot_summary_by_vm(rows: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    summary: dict[str, dict[str, object]] = {}
    oldest_by_vm: dict[str, datetime] = {}
    for row in rows:
        name = _first_value(row, "VM", "Name")
        if not name:
            continue
        key = name.lower()
        summary.setdefault(key, {"count": 0})
        summary[key]["count"] = int(summary[key]["count"]) + 1
        created_at = _snapshot_datetime(row)
        if created_at and (key not in oldest_by_vm or created_at < oldest_by_vm[key]):
            oldest_by_vm[key] = created_at
    for key, created_at in oldest_by_vm.items():
        summary[key]["oldest_created_at"] = created_at.isoformat()
        summary[key]["oldest_days"] = _age_days(created_at)
    return summary


def _snapshot_datetime(row: dict[str, str]) -> datetime | None:
    value = _first_value(row, "Date / Time", "Date", "Created", "Create Time", "Created Time")
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        pass
    for pattern in (
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M",
        "%m/%d/%Y",
    ):
        try:
            return datetime.strptime(value, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _age_days(value: datetime) -> int:
    return max(0, (datetime.now(UTC) - value.astimezone(UTC)).days)


def _networks_by_vm(rows: list[dict[str, str]]) -> dict[str, list[str]]:
    networks: dict[str, list[str]] = {}
    for row in rows:
        name = _first_value(row, "VM", "Name")
        network = _first_value(row, "Network", "Portgroup", "Port Group", "VLAN")
        if not name or not network:
            continue
        key = name.lower()
        networks.setdefault(key, [])
        if network not in networks[key]:
            networks[key].append(network)
    return networks


def _disk_gib_by_vm(rows: list[dict[str, str]]) -> dict[str, float]:
    totals_mib: dict[str, float] = {}
    for row in rows:
        name = _first_value(row, "VM", "Name")
        if not name:
            continue
        capacity = _first_number(row, "Capacity MiB", "Provisioned MiB", "Size MiB")
        totals_mib[name.lower()] = totals_mib.get(name.lower(), 0.0) + capacity
    return {name: _mib_to_gib(total) for name, total in totals_mib.items()}


def _storage_by_vm(rows: list[dict[str, str]]) -> dict[str, dict[str, object]]:
    storage: dict[str, dict[str, object]] = {}
    for row in rows:
        name = _first_value(row, "VM", "Name")
        if not name:
            continue
        key = name.lower()
        posture = storage.setdefault(
            key,
            {
                "disk_count": 0,
                "thin_provisioned": False,
                "raw_device_mapping": False,
                "shared_disk": False,
                "independent_disk": False,
                "encrypted": False,
                "datastores": [],
            },
        )
        posture["disk_count"] = int(posture["disk_count"]) + 1
        values = " ".join(value.lower() for value in row.values() if value)
        posture["thin_provisioned"] = bool(posture["thin_provisioned"] or _truthy_column(row, "Thin", "Thin Provisioned") or "thin" in values)
        posture["raw_device_mapping"] = bool(posture["raw_device_mapping"] or "rdm" in values or "raw device" in values)
        posture["shared_disk"] = bool(posture["shared_disk"] or _truthy_column(row, "Shared", "Multi Writer", "Multi-writer") or "multi-writer" in values)
        posture["independent_disk"] = bool(posture["independent_disk"] or "independent" in values)
        posture["encrypted"] = bool(posture["encrypted"] or _truthy_column(row, "Encrypted", "Encryption") or "encrypted" in values)
        datastores = posture["datastores"]
        datastore = _first_value(row, "Datastore", "Datastore Name", "Filename")
        if isinstance(datastores, list) and datastore and datastore not in datastores:
            datastores.append(datastore)
        free_percent = _first_number(row, "Datastore Free %", "Free %", "Free Percent")
        if free_percent:
            current = posture.get("min_datastore_free_percent")
            posture["min_datastore_free_percent"] = min(float(current), free_percent) if current is not None else free_percent
    return storage


def _truthy_column(row: dict[str, str], *keys: str) -> bool:
    value = _first_value(row, *keys).lower()
    return value in {"true", "yes", "y", "1", "enabled"}


def _uses_vds(networks: list[str]) -> bool:
    return any("dvs" in network.lower() or "distributed" in network.lower() or "vds" in network.lower() for network in networks)


def _uses_nsx(networks: list[str], tags: dict[str, str]) -> bool:
    if tags.get("nsx", "").lower() == "true":
        return True
    return any("nsx" in network.lower() or "overlay" in network.lower() for network in networks)


def _network_values(networks: list[str]) -> list[str]:
    return networks


def _has_vmware_tools(row: dict[str, str]) -> bool:
    value = _first_value(row, "Tools", "Tools Status", "VMware Tools", "Tools Version", "Tools Version Status")
    if not value:
        return bool(_first_value(row, "OS according to the VMware Tools"))
    return value.lower() not in {"not installed", "not running", "unmanaged", "unknown", "false", "no"}


def _tools_status(row: dict[str, str]) -> str:
    values = [
        _first_value(row, "Tools", "Tools Status", "VMware Tools"),
        _first_value(row, "Tools Version Status", "Tools Version Status 2", "Version Status"),
        _first_value(row, "Tools Running Status", "Tools Run Status", "Run Status"),
    ]
    return "; ".join(value for value in values if value)
