from __future__ import annotations

from dataclasses import dataclass
from typing import Any


ENVIRONMENT_ACCESS_SCHEMA_VERSION = "nmrcp_environment_access_v1"

ENVIRONMENTS = ("dev", "uat", "production")
TARGETS = ("pc", "move", "vcenter", "esxi")
MODES = ("read", "write")

TARGET_LABELS = {
    "pc": "Prism Central",
    "move": "Nutanix Move",
    "vcenter": "vCenter",
    "esxi": "ESXi",
}

BASE_GATES = {
    "read": ("source_scope_approved", "credential_source_approved"),
    "write": (
        "source_scope_approved",
        "credential_source_approved",
        "change_reference",
        "rollback_plan",
        "write_scope_approved",
    ),
}

ENVIRONMENT_GATES = {
    "dev": {
        "read": (),
        "write": ("operator_acknowledgement",),
    },
    "uat": {
        "read": ("change_reference",),
        "write": ("maintenance_window", "peer_review", "dry_run_passed"),
    },
    "production": {
        "read": ("change_reference", "business_owner_approval"),
        "write": (
            "maintenance_window",
            "peer_review",
            "dry_run_passed",
            "cab_approval",
            "backup_verified",
            "production_write_break_glass",
        ),
    },
}

TARGET_WRITE_GATES = {
    "pc": ("target_cluster_scope",),
    "move": ("move_lab_or_approved_appliance",),
    "vcenter": ("vm_scope_approved",),
    "esxi": ("host_scope_approved",),
}


@dataclass(frozen=True)
class EnvironmentAccessResult:
    environment: str
    target: str
    mode: str
    status: str
    required_gates: tuple[str, ...]
    satisfied_gates: tuple[str, ...]
    missing_gates: tuple[str, ...]
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": ENVIRONMENT_ACCESS_SCHEMA_VERSION,
            "environment": self.environment,
            "target": self.target,
            "target_label": TARGET_LABELS[self.target],
            "mode": self.mode,
            "status": self.status,
            "required_gates": list(self.required_gates),
            "satisfied_gates": list(self.satisfied_gates),
            "missing_gates": list(self.missing_gates),
            "warnings": list(self.warnings),
        }


def evaluate_environment_access(environment: str, target: str, mode: str, gates: dict[str, Any] | None = None) -> EnvironmentAccessResult:
    normalized_environment = _normalize(environment, ENVIRONMENTS, "environment")
    normalized_target = _normalize(target, TARGETS, "target")
    normalized_mode = _normalize(mode, MODES, "mode")
    provided = gates or {}
    required = required_gates(normalized_environment, normalized_target, normalized_mode)
    satisfied = tuple(gate for gate in required if _gate_satisfied(provided.get(gate)))
    missing = tuple(gate for gate in required if gate not in satisfied)
    warnings = []
    if normalized_mode == "write":
        warnings.append("write intent is gate-only; NMRCP does not execute mutating actions from this workflow")
    if normalized_environment == "production" and normalized_mode == "write":
        warnings.append("production write intent requires explicit break-glass approval and remains fail-closed until every gate is satisfied")
    return EnvironmentAccessResult(
        environment=normalized_environment,
        target=normalized_target,
        mode=normalized_mode,
        status="pass" if not missing else "blocked",
        required_gates=required,
        satisfied_gates=satisfied,
        missing_gates=missing,
        warnings=tuple(warnings),
    )


def required_gates(environment: str, target: str, mode: str) -> tuple[str, ...]:
    normalized_environment = _normalize(environment, ENVIRONMENTS, "environment")
    normalized_target = _normalize(target, TARGETS, "target")
    normalized_mode = _normalize(mode, MODES, "mode")
    gates: list[str] = []
    gates.extend(BASE_GATES[normalized_mode])
    gates.extend(ENVIRONMENT_GATES[normalized_environment][normalized_mode])
    if normalized_mode == "write":
        gates.extend(TARGET_WRITE_GATES[normalized_target])
    return tuple(dict.fromkeys(gates))


def environment_access_options() -> dict[str, Any]:
    return {
        "schema_version": "nmrcp_environment_access_options_v1",
        "environments": list(ENVIRONMENTS),
        "targets": [{"id": target, "label": TARGET_LABELS[target]} for target in TARGETS],
        "modes": list(MODES),
        "gate_catalog": sorted(
            set(BASE_GATES["read"])
            | set(BASE_GATES["write"])
            | {gate for env in ENVIRONMENT_GATES.values() for gates in env.values() for gate in gates}
            | {gate for gates in TARGET_WRITE_GATES.values() for gate in gates}
        ),
    }


def _normalize(value: str, allowed: tuple[str, ...], label: str) -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized not in allowed:
        raise ValueError(f"{label} must be one of {', '.join(allowed)}")
    return normalized


def _gate_satisfied(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return bool(value.strip())
    return value is not None
