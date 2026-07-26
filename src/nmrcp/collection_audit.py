from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


COLLECTION_AUDIT_SCHEMA = "nmrcp_collection_audit_v1"
ALLOWED_CREDENTIAL_STORAGE = {"not_persisted", "not_used"}
SENSITIVE_AUDIT_KEYS = {
    "api_key",
    "authorization",
    "endpoint",
    "host",
    "hostname",
    "password",
    "secret",
    "server",
    "token",
    "url",
    "username",
}

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")


@dataclass(frozen=True)
class CollectionAuditValidation:
    collector: str
    workload_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return (
            f"{status}: collector={self.collector}, workloads={self.workload_count}, "
            f"errors={len(self.errors)}, warnings={len(self.warnings)}"
        )


def validate_collection_audit_file(path: Path) -> CollectionAuditValidation:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return CollectionAuditValidation("unknown", 0, ("Inventory file must contain a JSON object",), ())
    return validate_collection_audit(payload)


def validate_collection_audit(inventory: dict[str, Any]) -> CollectionAuditValidation:
    errors: list[str] = []
    warnings: list[str] = []
    workloads = inventory.get("workloads")
    workload_count = len(workloads) if isinstance(workloads, list) else 0
    source = inventory.get("source")
    if not isinstance(source, dict):
        return CollectionAuditValidation("unknown", workload_count, ("Inventory source must be an object",), ())
    collector = str(source.get("system") or "unknown")
    audit = source.get("collection_audit")
    if not isinstance(audit, dict):
        return CollectionAuditValidation(collector, workload_count, ("source.collection_audit must be an object",), ())

    if audit.get("schema") != COLLECTION_AUDIT_SCHEMA:
        errors.append(f"source.collection_audit.schema must be {COLLECTION_AUDIT_SCHEMA}")
    if audit.get("mutating_calls") != 0:
        errors.append("source.collection_audit.mutating_calls must be 0")
    if audit.get("credential_storage") not in ALLOWED_CREDENTIAL_STORAGE:
        errors.append("source.collection_audit.credential_storage must be not_persisted or not_used")

    _validate_sensitive_content(audit, source, errors)
    _validate_collector_contract(audit, collector, workload_count, errors, warnings)
    return CollectionAuditValidation(collector, workload_count, tuple(errors), tuple(warnings))


def _validate_sensitive_content(audit: dict[str, Any], source: dict[str, Any], errors: list[str]) -> None:
    for path, key, value in _walk_audit(audit):
        if key.lower() in SENSITIVE_AUDIT_KEYS:
            errors.append(f"{path}: sensitive audit key {key!r} is not allowed")
        if isinstance(value, str):
            _validate_sensitive_string(path, value, errors)

    audit_text = json.dumps(audit, sort_keys=True)
    endpoint = str(source.get("endpoint") or "")
    if endpoint and endpoint in audit_text:
        errors.append("source.collection_audit must not duplicate source.endpoint")
    hostname = _hostname_from_endpoint(endpoint)
    if hostname and hostname in audit_text:
        errors.append("source.collection_audit must not duplicate the source endpoint hostname")


def _validate_sensitive_string(path: str, value: str, errors: list[str]) -> None:
    if "://" in value:
        errors.append(f"{path}: audit values must not contain URLs")
    if EMAIL_RE.search(value):
        errors.append(f"{path}: audit values must not contain email addresses or usernames")
    if IPV4_RE.search(value):
        errors.append(f"{path}: audit values must not contain IP addresses")


def _validate_collector_contract(
    audit: dict[str, Any],
    collector: str,
    workload_count: int,
    errors: list[str],
    warnings: list[str],
) -> None:
    api_paths = audit.get("api_paths")
    if isinstance(api_paths, list):
        for index, path in enumerate(api_paths):
            if not isinstance(path, str) or not path.startswith("/api/"):
                errors.append(f"source.collection_audit.api_paths[{index}] must be an API path")

    if _looks_like_vcenter(audit, collector):
        _validate_vcenter_contract(audit, workload_count, errors)
        return
    if _looks_like_prism(audit, collector):
        _validate_prism_contract(audit, workload_count, errors)
        return
    if collector == "rvtools-csv" or audit.get("mode") == "offline-import":
        _validate_rvtools_contract(audit, workload_count, errors)
        return
    warnings.append(f"unknown collection_audit collector contract for {collector}")


def _validate_vcenter_contract(audit: dict[str, Any], workload_count: int, errors: list[str]) -> None:
    required_paths = {"/api/session", "/api/vcenter/vm", "/api/vcenter/vm/{vm}"}
    paths = set(audit.get("api_paths") or [])
    missing = sorted(required_paths - paths)
    if missing:
        errors.append(f"vCenter audit missing API paths: {', '.join(missing)}")
    if "/api/vcenter/network" in paths and _int_value(audit.get("network_count")) < 0:
        errors.append("vCenter audit network_count must be a non-negative integer when network collection is reported")
    if audit.get("mode") != "read-only":
        errors.append("vCenter audit mode must be read-only")
    if audit.get("endpoint_configured") is not True:
        errors.append("vCenter audit endpoint_configured must be true")
    summary_count = _int_value(audit.get("summary_count"))
    details_limit = _int_value(audit.get("details_limit"))
    details_count = _int_value(audit.get("details_count"))
    if summary_count != workload_count:
        errors.append("vCenter audit summary_count must match inventory workload count")
    if details_count > summary_count:
        errors.append("vCenter audit details_count cannot exceed summary_count")
    if details_count > details_limit:
        errors.append("vCenter audit details_count cannot exceed details_limit")


def _validate_prism_contract(audit: dict[str, Any], workload_count: int, errors: list[str]) -> None:
    if audit.get("api_paths") != ["/api/nutanix/v3/vms/list"]:
        errors.append("Prism audit api_paths must be /api/nutanix/v3/vms/list only")
    if audit.get("mode") != "read-only":
        errors.append("Prism audit mode must be read-only")
    if audit.get("endpoint_configured") is not True:
        errors.append("Prism audit endpoint_configured must be true")
    if audit.get("post_paths_allowlisted") is not True:
        errors.append("Prism audit post_paths_allowlisted must be true")
    if _int_value(audit.get("entities_count")) != workload_count:
        errors.append("Prism audit entities_count must match inventory workload count")
    for key in ("page_size", "max_pages"):
        if _int_value(audit.get(key)) <= 0:
            errors.append(f"Prism audit {key} must be a positive integer")


def _validate_rvtools_contract(audit: dict[str, Any], workload_count: int, errors: list[str]) -> None:
    if audit.get("mode") != "offline-import":
        errors.append("RVTools audit mode must be offline-import")
    if audit.get("credential_storage") != "not_used":
        errors.append("RVTools audit credential_storage must be not_used")
    if audit.get("endpoint_configured") is not False:
        errors.append("RVTools audit endpoint_configured must be false")
    if _int_value(audit.get("workloads_count")) != workload_count:
        errors.append("RVTools audit workloads_count must match inventory workload count")
    observed = audit.get("files_observed")
    if not isinstance(observed, list) or "vInfo.csv" not in observed:
        errors.append("RVTools audit files_observed must include vInfo.csv")


def _looks_like_vcenter(audit: dict[str, Any], collector: str) -> bool:
    paths = set(audit.get("api_paths") or [])
    return collector == "vcenter-rest" or "/api/vcenter/vm" in paths


def _looks_like_prism(audit: dict[str, Any], collector: str) -> bool:
    paths = set(audit.get("api_paths") or [])
    return collector == "prism-central-v3" or "/api/nutanix/v3/vms/list" in paths


def _walk_audit(value: Any, path: str = "source.collection_audit") -> list[tuple[str, str, Any]]:
    found: list[tuple[str, str, Any]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            key_text = str(key)
            nested_path = f"{path}.{key_text}"
            found.append((nested_path, key_text, nested))
            found.extend(_walk_audit(nested, nested_path))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found.extend(_walk_audit(nested, f"{path}[{index}]"))
    return found


def _hostname_from_endpoint(endpoint: str) -> str:
    parsed = urlparse(endpoint)
    if parsed.hostname:
        return parsed.hostname
    if endpoint and "/" not in endpoint:
        return endpoint.split(":", 1)[0]
    return ""


def _int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1
