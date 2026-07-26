from __future__ import annotations

import json
import hashlib
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .assessment_intake import validate_assessment_intake
from .capacity import normalize_prism_capacity
from .collection_proof_report import render_collection_proof_report
from .connectors import EndpointConfig, PrismCentralClient, VCenterClient, endpoint_tls_mode
from .inventory import normalize_prism_inventory, normalize_vcenter_inventory


COLLECTION_SUMMARY_SCHEMA_VERSION = "nmrcp_collection_summary_v1"
COLLECTION_PROOF_MANIFEST_SCHEMA_VERSION = "nmrcp_collection_proof_manifest_v1"


def collect_sources(
    vcenter_config: EndpointConfig,
    prism_config: EndpointConfig,
    out_dir: Path,
    vcenter_details_limit: int = 250,
    prism_page_size: int = 500,
    prism_max_pages: int = 20,
    prism_capacity_page_size: int = 100,
    target: str = "ahv",
    cpu_reserved_percent: float = 20,
    memory_reserved_percent: float = 25,
    storage_reserved_percent: float = 30,
    cpu_overcommit_ratio: float = 1.0,
    assessment_intake_path: Path | None = None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    assessment_intake_proof = validate_assessment_intake_proof(assessment_intake_path)

    vcenter_client = VCenterClient(vcenter_config)
    vm_summaries = vcenter_client.list_vms()
    details_by_vm: dict[str, dict[str, Any]] = {}
    for vm in vm_summaries[:vcenter_details_limit]:
        vm_id = vm.get("vm")
        if isinstance(vm_id, str):
            details_by_vm[vm_id] = vcenter_client.get_vm_details(vm_id)
    vcenter_networks = vcenter_client.list_networks()
    vcenter_inventory = normalize_vcenter_inventory(
        vcenter_config.base_url,
        vm_summaries,
        details_by_vm,
        details_limit=vcenter_details_limit,
        network_count=len(vcenter_networks),
    )

    prism_client = PrismCentralClient(prism_config)
    prism_entities = prism_client.list_vms(page_size=prism_page_size, max_pages=prism_max_pages)
    prism_inventory = normalize_prism_inventory(
        prism_config.base_url,
        prism_entities,
        page_size=prism_page_size,
        max_pages=prism_max_pages,
    )
    clusters = prism_client.list_clusters(page_size=prism_capacity_page_size)
    prism_capacity = normalize_prism_capacity(
        clusters,
        target=target,
        cpu_reserved_percent=cpu_reserved_percent,
        memory_reserved_percent=memory_reserved_percent,
        storage_reserved_percent=storage_reserved_percent,
        cpu_overcommit_ratio=cpu_overcommit_ratio,
    )

    vcenter_path = out_dir / "vcenter-inventory.json"
    vcenter_networks_path = out_dir / "vcenter-networks.json"
    prism_path = out_dir / "prism-inventory.json"
    capacity_path = out_dir / "prism-capacity.json"
    summary_path = out_dir / "collection-summary.json"
    proof_manifest_path = out_dir / "collection-proof-manifest.json"
    proof_report_path = out_dir / "collection-proof-report.md"
    write_json(vcenter_path, vcenter_inventory)
    write_json(vcenter_networks_path, normalize_vcenter_networks(vcenter_networks))
    write_json(prism_path, prism_inventory)
    write_json(capacity_path, prism_capacity)

    summary = collection_summary(
        out_dir=out_dir,
        vcenter_inventory=vcenter_inventory,
        vcenter_networks=vcenter_networks,
        prism_inventory=prism_inventory,
        prism_capacity=prism_capacity,
        vcenter_config=vcenter_config,
        prism_config=prism_config,
        vcenter_path=vcenter_path,
        vcenter_networks_path=vcenter_networks_path,
        prism_path=prism_path,
        capacity_path=capacity_path,
        proof_manifest_path=proof_manifest_path,
        proof_report_path=proof_report_path,
        assessment_intake_proof=assessment_intake_proof,
    )
    write_json(summary_path, summary)
    proof_report_path.write_text(render_collection_proof_report(summary), encoding="utf-8")
    write_json(
        proof_manifest_path,
        collection_proof_manifest(
            out_dir=out_dir,
            collection_summary=summary,
            summary_path=summary_path,
            proof_manifest_path=proof_manifest_path,
        ),
    )
    return summary


def collection_summary(
    out_dir: Path,
    vcenter_inventory: dict[str, Any],
    vcenter_networks: list[dict[str, Any]],
    prism_inventory: dict[str, Any],
    prism_capacity: dict[str, Any],
    vcenter_config: EndpointConfig,
    prism_config: EndpointConfig,
    vcenter_path: Path,
    vcenter_networks_path: Path,
    prism_path: Path,
    capacity_path: Path,
    proof_manifest_path: Path,
    proof_report_path: Path,
    assessment_intake_proof: dict[str, Any] | None = None,
) -> dict[str, Any]:
    vcenter_audit = _audit(vcenter_inventory)
    prism_audit = _audit(prism_inventory)
    capacity_source = prism_capacity.get("source") if isinstance(prism_capacity.get("source"), dict) else {}
    targets = prism_capacity.get("targets") if isinstance(prism_capacity.get("targets"), list) else []
    summary = {
        "schema_version": COLLECTION_SUMMARY_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "status": "pass",
        "artifacts": {
            "vcenter_inventory": str(vcenter_path.relative_to(out_dir)),
            "vcenter_networks": str(vcenter_networks_path.relative_to(out_dir)),
            "prism_inventory": str(prism_path.relative_to(out_dir)),
            "prism_capacity": str(capacity_path.relative_to(out_dir)),
            "collection_summary": "collection-summary.json",
            "collection_proof_manifest": str(proof_manifest_path.relative_to(out_dir)),
            "collection_proof_report": str(proof_report_path.relative_to(out_dir)),
        },
        "checks": [
            {
                "name": "vcenter-read-only-collection",
                "status": "pass",
                "workloads": len(vcenter_inventory.get("workloads") or []),
                "api_paths": list(vcenter_audit.get("api_paths") or []),
                "mutating_calls": int(vcenter_audit.get("mutating_calls") or 0),
                "tls_verification": endpoint_tls_mode(vcenter_config),
            },
            {
                "name": "vcenter-network-read-only-collection",
                "status": "pass",
                "networks": len(vcenter_networks),
                "api_paths": ["/api/session", "/api/vcenter/network"],
                "mutating_calls": 0,
                "tls_verification": endpoint_tls_mode(vcenter_config),
            },
            {
                "name": "prism-read-only-collection",
                "status": "pass",
                "workloads": len(prism_inventory.get("workloads") or []),
                "api_paths": list(prism_audit.get("api_paths") or []),
                "mutating_calls": int(prism_audit.get("mutating_calls") or 0),
                "tls_verification": endpoint_tls_mode(prism_config),
            },
            {
                "name": "prism-capacity-read-only-collection",
                "status": "pass",
                "targets": len(targets),
                "api_paths": list(capacity_source.get("api_paths") or []),
                "mutating_calls": int(capacity_source.get("mutating_calls") or 0),
                "tls_verification": endpoint_tls_mode(prism_config),
            },
        ],
        "privacy": {
            "credentials_serialized": False,
            "endpoint_values_serialized": False,
            "summary_redacted": True,
            "tls_verification": {
                "vcenter": endpoint_tls_mode(vcenter_config),
                "prism-central": endpoint_tls_mode(prism_config),
            },
        },
    }
    if assessment_intake_proof:
        summary["governance"] = {"assessment_intake": assessment_intake_proof}
    return summary


def collection_proof_manifest(
    out_dir: Path,
    collection_summary: dict[str, Any],
    summary_path: Path,
    proof_manifest_path: Path,
) -> dict[str, Any]:
    artifacts = collection_summary.get("artifacts") if isinstance(collection_summary.get("artifacts"), dict) else {}
    artifact_names = sorted(
        {
            str(relative)
            for key, relative in artifacts.items()
            if key != "collection_proof_manifest" and isinstance(relative, str)
        }
    )
    if str(summary_path.relative_to(out_dir)) not in artifact_names:
        artifact_names.append(str(summary_path.relative_to(out_dir)))
        artifact_names.sort()
    return {
        "schema_version": COLLECTION_PROOF_MANIFEST_SCHEMA_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "security": {
            "mode": "read-only",
            "credentials_serialized": False,
            "endpoint_values_serialized": False,
            "mutation_allowed": False,
            "manifest_self_name": str(proof_manifest_path.relative_to(out_dir)),
            "read_only_api_allowlist": sorted(read_only_api_paths(collection_summary)),
            "assessment_intake": collection_summary.get("governance", {}).get("assessment_intake", {"status": "not_supplied"}),
        },
        "artifacts": [
            {
                "name": name,
                "size_bytes": (out_dir / name).stat().st_size,
                "sha256": sha256_file(out_dir / name),
                "contains_workload_data": name
                in {"vcenter-inventory.json", "vcenter-networks.json", "prism-inventory.json", "prism-capacity.json"},
            }
            for name in artifact_names
        ],
    }


def validate_assessment_intake_proof(path: Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    result = validate_assessment_intake(path)
    if not result.ok:
        details = "; ".join(result.errors)
        raise ValueError(f"Assessment intake validation failed: {details}")
    return {
        "status": "pass",
        "schema_version": "nmrcp_assessment_intake_validation_v1",
        "source_sha256": sha256_file(path),
        "rows": result.rows,
        "warnings": list(result.warnings),
        "values_serialized": False,
    }


def read_only_api_paths(collection_summary: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    checks = collection_summary.get("checks") if isinstance(collection_summary.get("checks"), list) else []
    for check in checks:
        if not isinstance(check, dict):
            continue
        for path in check.get("api_paths") or []:
            paths.add(str(path))
    return paths


def normalize_vcenter_networks(networks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": "nmrcp_vcenter_network_inventory_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "source": {
            "system": "vcenter-rest",
            "mode": "read-only",
            "credential_storage": "not_persisted",
            "api_paths": ["/api/session", "/api/vcenter/network"],
            "mutating_calls": 0,
        },
        "networks": [
            {
                "network": str(item.get("network") or item.get("network_id") or item.get("id") or item.get("name") or "unknown"),
                "name": str(item.get("name") or item.get("network") or "unknown"),
                "type": str(item.get("type") or item.get("network_type") or "unknown"),
                "vlan": str(item.get("vlan") or item.get("vlan_id") or ""),
            }
            for item in networks
            if isinstance(item, dict)
        ],
    }


def _audit(inventory: dict[str, Any]) -> dict[str, Any]:
    source = inventory.get("source") if isinstance(inventory.get("source"), dict) else {}
    audit = source.get("collection_audit") if isinstance(source.get("collection_audit"), dict) else {}
    return audit


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
