from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from .move_plan import validate_move_plan


REQUIRED_CONFIG_KEYS = {
    "plan_name",
    "source_provider",
    "target_provider",
    "target_cluster",
    "target_container",
    "network_mappings",
    "schedule",
}


def load_move_config(path: Path) -> dict[str, Any]:
    config = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(config, dict):
        raise ValueError("Move payload config must be a JSON object")
    missing = [key for key in sorted(REQUIRED_CONFIG_KEYS) if key not in config]
    if missing:
        raise ValueError(f"Move payload config missing required keys: {', '.join(missing)}")
    if not isinstance(config["network_mappings"], list) or not config["network_mappings"]:
        raise ValueError("Move payload config network_mappings must be a non-empty list")
    if not isinstance(config["schedule"], dict):
        raise ValueError("Move payload config schedule must be an object")
    return config


def build_move_payload(plan_path: Path, config_path: Path) -> dict[str, Any]:
    validation = validate_move_plan(plan_path)
    if not validation.ok:
        raise ValueError("Move plan validation failed; refusing to generate payload")

    config = load_move_config(config_path)
    workloads = included_workloads(plan_path)
    if not workloads:
        raise ValueError("Move plan has no included workloads")

    from .network_mapping import validate_network_mappings

    network_validation = validate_network_mappings(plan_path, config_path)
    if not network_validation.ok:
        raise ValueError("Network mapping validation failed; refusing to generate payload")

    return {
        "contract": "nmrcp_move_api_payload_dry_run_v1",
        "dry_run_only": True,
        "mutation_allowed": False,
        "plan_name": config["plan_name"],
        "source_provider": config["source_provider"],
        "target_provider": config["target_provider"],
        "target_cluster": config["target_cluster"],
        "target_container": config["target_container"],
        "network_mappings": config["network_mappings"],
        "schedule": config["schedule"],
        "workloads": workloads,
        "validation": {
            "move_plan_schema": "nmrcp_move_plan_v1",
            "included_count": validation.included_count,
            "held_count": validation.hold_count,
            "warnings": list(validation.warnings),
            "network_mapping": network_validation.summary(),
        },
        "operator_notes": [
            "Generated locally from validated readiness evidence.",
            "Do not submit to Nutanix Move until reviewed and tested against a lab Move appliance.",
            "Provider UUIDs, network mappings, and schedule settings must be confirmed by the migration operator.",
        ],
    }


def included_workloads(plan_path: Path) -> list[dict[str, Any]]:
    workloads: list[dict[str, Any]] = []
    with plan_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            if row.get("include_in_move_plan") != "yes":
                continue
            workloads.append(
                {
                    "source_vm_id": row.get("source_vm_id", ""),
                    "source_vm_name": row.get("source_vm_name", ""),
                    "wave": row.get("wave", ""),
                    "owner": row.get("owner", ""),
                    "target": row.get("target", ""),
                    "readiness": row.get("readiness", ""),
                    "risk_score": int(row.get("risk_score") or 0),
                    "target_networks": split_semicolon(row.get("target_networks", "")),
                    "dependency_count": int(row.get("dependency_count") or 0),
                    "application_owner_approval": row.get("application_owner_approval", ""),
                    "rollback_owner": row.get("rollback_owner", ""),
                    "precheck_status": row.get("precheck_status", ""),
                }
            )
    return workloads


def split_semicolon(value: str) -> list[str]:
    return [item.strip() for item in value.split(";") if item.strip()]
