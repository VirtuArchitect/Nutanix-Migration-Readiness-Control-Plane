from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Finding, WorkloadAssessment


SUPPORTED_TARGETS = {"ahv", "nc2"}
SUPPORTED_GUEST_FAMILIES = {
    "rhel",
    "red hat",
    "ubuntu",
    "debian",
    "sles",
    "suse",
    "windows server 2016",
    "windows server 2019",
    "windows server 2022",
}


@dataclass(frozen=True)
class ReadinessPolicy:
    snapshot_max_age_days: int = 7
    backup_max_age_hours: int = 24
    prepare_risk_threshold: int = 25
    blocked_risk_threshold: int = 50

    def to_dict(self) -> dict[str, int]:
        return {
            "snapshot_max_age_days": self.snapshot_max_age_days,
            "backup_max_age_hours": self.backup_max_age_hours,
            "prepare_risk_threshold": self.prepare_risk_threshold,
            "blocked_risk_threshold": self.blocked_risk_threshold,
        }


DEFAULT_POLICY = ReadinessPolicy()


def load_readiness_policy(path: Path | None) -> ReadinessPolicy:
    if path is None:
        return DEFAULT_POLICY
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Readiness policy file must contain a JSON object")
    allowed = set(DEFAULT_POLICY.to_dict())
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ValueError(f"Unsupported readiness policy keys: {', '.join(unknown)}")
    values = DEFAULT_POLICY.to_dict()
    for key, value in payload.items():
        if not isinstance(value, int) or value <= 0:
            raise ValueError(f"Readiness policy {key} must be a positive integer")
        values[key] = value
    if values["prepare_risk_threshold"] >= values["blocked_risk_threshold"]:
        raise ValueError("Readiness policy prepare_risk_threshold must be lower than blocked_risk_threshold")
    return ReadinessPolicy(**values)


def assess_inventory(
    inventory: dict[str, Any],
    target: str = "ahv",
    policy: ReadinessPolicy = DEFAULT_POLICY,
) -> list[WorkloadAssessment]:
    normalized_target = target.lower()
    if normalized_target not in SUPPORTED_TARGETS:
        raise ValueError(f"Unsupported migration target: {target}")

    workloads = inventory.get("workloads")
    if not isinstance(workloads, list):
        raise ValueError("Inventory must contain a workloads list")

    return [assess_workload(workload, normalized_target, policy=policy) for workload in workloads]


def assess_workload(
    workload: dict[str, Any],
    target: str = "ahv",
    policy: ReadinessPolicy = DEFAULT_POLICY,
) -> WorkloadAssessment:
    findings: list[Finding] = []
    risk_score = 0

    workload_id = str(workload.get("id") or workload.get("name") or "unknown")
    name = str(workload.get("name") or workload_id)
    owner = str(workload.get("owner") or "Unassigned")
    guest_os = str(workload.get("guest_os") or "").lower()
    power_state = str(workload.get("power_state") or "").lower()
    networking = workload.get("networking") or {}
    guest_identity = workload.get("guest_identity") if isinstance(workload.get("guest_identity"), dict) else {}
    snapshots = workload.get("snapshots") or {}
    tools = workload.get("tools") or {}
    backup = workload.get("backup") or {}
    storage = workload.get("storage") or {}
    dependencies = workload.get("dependencies") or []
    governance = workload.get("governance") if isinstance(workload.get("governance"), dict) else {}
    vendor_support = [str(item).lower() for item in workload.get("vendor_support", [])]

    if not guest_os:
        findings.append(
            Finding(
                "guest_os_missing",
                "high",
                "Guest OS is missing, so target compatibility cannot be verified.",
                "Collect guest OS details from vCenter tools or CMDB before wave assignment.",
            )
        )
        risk_score += 25
    elif not any(family in guest_os for family in SUPPORTED_GUEST_FAMILIES):
        findings.append(
            Finding(
                "guest_os_research_required",
                "medium",
                "Guest OS is not in the current known-good family list.",
                "Verify Nutanix support matrix and application vendor support before migration.",
            )
        )
        risk_score += 15

    if power_state and not _is_powered_on(power_state):
        findings.append(
            Finding(
                "power_state_not_on",
                "medium",
                "Workload is not reported as powered on, so live guest validation and precheck evidence may be stale.",
                "Confirm powered-state expectations, cold-migration path, guest tools state, and application owner approval before scheduling.",
            )
        )
        risk_score += 10

    if power_state and _is_powered_on(power_state):
        valid_guest_ips = guest_identity.get("valid_ip_addresses") if isinstance(guest_identity.get("valid_ip_addresses"), list) else []
        invalid_guest_ips = guest_identity.get("invalid_ip_addresses") if isinstance(guest_identity.get("invalid_ip_addresses"), list) else []
        if invalid_guest_ips:
            findings.append(
                Finding(
                    "guest_ip_invalid",
                    "high",
                    "One or more captured guest IP addresses are malformed.",
                    "Fix source inventory or guest tools/IPAM evidence before using it for post-cutover validation.",
                )
            )
            risk_score += 15
        if not valid_guest_ips:
            findings.append(
                Finding(
                    "guest_ip_missing",
                    "medium",
                    "Powered-on workload does not have a valid guest IP address in source evidence.",
                    "Collect guest IP evidence from VMware Tools, IPAM, CMDB, or application owner before cutover.",
                )
            )
            risk_score += 10
        if not str(guest_identity.get("dns_name") or guest_identity.get("hostname") or "").strip():
            findings.append(
                Finding(
                    "guest_dns_missing",
                    "low",
                    "Powered-on workload does not have guest DNS or hostname evidence.",
                    "Capture DNS or hostname evidence so post-migration identity checks are reviewable.",
                )
            )
            risk_score += 5

    if networking.get("uses_nsx"):
        findings.append(
            Finding(
                "nsx_dependency",
                "critical",
                "Workload depends on NSX constructs that require network redesign or mapping.",
                "Map NSX security groups, overlays, and routing before attempting AHV cutover.",
            )
        )
        risk_score += 35

    if networking.get("uses_vds"):
        findings.append(
            Finding(
                "vds_mapping_required",
                "medium",
                "Workload uses a VMware distributed switch backed port group.",
                "Map port groups, VLANs, and IPAM expectations to the target Nutanix network.",
            )
        )
        risk_score += 10

    if int(snapshots.get("count") or 0) > 0:
        findings.append(
            Finding(
                "snapshots_present",
                "medium",
                "One or more VMware snapshots are present.",
                "Consolidate or remove snapshots before migration planning.",
            )
        )
        risk_score += 10

    if int(snapshots.get("oldest_days") or 0) >= policy.snapshot_max_age_days:
        findings.append(
            Finding(
                "snapshot_age_exceeds_policy",
                "high",
                f"One or more VMware snapshots exceed the {policy.snapshot_max_age_days}-day readiness policy.",
                "Consolidate aged snapshots and confirm datastore capacity before migration planning.",
            )
        )
        risk_score += 15

    if tools.get("vmware_tools") is False:
        findings.append(
            Finding(
                "vmware_tools_missing",
                "high",
                "VMware Tools are missing or not running, so guest discovery and driver readiness are weak.",
                "Repair guest tools or validate guest OS, IP, shutdown, and driver state by another approved method.",
            )
        )
        risk_score += 20

    tools_status = str(tools.get("status") or "").lower()
    if tools_status and any(marker in tools_status for marker in ("old", "outdated", "unsupported", "guesttoolsneedupgrade")):
        findings.append(
            Finding(
                "vmware_tools_outdated",
                "medium",
                "VMware Tools appear outdated or unsupported.",
                "Upgrade guest tools or document why the current guest tooling is acceptable before cutover.",
            )
        )
        risk_score += 10

    if tools.get("vmware_tools") and not tools.get("virtio_ready"):
        findings.append(
            Finding(
                "virtio_not_ready",
                "high",
                "VMware tools are present but Nutanix VirtIO readiness is not confirmed.",
                "Install or validate Nutanix VirtIO drivers before cutover.",
            )
        )
        risk_score += 25

    if not backup.get("protected"):
        findings.append(
            Finding(
                "backup_not_confirmed",
                "high",
                "Recent recoverable backup protection is not confirmed.",
                "Confirm backup success and restore point before migration approval.",
            )
        )
        risk_score += 25

    if backup.get("protected") and int(backup.get("last_success_hours") or 0) > policy.backup_max_age_hours:
        findings.append(
            Finding(
                "backup_recovery_point_stale",
                "high",
                f"Backup protection exists, but the last successful restore point is older than {policy.backup_max_age_hours} hours.",
                "Confirm a recent successful backup and restore point before migration approval.",
            )
        )
        risk_score += 20

    if workload.get("tier") == "critical" and target not in vendor_support:
        findings.append(
            Finding(
                "vendor_support_unconfirmed",
                "high",
                "Critical workload does not declare vendor support for the selected target.",
                "Obtain application owner and vendor approval before scheduling migration.",
            )
        )
        risk_score += 20

    if governance and governance.get("application_owner_approved") is not True:
        findings.append(
            Finding(
                "application_owner_approval_missing",
                "high",
                "Application owner approval is not confirmed in workload governance metadata.",
                "Capture application owner approval before Move staging or remediation closure.",
            )
        )
        risk_score += 20

    if governance and not str(governance.get("rollback_owner") or "").strip():
        findings.append(
            Finding(
                "rollback_owner_missing",
                "high",
                "Rollback ownership is not confirmed in workload governance metadata.",
                "Assign a rollback owner and confirm stop or backout criteria before migration approval.",
            )
        )
        risk_score += 15

    if storage.get("raw_device_mapping"):
        findings.append(
            Finding(
                "storage_rdm_mapping_required",
                "critical",
                "Workload has raw device mapping or raw disk evidence that Nutanix Move may not migrate directly.",
                "Convert or redesign raw device mappings before Move staging and capture storage-owner approval.",
            )
        )
        risk_score += 40

    if storage.get("shared_disk"):
        findings.append(
            Finding(
                "shared_disk_cluster_review",
                "high",
                "Workload has shared or multi-writer disk evidence that requires cluster-aware migration planning.",
                "Validate application clustering, disk sharing semantics, and supported Nutanix target design before cutover.",
            )
        )
        risk_score += 25

    if storage.get("independent_disk"):
        findings.append(
            Finding(
                "independent_disk_review",
                "high",
                "Workload has independent disk evidence that may be excluded from snapshot-based migration workflows.",
                "Confirm disk inclusion, backup state, and Move behavior before staging the workload.",
            )
        )
        risk_score += 20

    if storage.get("encrypted"):
        findings.append(
            Finding(
                "encrypted_disk_review",
                "medium",
                "Workload has encrypted disk evidence that requires key and target-platform compatibility review.",
                "Verify encryption ownership, key access, and target support before migration approval.",
            )
        )
        risk_score += 15

    free_percent = _float_or_none(storage.get("min_datastore_free_percent"))
    if free_percent is not None and free_percent < 15:
        findings.append(
            Finding(
                "datastore_free_space_low",
                "high",
                "Source datastore free space is below the 15 percent migration safety threshold.",
                "Increase datastore free space or obtain storage-owner approval before snapshot, replication, or rollback activity.",
            )
        )
        risk_score += 20

    if dependencies and any(not dependency.get("owner") for dependency in dependencies if isinstance(dependency, dict)):
        findings.append(
            Finding(
                "dependency_owner_missing",
                "medium",
                "One or more declared dependencies do not have an owner.",
                "Assign dependency owners before wave planning.",
            )
        )
        risk_score += 10

    readiness = classify_readiness(risk_score, findings, policy=policy)
    return WorkloadAssessment(
        workload_id=workload_id,
        name=name,
        owner=owner,
        readiness=readiness,
        risk_score=min(risk_score, 100),
        target=target,
        findings=tuple(findings),
    )


def classify_readiness(
    risk_score: int,
    findings: list[Finding],
    policy: ReadinessPolicy = DEFAULT_POLICY,
) -> str:
    if any(finding.severity == "critical" for finding in findings):
        return "blocked"
    if risk_score >= policy.blocked_risk_threshold:
        return "blocked"
    if risk_score >= policy.prepare_risk_threshold:
        return "prepare"
    if risk_score >= 10:
        return "research"
    return "ready"


def _float_or_none(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_powered_on(value: str) -> bool:
    normalized = value.replace("_", "").replace("-", "").replace(" ", "")
    return normalized in {"poweredon", "poweron", "on", "running", "poweredup"}
