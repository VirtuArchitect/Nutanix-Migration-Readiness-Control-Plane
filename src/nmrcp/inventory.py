from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .dependency_hints import dependencies_from_metadata
from .guest_identity import guest_identity_from_values


def normalized_source(system: str, endpoint: str) -> dict[str, Any]:
    return {
        "system": system,
        "endpoint": endpoint,
        "collected_at": datetime.now(UTC).isoformat(),
        "mode": "read-only",
    }


def normalize_vcenter_inventory(
    endpoint: str,
    vm_summaries: list[dict[str, Any]],
    details_by_vm: dict[str, dict[str, Any]] | None = None,
    details_limit: int | None = None,
    network_count: int | None = None,
) -> dict[str, Any]:
    details_by_vm = details_by_vm or {}
    workloads = []
    for vm in vm_summaries:
        vm_id = str(vm.get("vm") or vm.get("id") or vm.get("name") or "unknown")
        details = details_by_vm.get(vm_id, {})
        nics = details.get("nics") or []
        disks = details.get("disks") or []
        guest_os = details.get("guest_OS") or vm.get("guest_OS") or vm.get("guest_os") or ""
        cpu = details.get("cpu", {}).get("count") if isinstance(details.get("cpu"), dict) else vm.get("cpu_count")
        memory_mib = (
            details.get("memory", {}).get("size_MiB")
            if isinstance(details.get("memory"), dict)
            else vm.get("memory_size_MiB")
        )
        tools = _vcenter_tools_summary(vm, details)
        identity = details.get("identity") if isinstance(details.get("identity"), dict) else {}
        workloads.append(
            {
                "id": vm_id,
                "name": str(vm.get("name") or details.get("name") or vm_id),
                "owner": _tag_value(vm.get("tags") or [], "owner") or "Unassigned",
                "tier": _tag_value(vm.get("tags") or [], "tier") or "unknown",
                "guest_os": str(guest_os),
                "cpu": int(cpu or 0),
                "memory_gib": round(int(memory_mib or 0) / 1024, 2),
                "disk_gib": _sum_vcenter_disk_gib(disks),
                "storage": _vcenter_storage_posture(disks),
                "power_state": vm.get("power_state") or details.get("power_state"),
                "tags": _normalize_tags(vm.get("tags") or []),
                "networking": {
                    "uses_vds": _vcenter_uses_vds(nics),
                    "uses_nsx": _vcenter_uses_nsx(nics, vm.get("tags") or []),
                    "vlans": _vcenter_vlans(nics),
                },
                "guest_identity": guest_identity_from_values(
                    hostname=details.get("host_name") or vm.get("host_name") or identity.get("host_name"),
                    dns_name=details.get("dns_name") or vm.get("dns_name") or identity.get("dns_name"),
                    ip_addresses=details.get("ip_addresses") or vm.get("ip_addresses") or identity.get("ip_addresses") or details.get("ip_address") or vm.get("ip_address"),
                ),
                "snapshots": {
                    **_vcenter_snapshot_summary(vm, details),
                },
                "tools": tools,
                "backup": {
                    "protected": _tag_value(vm.get("tags") or [], "backup") == "protected",
                    "last_success_hours": _int_tag(vm.get("tags") or [], "backup_last_success_hours"),
                },
                "vendor_support": _csv_tag(vm.get("tags") or [], "vendor_support"),
                "dependencies": dependencies_from_metadata(
                    vm.get("tags") or [],
                    [
                        vm.get("annotation"),
                        vm.get("notes"),
                        vm.get("description"),
                        details.get("annotation"),
                        details.get("notes"),
                        details.get("description"),
                    ],
                ),
            }
        )
    api_paths = ["/api/session", "/api/vcenter/vm", "/api/vcenter/vm/{vm}"]
    if network_count is not None:
        api_paths.append("/api/vcenter/network")
    audit = {
        "schema": "nmrcp_collection_audit_v1",
        "mode": "read-only",
        "credential_storage": "not_persisted",
        "endpoint_configured": bool(endpoint),
        "api_paths": api_paths,
        "summary_count": len(vm_summaries),
        "details_limit": details_limit if details_limit is not None else len(details_by_vm),
        "details_count": len(details_by_vm),
        "mutating_calls": 0,
    }
    if network_count is not None:
        audit["network_count"] = network_count
    source = normalized_source("vcenter-rest", endpoint)
    source["collection_audit"] = audit
    return {"source": source, "workloads": workloads}


def normalize_prism_inventory(
    endpoint: str,
    entities: list[dict[str, Any]],
    page_size: int | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    workloads = []
    for entity in entities:
        metadata = entity.get("metadata") or {}
        spec = entity.get("spec") or {}
        resources = spec.get("resources") or {}
        status = entity.get("status") or {}
        status_resources = status.get("resources") or {}
        workload_id = str(metadata.get("uuid") or status.get("uuid") or spec.get("uuid") or spec.get("name") or "unknown")
        memory_mib = resources.get("memory_size_mib") or status_resources.get("memory_size_mib") or 0
        disks = resources.get("disk_list") or status_resources.get("disk_list") or []
        nics = resources.get("nic_list") or status_resources.get("nic_list") or []
        categories = metadata.get("categories") if isinstance(metadata.get("categories"), dict) else {}
        description = (
            metadata.get("description")
            or spec.get("description")
            or resources.get("description")
            or status.get("description")
            or status_resources.get("description")
        )
        guest_tools = status_resources.get("guest_tools") if isinstance(status_resources.get("guest_tools"), dict) else {}
        workloads.append(
            {
                "id": workload_id,
                "name": str(spec.get("name") or status.get("name") or workload_id),
                "owner": str(categories.get("Owner") or categories.get("owner") or "Unassigned"),
                "tier": str(categories.get("Tier") or categories.get("tier") or "unknown").lower(),
                "guest_os": str(resources.get("guest_os") or status_resources.get("guest_os") or ""),
                "cpu": _prism_cpu(resources or status_resources),
                "memory_gib": round(int(memory_mib or 0) / 1024, 2),
                "disk_gib": _sum_prism_disk_gib(disks),
                "storage": _prism_storage_posture(disks),
                "power_state": resources.get("power_state") or status_resources.get("power_state"),
                "tags": [f"{key}:{value}" for key, value in categories.items()],
                "networking": {
                    "uses_vds": False,
                    "uses_nsx": False,
                    "vlans": _prism_vlans(nics),
                },
                "guest_identity": guest_identity_from_values(
                    hostname=resources.get("hostname") or status_resources.get("hostname") or guest_tools.get("host_name"),
                    dns_name=resources.get("dns_name") or status_resources.get("dns_name") or guest_tools.get("dns_name"),
                    ip_addresses=resources.get("ip_addresses") or status_resources.get("ip_addresses") or guest_tools.get("ip_addresses") or guest_tools.get("ip_address"),
                ),
                "snapshots": {
                    "count": int(resources.get("snapshot_count") or status_resources.get("snapshot_count") or 0),
                },
                "tools": {
                    "vmware_tools": False,
                    "virtio_ready": True,
                    "status": "",
                },
                "backup": {
                    "protected": str(categories.get("Backup") or categories.get("backup") or "").lower() == "protected",
                    "last_success_hours": _safe_int(categories.get("BackupLastSuccessHours") or categories.get("backup_last_success_hours")),
                },
                "vendor_support": _split_csv(str(categories.get("VendorSupport") or categories.get("vendor_support") or "ahv,nc2")),
                "dependencies": dependencies_from_metadata(categories, [description]),
            }
        )
    source = normalized_source("prism-central-v3", endpoint)
    source["collection_audit"] = {
        "schema": "nmrcp_collection_audit_v1",
        "mode": "read-only",
        "credential_storage": "not_persisted",
        "endpoint_configured": bool(endpoint),
        "api_paths": ["/api/nutanix/v3/vms/list"],
        "page_size": page_size,
        "max_pages": max_pages,
        "entities_count": len(entities),
        "post_paths_allowlisted": True,
        "mutating_calls": 0,
    }
    return {"source": source, "workloads": workloads}


def _normalize_tags(tags: list[Any]) -> list[str]:
    normalized: list[str] = []
    for tag in tags:
        if isinstance(tag, str):
            normalized.append(tag)
        elif isinstance(tag, dict):
            key = tag.get("key") or tag.get("category") or tag.get("name")
            value = tag.get("value")
            normalized.append(f"{key}:{value}" if value is not None else str(key))
    return [item for item in normalized if item and item != "None"]


def _tag_value(tags: list[Any], key: str) -> str | None:
    key_lower = key.lower()
    for tag in tags:
        if isinstance(tag, str) and ":" in tag:
            tag_key, value = tag.split(":", 1)
            if tag_key.lower() == key_lower:
                return value.lower()
        if isinstance(tag, dict):
            tag_key = str(tag.get("key") or tag.get("category") or tag.get("name") or "").lower()
            if tag_key == key_lower:
                value = tag.get("value")
                return str(value).lower() if value is not None else None
    return None


def _csv_tag(tags: list[Any], key: str) -> list[str]:
    value = _tag_value(tags, key)
    return _split_csv(value or "")


def _int_tag(tags: list[Any], key: str) -> int:
    return _safe_int(_tag_value(tags, key))


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _split_csv(value: str) -> list[str]:
    return [item.strip().lower() for item in value.split(",") if item.strip()]


def _sum_vcenter_disk_gib(disks: list[Any]) -> float:
    total_mib = 0
    for disk in disks:
        if isinstance(disk, dict):
            total_mib += int(disk.get("capacity") or disk.get("capacity_MiB") or 0)
    return round(total_mib / 1024, 2)


def _vcenter_snapshot_summary(vm: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    snapshots = details.get("snapshots") or details.get("snapshot_list") or vm.get("snapshots") or vm.get("snapshot_list")
    count = int(details.get("snapshot_count") or vm.get("snapshot_count") or 0)
    oldest_days = _safe_int(details.get("snapshot_oldest_days") or vm.get("snapshot_oldest_days"))
    oldest_created_at = str(details.get("snapshot_oldest_created_at") or vm.get("snapshot_oldest_created_at") or "")
    if isinstance(snapshots, list):
        count = count or len(snapshots)
        oldest = _oldest_snapshot_datetime(snapshots)
        if oldest:
            oldest_days = _age_days(oldest)
            oldest_created_at = oldest.isoformat()
    result: dict[str, Any] = {"count": count}
    if oldest_days:
        result["oldest_days"] = oldest_days
    if oldest_created_at:
        result["oldest_created_at"] = oldest_created_at
    return result


def _vcenter_tools_summary(vm: dict[str, Any], details: dict[str, Any]) -> dict[str, Any]:
    tools = details.get("tools") if isinstance(details.get("tools"), dict) else {}
    values = [
        details.get("tools_status"),
        details.get("tools_version_status"),
        details.get("tools_run_status"),
        vm.get("tools_status"),
        vm.get("tools_version_status"),
        vm.get("tools_run_status"),
        tools.get("status"),
        tools.get("version_status"),
        tools.get("run_state"),
        tools.get("install_type"),
    ]
    status = "; ".join(str(value) for value in values if value not in {None, ""})
    status_lower = status.lower()
    explicit_missing = any(
        marker in status_lower
        for marker in (
            "not installed",
            "notinstalled",
            "not running",
            "notrunning",
            "unmanaged",
            "guesttoolsnotinstalled",
            "guesttoolsnotrunning",
        )
    )
    explicit_present = any(
        marker in status_lower
        for marker in (
            "toolsok",
            "guesttoolscurrent",
            "guesttoolsneedupgrade",
            "old",
            "outdated",
            "unsupported",
            "running",
        )
    )
    return {
        "vmware_tools": False
        if explicit_missing
        else bool(explicit_present or details.get("identity") or details.get("guest_OS") or vm.get("guest_OS")),
        "virtio_ready": bool(_tag_value(vm.get("tags") or [], "virtio_ready") == "true"),
        "status": status,
    }


def _oldest_snapshot_datetime(snapshots: list[Any]) -> datetime | None:
    oldest: datetime | None = None
    for snapshot in snapshots:
        if not isinstance(snapshot, dict):
            continue
        created_at = _datetime_value(
            snapshot.get("create_time")
            or snapshot.get("created_at")
            or snapshot.get("created")
            or snapshot.get("date_time")
            or snapshot.get("Date / Time")
        )
        if created_at and (oldest is None or created_at < oldest):
            oldest = created_at
    return oldest


def _datetime_value(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
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
            return datetime.strptime(text, pattern).replace(tzinfo=UTC)
        except ValueError:
            continue
    return None


def _age_days(value: datetime) -> int:
    return max(0, (datetime.now(UTC) - value.astimezone(UTC)).days)


def _vcenter_storage_posture(disks: list[Any]) -> dict[str, Any]:
    datastore_names: list[str] = []
    free_percents: list[float] = []
    storage = {
        "disk_count": len([disk for disk in disks if isinstance(disk, dict)]),
        "thin_provisioned": False,
        "raw_device_mapping": False,
        "shared_disk": False,
        "independent_disk": False,
        "encrypted": False,
        "datastores": datastore_names,
    }
    for disk in disks:
        if not isinstance(disk, dict):
            continue
        values = [str(value).lower() for value in disk.values() if value is not None]
        joined = " ".join(values)
        storage["thin_provisioned"] = bool(storage["thin_provisioned"] or disk.get("thin_provisioned") is True or "thin" in joined)
        storage["raw_device_mapping"] = bool(storage["raw_device_mapping"] or "rdm" in joined or "raw" in joined)
        storage["shared_disk"] = bool(storage["shared_disk"] or disk.get("shared") is True or "multi-writer" in joined or "shared" in joined)
        storage["independent_disk"] = bool(storage["independent_disk"] or "independent" in joined)
        storage["encrypted"] = bool(storage["encrypted"] or disk.get("encrypted") is True or "encrypted" in joined)
        datastore = disk.get("datastore") or disk.get("datastore_name")
        if datastore and str(datastore) not in datastore_names:
            datastore_names.append(str(datastore))
        free_percent = _float_value(disk.get("datastore_free_percent") or disk.get("free_percent"))
        if free_percent is not None:
            free_percents.append(free_percent)
    if free_percents:
        storage["min_datastore_free_percent"] = min(free_percents)
    return storage


def _sum_prism_disk_gib(disks: list[Any]) -> float:
    total_bytes = 0
    for disk in disks:
        if not isinstance(disk, dict):
            continue
        size = disk.get("disk_size_bytes")
        if size is None:
            size = (disk.get("data_source_reference") or {}).get("disk_size_bytes")
        total_bytes += int(size or 0)
    return round(total_bytes / (1024**3), 2)


def _prism_storage_posture(disks: list[Any]) -> dict[str, Any]:
    storage_container_names: list[str] = []
    for disk in disks:
        if not isinstance(disk, dict):
            continue
        container = disk.get("storage_container_reference") or (disk.get("data_source_reference") or {}).get("storage_container_reference") or {}
        if isinstance(container, dict) and container.get("name"):
            name = str(container["name"])
            if name not in storage_container_names:
                storage_container_names.append(name)
    return {
        "disk_count": len([disk for disk in disks if isinstance(disk, dict)]),
        "thin_provisioned": True,
        "raw_device_mapping": False,
        "shared_disk": False,
        "independent_disk": False,
        "encrypted": False,
        "storage_containers": storage_container_names,
    }


def _float_value(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _vcenter_uses_vds(nics: list[Any]) -> bool:
    return any(
        isinstance(nic, dict)
        and any("distributed" in str(value).lower() or "vds" in str(value).lower() for value in nic.values())
        for nic in nics
    )


def _vcenter_uses_nsx(nics: list[Any], tags: list[Any]) -> bool:
    if _tag_value(tags, "nsx") == "true":
        return True
    return any(
        isinstance(nic, dict)
        and any("nsx" in str(value).lower() or "overlay" in str(value).lower() for value in nic.values())
        for nic in nics
    )


def _vcenter_vlans(nics: list[Any]) -> list[str]:
    vlans = []
    for nic in nics:
        if isinstance(nic, dict) and nic.get("vlan") is not None:
            vlans.append(str(nic["vlan"]))
    return vlans


def _prism_cpu(resources: dict[str, Any]) -> int:
    sockets = int(resources.get("num_sockets") or 0)
    per_socket = int(resources.get("num_vcpus_per_socket") or 0)
    return sockets * per_socket if sockets and per_socket else int(resources.get("num_vcpus") or 0)


def _prism_vlans(nics: list[Any]) -> list[str]:
    vlans = []
    for nic in nics:
        if not isinstance(nic, dict):
            continue
        subnet = nic.get("subnet_reference") or {}
        if subnet.get("name"):
            vlans.append(str(subnet["name"]))
    return vlans
