from __future__ import annotations

import csv
from datetime import UTC, datetime
import hashlib
import html
import json
from pathlib import Path
from typing import Any

from .approval_exceptions import approval_exceptions_context, write_approval_exceptions_csv
from .compatibility_research import compatibility_research_context, write_compatibility_research_csv
from .connectivity_checklist import connectivity_checklist_context, write_connectivity_checklist_csv
from .dependencies import apply_dependency_readiness_gates, dependency_sequence
from .dependency_review import dependency_review_context, write_dependency_review_csv
from .identity_cutover_plan import identity_cutover_context, write_identity_cutover_plan_csv
from .inventory_coverage import INVENTORY_COVERAGE_COLUMNS, INVENTORY_COVERAGE_CONTEXT_SCHEMA_VERSION
from .migration_execution_queue import migration_execution_queue_context, write_migration_execution_queue_csv
from .move_lab_closure_checklist import write_move_lab_closure_checklist
from .move_lab_evidence_request import write_move_lab_evidence_request
from .move_plan_brief import write_move_plan_brief
from .move_staging_readiness import move_staging_readiness_context, write_move_staging_brief, write_move_staging_readiness_csv
from .models import Wave, WorkloadAssessment
from .operator_portal import write_operator_portal
from .operations_console import write_operations_console
from .partner_handoff_matrix import partner_handoff_context, write_partner_handoff_matrix_csv
from .prism_categories import prism_category_context, write_prism_category_mapping_csv
from .recovery_readiness import recovery_readiness_context, write_recovery_readiness_csv
from .redaction import redact_dict
from .rollback_plan import rollback_plan_context, write_rollback_plan_csv
from .scoring import ReadinessPolicy, assess_inventory
from .storage_posture import storage_posture_context, write_storage_posture_csv
from .stakeholder_comms import stakeholder_comms_context, write_stakeholder_comms_csv
from .source_endpoint_evidence_request import write_source_endpoint_evidence_request
from .tools_driver_readiness import tools_driver_context, write_tools_driver_readiness_csv
from .wave_execution_calendar import wave_execution_calendar_context, write_wave_execution_calendar_csv
from .workload_validation_checklist import workload_validation_context, write_workload_validation_checklist_csv
from .what_will_break import what_will_break_context, write_what_will_break_brief, write_what_will_break_csv


MOVE_PLAN_SCHEMA_VERSION = "nmrcp_move_plan_v1"


def write_assessment(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    out_dir: Path,
    policy: dict[str, Any] | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    coverage_rows = inventory_coverage_rows(inventory)
    payload = {
        "source": redact_dict(inventory.get("source", {})),
        "summary": summarize(assessments),
        "inventory_coverage": summarize_inventory_coverage_rows(coverage_rows),
        "inventory_coverage_context": inventory_coverage_context(coverage_rows),
        "business_context": business_context(inventory),
        "signoff_context": signoff_context(inventory, assessments),
        "approval_exceptions_context": approval_exceptions_context(assessments, waves),
        "partner_handoff_context": partner_handoff_context(assessments, waves),
        "wave_execution_calendar_context": wave_execution_calendar_context(assessments, waves),
        "target_comparison_context": target_comparison_context(inventory, policy or {}),
        "compatibility_research_context": compatibility_research_context(inventory, assessments),
        "dependency_sequence_context": dependency_sequence_context(inventory, assessments),
        "dependency_review_context": dependency_review_context(inventory, assessments),
        "connectivity_checklist_context": connectivity_checklist_context(inventory, assessments),
        "identity_cutover_context": identity_cutover_context(inventory, assessments, waves),
        "tools_driver_context": tools_driver_context(inventory, assessments),
        "storage_posture_context": storage_posture_context(inventory, assessments),
        "recovery_readiness_context": recovery_readiness_context(inventory, assessments),
        "rollback_plan_context": rollback_plan_context(inventory, assessments, waves),
        "move_staging_readiness_context": move_staging_readiness_context(inventory, assessments, waves),
        "workload_validation_context": workload_validation_context(inventory, assessments, waves),
        "migration_execution_queue_context": migration_execution_queue_context(inventory, assessments, waves),
        "prism_category_context": prism_category_context(inventory, assessments),
        "stakeholder_comms_context": stakeholder_comms_context(assessments, waves),
        "what_will_break_context": what_will_break_context(assessments, waves, coverage_rows=coverage_rows),
        "policy": policy or {},
        "assessments": [assessment.to_dict() for assessment in assessments],
        "waves": [wave.to_dict() for wave in waves],
    }
    (out_dir / "assessment.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    write_inventory_coverage_csv(inventory, out_dir / "inventory-coverage.csv")
    write_waves_csv(assessments, waves, out_dir / "migration-waves.csv")
    write_wave_readiness_summary_csv(assessments, waves, out_dir / "wave-readiness-summary.csv")
    write_wave_execution_calendar_csv(assessments, waves, out_dir / "wave-execution-calendar.csv")
    write_partner_handoff_matrix_csv(assessments, waves, out_dir / "partner-handoff-matrix.csv")
    write_target_comparison_csv(inventory, policy or {}, out_dir / "target-readiness-comparison.csv")
    write_compatibility_research_csv(inventory, assessments, out_dir / "compatibility-research.csv")
    write_sequence_csv(inventory, assessments, out_dir / "dependency-sequence.csv")
    write_dependency_review_csv(inventory, assessments, out_dir / "dependency-review.csv")
    write_connectivity_checklist_csv(inventory, assessments, out_dir / "connectivity-checklist.csv")
    write_identity_cutover_plan_csv(inventory, assessments, waves, out_dir / "identity-cutover-plan.csv")
    write_tools_driver_readiness_csv(inventory, assessments, out_dir / "tools-driver-readiness.csv")
    write_storage_posture_csv(inventory, assessments, out_dir / "storage-posture.csv")
    write_recovery_readiness_csv(inventory, assessments, out_dir / "recovery-readiness.csv")
    write_rollback_plan_csv(inventory, assessments, waves, out_dir / "rollback-plan.csv")
    write_move_staging_readiness_csv(inventory, assessments, waves, out_dir / "move-staging-readiness.csv")
    write_move_staging_brief(inventory, assessments, waves, out_dir / "move-staging-brief.md")
    write_workload_validation_checklist_csv(inventory, assessments, waves, out_dir / "workload-validation-checklist.csv")
    write_migration_execution_queue_csv(inventory, assessments, waves, out_dir / "migration-execution-queue.csv")
    write_prism_category_mapping_csv(inventory, assessments, out_dir / "prism-category-mapping.csv")
    write_stakeholder_comms_csv(assessments, waves, out_dir / "stakeholder-communication-plan.csv")
    write_what_will_break_csv(assessments, waves, out_dir / "what-will-break-report.csv", coverage_rows=coverage_rows)
    write_what_will_break_brief(assessments, waves, out_dir / "what-will-break-brief.md", coverage_rows=coverage_rows)
    write_remediation_tracker_csv(assessments, waves, out_dir / "remediation-tracker.csv")
    write_migration_risk_register_csv(assessments, waves, out_dir / "migration-risk-register.csv")
    write_owner_risk_summary_csv(assessments, waves, out_dir / "owner-risk-summary.csv")
    write_business_impact_summary_csv(inventory, assessments, waves, out_dir / "business-impact-summary.csv")
    write_owner_signoff_matrix_csv(inventory, assessments, waves, out_dir / "owner-signoff-matrix.csv")
    write_approval_exceptions_csv(assessments, waves, out_dir / "approval-exceptions.csv")
    write_move_plan_csv(inventory, assessments, waves, out_dir / "nutanix-move-plan.csv")
    write_move_plan_brief(out_dir / "nutanix-move-plan.csv", out_dir / "assessment.json", out_dir / "move-plan-brief.md")
    write_executive_readiness_brief(inventory, assessments, waves, out_dir / "executive-readiness-brief.md")
    write_evidence_markdown(inventory, assessments, waves, out_dir / "change-board-evidence.md")
    write_migration_runbook(inventory, assessments, waves, out_dir / "migration-runbook.md")
    write_operations_console(inventory, assessments, waves, out_dir / "operations-console.html")
    write_operator_portal(inventory, assessments, waves, out_dir / "operator-portal.html")
    write_html_report(inventory, assessments, waves, out_dir / "operator-report.html")
    write_operator_dashboard(inventory, assessments, waves, out_dir / "operator-dashboard.html")
    write_validation_checklist(out_dir / "pre-post-validation-checklist.md")
    write_move_lab_closure_checklist(out_dir / "move-lab-closure-checklist.md")
    write_move_lab_evidence_request(assessments, waves, out_dir / "move-lab-evidence-request.md")
    write_source_endpoint_evidence_request(assessments, out_dir / "source-endpoint-evidence-request.md")
    write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)


def summarize(assessments: list[WorkloadAssessment]) -> dict[str, int]:
    summary = {"ready": 0, "research": 0, "prepare": 0, "blocked": 0}
    for assessment in assessments:
        summary[assessment.readiness] = summary.get(assessment.readiness, 0) + 1
    summary["total"] = len(assessments)
    return summary


def summarize_inventory_coverage(inventory: dict[str, Any]) -> dict[str, int | float]:
    return summarize_inventory_coverage_rows(inventory_coverage_rows(inventory))


def summarize_inventory_coverage_rows(rows: list[dict[str, str | int]]) -> dict[str, int | float]:
    if not rows:
        return {"workloads": 0, "average_coverage_percent": 0.0, "workloads_with_gaps": 0}
    total = sum(int(row["coverage_percent"]) for row in rows)
    return {
        "workloads": len(rows),
        "average_coverage_percent": round(total / len(rows), 2),
        "workloads_with_gaps": sum(1 for row in rows if row["missing_fields"]),
    }


def inventory_coverage_context(rows: list[dict[str, str | int]]) -> dict[str, Any]:
    return {
        "schema_version": INVENTORY_COVERAGE_CONTEXT_SCHEMA_VERSION,
        "rows": [
            {column: str(row.get(column) or "") for column in INVENTORY_COVERAGE_COLUMNS}
            for row in rows
        ],
    }


def business_context(inventory: dict[str, Any]) -> dict[str, Any]:
    workloads = inventory.get("workloads") if isinstance(inventory.get("workloads"), list) else []
    return {
        "schema_version": "nmrcp_business_context_v1",
        "workloads": [
            {
                "workload_id": str(workload.get("id") or workload.get("name") or "unknown"),
                "name": str(workload.get("name") or workload.get("id") or "unknown"),
                "owner": str(workload.get("owner") or "Unassigned"),
                "tier": normalized_tier(workload.get("tier")),
            }
            for workload in workloads
            if isinstance(workload, dict)
        ],
    }


def signoff_context(inventory: dict[str, Any], assessments: list[WorkloadAssessment]) -> dict[str, Any]:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    rows: list[dict[str, Any]] = []
    for assessment in assessments:
        workload = workloads.get(assessment.workload_id, {})
        dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
        rows.append(
            {
                "workload_id": assessment.workload_id,
                "required_signoffs": required_signoffs(assessment, workload, dependencies),
                "has_dependencies": bool(dependencies),
            }
        )
    return {
        "schema_version": "nmrcp_signoff_context_v1",
        "workloads": rows,
    }


def target_comparison_context(inventory: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    ahv = {
        assessment.workload_id: assessment
        for assessment in apply_dependency_readiness_gates(
            inventory,
            assess_inventory(inventory, target="ahv", policy=ReadinessPolicy(**policy) if policy else ReadinessPolicy()),
        )
    }
    nc2 = {
        assessment.workload_id: assessment
        for assessment in apply_dependency_readiness_gates(
            inventory,
            assess_inventory(inventory, target="nc2", policy=ReadinessPolicy(**policy) if policy else ReadinessPolicy()),
        )
    }
    workloads: list[dict[str, Any]] = []
    for workload_id in sorted(set(ahv) | set(nc2)):
        ahv_assessment = ahv.get(workload_id)
        nc2_assessment = nc2.get(workload_id)
        preferred, reason = preferred_target(ahv_assessment, nc2_assessment)
        assessment = ahv_assessment or nc2_assessment
        workloads.append(
            {
                "workload_id": workload_id,
                "name": assessment.name if assessment else workload_id,
                "owner": assessment.owner if assessment else "Unassigned",
                "ahv_readiness": ahv_assessment.readiness if ahv_assessment else "unknown",
                "ahv_risk_score": ahv_assessment.risk_score if ahv_assessment else "",
                "ahv_findings": [finding.code for finding in ahv_assessment.findings] if ahv_assessment else [],
                "nc2_readiness": nc2_assessment.readiness if nc2_assessment else "unknown",
                "nc2_risk_score": nc2_assessment.risk_score if nc2_assessment else "",
                "nc2_findings": [finding.code for finding in nc2_assessment.findings] if nc2_assessment else [],
                "preferred_target": preferred,
                "decision_reason": reason,
            }
        )
    return {
        "schema_version": "nmrcp_target_comparison_context_v1",
        "workloads": workloads,
    }


def dependency_sequence_context(inventory: dict[str, Any], assessments: list[WorkloadAssessment]) -> dict[str, Any]:
    assessments_by_id = {assessment.workload_id: assessment for assessment in assessments}
    sequence = dependency_sequence(inventory, assessments)
    workloads_by_id = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    rows: list[dict[str, Any]] = []
    for index, workload_id in enumerate(sequence, start=1):
        assessment = assessments_by_id[workload_id]
        workload = workloads_by_id.get(workload_id, {})
        dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
        rows.append(
            {
                "sequence": index,
                "workload_id": assessment.workload_id,
                "name": assessment.name,
                "owner": assessment.owner,
                "readiness": assessment.readiness,
                "dependency_count": len(dependencies),
            }
        )
    return {
        "schema_version": "nmrcp_dependency_sequence_context_v1",
        "workloads": rows,
    }


def write_inventory_coverage_csv(inventory: dict[str, Any], path: Path) -> None:
    rows = inventory_coverage_rows(inventory)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "workload_id",
                "name",
                "coverage_percent",
                "present_fields",
                "partial_fields",
                "missing_fields",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def inventory_coverage_rows(inventory: dict[str, Any]) -> list[dict[str, str | int]]:
    rows: list[dict[str, str | int]] = []
    workloads = inventory.get("workloads") if isinstance(inventory.get("workloads"), list) else []
    for workload in workloads:
        if not isinstance(workload, dict):
            continue
        status = inventory_coverage_status(workload)
        present = sorted(key for key, value in status.items() if value == "present")
        partial = sorted(key for key, value in status.items() if value == "partial")
        missing = sorted(key for key, value in status.items() if value == "missing")
        score = round(((len(present) + (len(partial) * 0.5)) / len(status)) * 100)
        rows.append(
            {
                "workload_id": str(workload.get("id") or workload.get("name") or "unknown"),
                "name": str(workload.get("name") or workload.get("id") or "unknown"),
                "coverage_percent": score,
                "present_fields": ";".join(present),
                "partial_fields": ";".join(partial),
                "missing_fields": ";".join(missing),
            }
        )
    return rows


def inventory_coverage_status(workload: dict[str, Any]) -> dict[str, str]:
    networking = workload.get("networking") if isinstance(workload.get("networking"), dict) else {}
    guest_identity = workload.get("guest_identity") if isinstance(workload.get("guest_identity"), dict) else {}
    snapshots = workload.get("snapshots") if isinstance(workload.get("snapshots"), dict) else {}
    tools = workload.get("tools") if isinstance(workload.get("tools"), dict) else {}
    backup = workload.get("backup") if isinstance(workload.get("backup"), dict) else {}
    storage = workload.get("storage") if isinstance(workload.get("storage"), dict) else {}
    governance = workload.get("governance") if isinstance(workload.get("governance"), dict) else {}
    dependencies = workload.get("dependencies")
    return {
        "owner": present_if_text(workload.get("owner"), unknown_values={"Unassigned", "unknown"}),
        "tier": present_if_text(workload.get("tier"), unknown_values={"unknown"}),
        "guest_os": present_if_text(workload.get("guest_os")),
        "cpu": present_if_number(workload.get("cpu")),
        "memory_gib": present_if_number(workload.get("memory_gib")),
        "disk_gib": present_if_number(workload.get("disk_gib")),
        "networking": nested_status(networking, required_keys=("uses_vds", "uses_nsx"), list_keys=("vlans",)),
        "guest_identity": guest_identity_status(guest_identity),
        "snapshots": nested_status(snapshots, required_keys=("count",)),
        "tools": nested_status(tools, required_keys=("vmware_tools", "virtio_ready")),
        "backup": nested_status(backup, required_keys=("protected",)),
        "storage": nested_status(storage, required_keys=("disk_count",)),
        "vendor_support": present_if_list(workload.get("vendor_support")),
        "application_owner_approval": present_if_bool(governance.get("application_owner_approved")),
        "rollback_owner": present_if_text(governance.get("rollback_owner")),
        "dependencies": "present" if isinstance(dependencies, list) else "missing",
    }


def nested_status(
    value: dict[str, Any],
    required_keys: tuple[str, ...],
    list_keys: tuple[str, ...] = (),
) -> str:
    if not value:
        return "missing"
    required_present = all(key in value and value[key] not in {None, ""} for key in required_keys)
    list_present = all(isinstance(value.get(key), list) for key in list_keys)
    if required_present and list_present:
        return "present"
    return "partial"


def guest_identity_status(value: dict[str, Any]) -> str:
    if not value:
        return "missing"
    valid_ips = value.get("valid_ip_addresses")
    dns_name = str(value.get("dns_name") or "").strip()
    hostname = str(value.get("hostname") or "").strip()
    invalid_ips = value.get("invalid_ip_addresses")
    if isinstance(valid_ips, list) and valid_ips and (dns_name or hostname):
        return "present"
    if (isinstance(valid_ips, list) and valid_ips) or dns_name or hostname or (isinstance(invalid_ips, list) and invalid_ips):
        return "partial"
    return "missing"


def present_if_text(value: Any, unknown_values: set[str] | None = None) -> str:
    if value is None:
        return "missing"
    text = str(value).strip()
    if not text:
        return "missing"
    if unknown_values and text in unknown_values:
        return "missing"
    return "present"


def present_if_number(value: Any) -> str:
    return "present" if isinstance(value, (int, float)) and value > 0 else "missing"


def present_if_bool(value: Any) -> str:
    return "present" if isinstance(value, bool) else "missing"


def present_if_list(value: Any) -> str:
    return "present" if isinstance(value, list) and bool(value) else "missing"


def write_waves_csv(assessments: list[WorkloadAssessment], waves: list[Wave], path: Path) -> None:
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["wave", "workload_id", "name", "owner", "target", "readiness", "risk_score", "top_findings"],
        )
        writer.writeheader()
        for assessment in assessments:
            writer.writerow(
                {
                    "wave": wave_by_workload.get(assessment.workload_id, "Unassigned"),
                    "workload_id": assessment.workload_id,
                    "name": assessment.name,
                    "owner": assessment.owner,
                    "target": assessment.target,
                    "readiness": assessment.readiness,
                    "risk_score": assessment.risk_score,
                    "top_findings": "; ".join(finding.code for finding in assessment.findings[:3]),
                }
            )


def write_wave_readiness_summary_csv(assessments: list[WorkloadAssessment], waves: list[Wave], path: Path) -> None:
    assessments_by_id = {assessment.workload_id: assessment for assessment in assessments}
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "wave",
                "description",
                "total_workloads",
                "ready",
                "research",
                "prepare",
                "blocked",
                "average_risk_score",
                "max_risk_score",
                "open_findings",
                "critical_findings",
                "high_findings",
                "move_staging_status",
                "move_staging_candidates",
                "held_workloads",
                "owners",
                "next_gate",
            ],
        )
        writer.writeheader()
        for wave in waves:
            wave_assessments = [assessments_by_id[workload_id] for workload_id in wave.workload_ids if workload_id in assessments_by_id]
            summary = summarize(wave_assessments)
            findings = [finding for assessment in wave_assessments for finding in assessment.findings]
            held_workloads = [
                assessment.name
                for assessment in wave_assessments
                if assessment.readiness in {"prepare", "blocked"}
            ]
            candidates = [
                assessment.name
                for assessment in wave_assessments
                if assessment.readiness in {"ready", "research"}
            ]
            writer.writerow(
                {
                    "wave": wave.name,
                    "description": wave.description,
                    "total_workloads": summary["total"],
                    "ready": summary["ready"],
                    "research": summary["research"],
                    "prepare": summary["prepare"],
                    "blocked": summary["blocked"],
                    "average_risk_score": average_risk_score(wave_assessments),
                    "max_risk_score": max((assessment.risk_score for assessment in wave_assessments), default=0),
                    "open_findings": len(findings),
                    "critical_findings": severity_count(findings, "critical"),
                    "high_findings": severity_count(findings, "high"),
                    "move_staging_status": wave_move_staging_status(summary, findings),
                    "move_staging_candidates": ";".join(candidates),
                    "held_workloads": ";".join(held_workloads),
                    "owners": ";".join(sorted({assessment.owner or "Unassigned" for assessment in wave_assessments})),
                    "next_gate": wave_next_gate(summary, findings),
                }
            )


def average_risk_score(assessments: list[WorkloadAssessment]) -> float:
    if not assessments:
        return 0.0
    return round(sum(assessment.risk_score for assessment in assessments) / len(assessments), 2)


def wave_move_staging_status(summary: dict[str, int], findings: list[Any]) -> str:
    if summary["prepare"] or summary["blocked"]:
        return "hold"
    if severity_count(findings, "critical") or severity_count(findings, "high"):
        return "hold"
    if summary["research"]:
        return "conditional"
    return "ready"


def wave_next_gate(summary: dict[str, int], findings: list[Any]) -> str:
    if summary["blocked"]:
        return "Clear blocked findings and obtain formal risk acceptance before Move staging."
    if summary["prepare"]:
        return "Close remediation tracker rows and re-run assessment before Move staging."
    if severity_count(findings, "critical") or severity_count(findings, "high"):
        return "Resolve high-severity findings before scheduling the wave."
    if summary["research"]:
        return "Confirm compatibility research, owner approval, backup proof, and rollback criteria."
    return "Confirm owner signoff, backup proof, rollback criteria, and pre/post validation ownership."


def write_target_comparison_csv(inventory: dict[str, Any], policy: dict[str, Any], path: Path) -> None:
    ahv = {
        assessment.workload_id: assessment
        for assessment in apply_dependency_readiness_gates(
            inventory,
            assess_inventory(inventory, target="ahv", policy=ReadinessPolicy(**policy) if policy else ReadinessPolicy()),
        )
    }
    nc2 = {
        assessment.workload_id: assessment
        for assessment in apply_dependency_readiness_gates(
            inventory,
            assess_inventory(inventory, target="nc2", policy=ReadinessPolicy(**policy) if policy else ReadinessPolicy()),
        )
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "workload_id",
                "name",
                "owner",
                "ahv_readiness",
                "ahv_risk_score",
                "ahv_findings",
                "nc2_readiness",
                "nc2_risk_score",
                "nc2_findings",
                "preferred_target",
                "decision_reason",
            ],
        )
        writer.writeheader()
        for workload_id in sorted(set(ahv) | set(nc2)):
            ahv_assessment = ahv.get(workload_id)
            nc2_assessment = nc2.get(workload_id)
            preferred, reason = preferred_target(ahv_assessment, nc2_assessment)
            assessment = ahv_assessment or nc2_assessment
            writer.writerow(
                {
                    "workload_id": workload_id,
                    "name": assessment.name if assessment else workload_id,
                    "owner": assessment.owner if assessment else "Unassigned",
                    "ahv_readiness": ahv_assessment.readiness if ahv_assessment else "unknown",
                    "ahv_risk_score": ahv_assessment.risk_score if ahv_assessment else "",
                    "ahv_findings": "; ".join(finding.code for finding in ahv_assessment.findings) if ahv_assessment else "",
                    "nc2_readiness": nc2_assessment.readiness if nc2_assessment else "unknown",
                    "nc2_risk_score": nc2_assessment.risk_score if nc2_assessment else "",
                    "nc2_findings": "; ".join(finding.code for finding in nc2_assessment.findings) if nc2_assessment else "",
                    "preferred_target": preferred,
                    "decision_reason": reason,
                }
            )


def preferred_target(ahv: WorkloadAssessment | None, nc2: WorkloadAssessment | None) -> tuple[str, str]:
    if ahv is None or nc2 is None:
        return "review", "target assessment missing"
    readiness_rank = {"ready": 0, "research": 1, "prepare": 2, "blocked": 3}
    ahv_rank = readiness_rank.get(ahv.readiness, 99)
    nc2_rank = readiness_rank.get(nc2.readiness, 99)
    if ahv_rank < nc2_rank:
        return "ahv", "AHV has lower readiness state"
    if nc2_rank < ahv_rank:
        return "nc2", "NC2 has lower readiness state"
    if ahv.risk_score < nc2.risk_score:
        return "ahv", "AHV has lower risk score"
    if nc2.risk_score < ahv.risk_score:
        return "nc2", "NC2 has lower risk score"
    return "either", "AHV and NC2 readiness are equivalent"


def write_sequence_csv(inventory: dict[str, Any], assessments: list[WorkloadAssessment], path: Path) -> None:
    assessments_by_id = {assessment.workload_id: assessment for assessment in assessments}
    sequence = dependency_sequence(inventory, assessments)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "sequence",
                "workload_id",
                "name",
                "owner",
                "readiness",
                "dependency_count",
                "notes",
            ],
        )
        writer.writeheader()
        for index, workload_id in enumerate(sequence, start=1):
            assessment = assessments_by_id[workload_id]
            workload = next(
                (
                    item
                    for item in inventory.get("workloads", [])
                    if isinstance(item, dict) and str(item.get("id") or item.get("name")) == workload_id
                ),
                {},
            )
            dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
            writer.writerow(
                {
                    "sequence": index,
                    "workload_id": assessment.workload_id,
                    "name": assessment.name,
                    "owner": assessment.owner,
                    "readiness": assessment.readiness,
                    "dependency_count": len(dependencies),
                    "notes": "dependency-aware included workload order",
                }
            )


def write_remediation_tracker_csv(assessments: list[WorkloadAssessment], waves: list[Wave], path: Path) -> None:
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "status",
                "owner",
                "wave",
                "workload_id",
                "workload_name",
                "target",
                "readiness",
                "risk_score",
                "severity",
                "finding_code",
                "recommended_action",
                "evidence_ref",
                "closure_ref",
                "closed_by",
                "closed_at",
                "notes",
            ],
        )
        writer.writeheader()
        for assessment in assessments:
            for finding in assessment.findings:
                writer.writerow(
                    {
                        "status": "open",
                        "owner": assessment.owner,
                        "wave": wave_by_workload.get(assessment.workload_id, "Unassigned"),
                        "workload_id": assessment.workload_id,
                        "workload_name": assessment.name,
                        "target": assessment.target,
                        "readiness": assessment.readiness,
                        "risk_score": assessment.risk_score,
                        "severity": finding.severity,
                        "finding_code": finding.code,
                        "recommended_action": finding.recommended_action,
                        "evidence_ref": f"assessment.json#{assessment.workload_id}/{finding.code}",
                        "closure_ref": "",
                        "closed_by": "",
                        "closed_at": "",
                        "notes": "",
                    }
                )


def write_migration_risk_register_csv(assessments: list[WorkloadAssessment], waves: list[Wave], path: Path) -> None:
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    grouped: dict[str, list[tuple[WorkloadAssessment, Any]]] = {}
    for assessment in assessments:
        for finding in assessment.findings:
            grouped.setdefault(finding.code, []).append((assessment, finding))

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "finding_code",
                "highest_severity",
                "affected_workloads",
                "ready",
                "research",
                "prepare",
                "blocked",
                "max_risk_score",
                "owners",
                "waves",
                "workloads",
                "move_staging_blocker",
                "recommended_action",
            ],
        )
        writer.writeheader()
        for finding_code in sorted(grouped, key=lambda code: risk_register_sort_key(code, grouped[code])):
            rows = grouped[finding_code]
            assessments_for_code = [assessment for assessment, _finding in rows]
            summary = summarize(assessments_for_code)
            findings = [_finding for _assessment, _finding in rows]
            highest = highest_severity(findings)
            writer.writerow(
                {
                    "finding_code": finding_code,
                    "highest_severity": highest,
                    "affected_workloads": len({assessment.workload_id for assessment in assessments_for_code}),
                    "ready": summary["ready"],
                    "research": summary["research"],
                    "prepare": summary["prepare"],
                    "blocked": summary["blocked"],
                    "max_risk_score": max(assessment.risk_score for assessment in assessments_for_code),
                    "owners": ";".join(sorted({assessment.owner or "Unassigned" for assessment in assessments_for_code})),
                    "waves": ";".join(sorted({wave_by_workload.get(assessment.workload_id, "Unassigned") for assessment in assessments_for_code})),
                    "workloads": ";".join(sorted({assessment.name for assessment in assessments_for_code})),
                    "move_staging_blocker": "yes" if risk_register_blocks_move(assessments_for_code, highest) else "no",
                    "recommended_action": first_recommended_action(findings),
                }
            )


def risk_register_sort_key(finding_code: str, rows: list[tuple[WorkloadAssessment, Any]]) -> tuple[int, int, str]:
    severities = [finding.severity for _assessment, finding in rows]
    max_risk = max(assessment.risk_score for assessment, _finding in rows)
    return (-severity_rank(highest_severity_value(severities)), -max_risk, finding_code)


def highest_severity(findings: list[Any]) -> str:
    return highest_severity_value([str(finding.severity) for finding in findings])


def highest_severity_value(severities: list[str]) -> str:
    if not severities:
        return "none"
    return max(severities, key=severity_rank)


def severity_rank(severity: str) -> int:
    return {
        "critical": 4,
        "high": 3,
        "medium": 2,
        "low": 1,
    }.get(str(severity).lower(), 0)


def risk_register_blocks_move(assessments: list[WorkloadAssessment], highest: str) -> bool:
    return any(assessment.readiness in {"prepare", "blocked"} for assessment in assessments) or severity_rank(highest) >= 3


def first_recommended_action(findings: list[Any]) -> str:
    if not findings:
        return ""
    return str(findings[0].recommended_action)


def write_owner_risk_summary_csv(assessments: list[WorkloadAssessment], waves: list[Wave], path: Path) -> None:
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    by_owner: dict[str, list[WorkloadAssessment]] = {}
    for assessment in assessments:
        by_owner.setdefault(assessment.owner or "Unassigned", []).append(assessment)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "owner",
                "total_workloads",
                "ready",
                "research",
                "prepare",
                "blocked",
                "average_risk_score",
                "max_risk_score",
                "open_findings",
                "critical_findings",
                "high_findings",
                "medium_findings",
                "blocked_workloads",
                "waves",
                "next_action",
            ],
        )
        writer.writeheader()
        for owner in sorted(by_owner):
            owner_assessments = by_owner[owner]
            summary = summarize(owner_assessments)
            findings = [finding for assessment in owner_assessments for finding in assessment.findings]
            blocked_names = [
                assessment.name
                for assessment in owner_assessments
                if assessment.readiness in {"prepare", "blocked"}
            ]
            waves_for_owner = sorted(
                {
                    wave_by_workload.get(assessment.workload_id, "Unassigned")
                    for assessment in owner_assessments
                }
            )
            writer.writerow(
                {
                    "owner": owner,
                    "total_workloads": summary["total"],
                    "ready": summary["ready"],
                    "research": summary["research"],
                    "prepare": summary["prepare"],
                    "blocked": summary["blocked"],
                    "average_risk_score": round(
                        sum(assessment.risk_score for assessment in owner_assessments) / len(owner_assessments),
                        2,
                    ),
                    "max_risk_score": max(assessment.risk_score for assessment in owner_assessments),
                    "open_findings": len(findings),
                    "critical_findings": severity_count(findings, "critical"),
                    "high_findings": severity_count(findings, "high"),
                    "medium_findings": severity_count(findings, "medium"),
                    "blocked_workloads": ";".join(blocked_names),
                    "waves": ";".join(waves_for_owner),
                    "next_action": owner_next_action(summary, findings),
                }
            )


def write_business_impact_summary_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    by_tier: dict[str, list[WorkloadAssessment]] = {}
    for assessment in assessments:
        workload = workloads.get(assessment.workload_id, {})
        tier = normalized_tier(workload.get("tier"))
        by_tier.setdefault(tier, []).append(assessment)

    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "tier",
                "total_workloads",
                "ready",
                "research",
                "prepare",
                "blocked",
                "average_risk_score",
                "max_risk_score",
                "open_findings",
                "critical_findings",
                "high_findings",
                "move_staging_status",
                "affected_owners",
                "held_workloads",
                "waves",
                "executive_summary",
            ],
        )
        writer.writeheader()
        for tier in sorted(by_tier, key=tier_sort_key):
            tier_assessments = by_tier[tier]
            summary = summarize(tier_assessments)
            findings = [finding for assessment in tier_assessments for finding in assessment.findings]
            held_workloads = [
                assessment.name
                for assessment in tier_assessments
                if assessment.readiness in {"prepare", "blocked"}
            ]
            writer.writerow(
                {
                    "tier": tier,
                    "total_workloads": summary["total"],
                    "ready": summary["ready"],
                    "research": summary["research"],
                    "prepare": summary["prepare"],
                    "blocked": summary["blocked"],
                    "average_risk_score": average_risk_score(tier_assessments),
                    "max_risk_score": max((assessment.risk_score for assessment in tier_assessments), default=0),
                    "open_findings": len(findings),
                    "critical_findings": severity_count(findings, "critical"),
                    "high_findings": severity_count(findings, "high"),
                    "move_staging_status": business_impact_status(summary, findings),
                    "affected_owners": ";".join(sorted({assessment.owner or "Unassigned" for assessment in tier_assessments})),
                    "held_workloads": ";".join(held_workloads),
                    "waves": ";".join(sorted({wave_by_workload.get(assessment.workload_id, "Unassigned") for assessment in tier_assessments})),
                    "executive_summary": business_impact_summary(tier, summary, held_workloads, findings),
                }
            )


def normalized_tier(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text or "unknown"


def tier_sort_key(tier: str) -> tuple[int, str]:
    return (
        {
            "critical": 0,
            "tier-0": 1,
            "tier-1": 2,
            "high": 3,
            "medium": 4,
            "noncritical": 5,
            "low": 6,
            "unknown": 99,
        }.get(tier, 50),
        tier,
    )


def business_impact_status(summary: dict[str, int], findings: list[Any]) -> str:
    if summary["blocked"] or severity_count(findings, "critical"):
        return "blocked"
    if summary["prepare"] or severity_count(findings, "high"):
        return "remediate"
    if summary["research"]:
        return "review"
    return "ready"


def business_impact_summary(tier: str, summary: dict[str, int], held_workloads: list[str], findings: list[Any]) -> str:
    if summary["blocked"]:
        return f"{tier} tier has blocked workloads; clear {', '.join(held_workloads)} before executive migration approval."
    if summary["prepare"]:
        return f"{tier} tier requires remediation before Move staging."
    if severity_count(findings, "high") or severity_count(findings, "critical"):
        return f"{tier} tier has high-severity readiness findings requiring owner acceptance."
    if summary["research"]:
        return f"{tier} tier requires compatibility research before scheduling."
    return f"{tier} tier is ready for owner signoff and controlled staging."


def severity_count(findings: list[Any], severity: str) -> int:
    return sum(1 for finding in findings if finding.severity == severity)


def owner_next_action(summary: dict[str, int], findings: list[Any]) -> str:
    if summary["blocked"]:
        return "Clear blocked workload findings before Move staging."
    if summary["prepare"]:
        return "Close remediation tracker rows and re-run assessment."
    if findings:
        return "Review research findings with application owner."
    return "Confirm owner approval, backup proof, and validation plan."


def write_owner_signoff_matrix_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "status",
                "owner",
                "wave",
                "workload_id",
                "workload_name",
                "target",
                "readiness",
                "risk_score",
                "required_signoffs",
                "blocking_reason",
                "approval_due",
                "evidence_refs",
                "approval_ref",
                "approved_by",
                "approved_at",
                "notes",
            ],
        )
        writer.writeheader()
        for assessment in assessments:
            workload = workloads.get(assessment.workload_id, {})
            dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
            signoffs = required_signoffs(assessment, workload, dependencies)
            writer.writerow(
                {
                    "status": "pending",
                    "owner": assessment.owner,
                    "wave": wave_by_workload.get(assessment.workload_id, "Unassigned"),
                    "workload_id": assessment.workload_id,
                    "workload_name": assessment.name,
                    "target": assessment.target,
                    "readiness": assessment.readiness,
                    "risk_score": assessment.risk_score,
                    "required_signoffs": ";".join(signoffs),
                    "blocking_reason": signoff_blocking_reason(assessment),
                    "approval_due": signoff_due(assessment),
                    "evidence_refs": ";".join(
                        [
                            f"assessment.json#{assessment.workload_id}",
                            f"nutanix-move-plan.csv#{assessment.workload_id}",
                            f"pre-post-validation-checklist.md#{assessment.workload_id}",
                        ]
                    ),
                    "approval_ref": "",
                    "approved_by": "",
                    "approved_at": "",
                    "notes": "",
                }
            )


def required_signoffs(
    assessment: WorkloadAssessment,
    workload: dict[str, Any],
    dependencies: list[Any],
) -> list[str]:
    signoffs = ["application_owner", "migration_lead", "rollback_owner"]
    backup = workload.get("backup") if isinstance(workload.get("backup"), dict) else {}
    networking = workload.get("networking") if isinstance(workload.get("networking"), dict) else {}
    storage = workload.get("storage") if isinstance(workload.get("storage"), dict) else {}
    severities = {finding.severity for finding in assessment.findings}
    codes = {finding.code for finding in assessment.findings}
    if assessment.readiness in {"prepare", "blocked"} or severities & {"critical", "high"}:
        signoffs.append("risk_acceptance")
    if dependencies:
        signoffs.append("dependency_owner")
    if not backup.get("protected") or "backup_not_confirmed" in codes:
        signoffs.append("backup_owner")
    if networking.get("uses_nsx") or networking.get("uses_vds"):
        signoffs.append("network_owner")
    if storage.get("raw_device_mapping") or storage.get("shared_disk") or storage.get("independent_disk") or "datastore_free_space_low" in codes:
        signoffs.append("storage_owner")
    if assessment.target == "nc2":
        signoffs.append("cloud_owner")
    return sorted(set(signoffs))


def signoff_blocking_reason(assessment: WorkloadAssessment) -> str:
    if assessment.readiness == "blocked":
        return "blocked workload requires remediation and formal risk acceptance"
    if assessment.readiness == "prepare":
        return "remediation must close before owner approval"
    if assessment.readiness == "research":
        return "research findings require application owner acceptance"
    return "owner approval required before Move staging"


def signoff_due(assessment: WorkloadAssessment) -> str:
    if assessment.readiness in {"blocked", "prepare"}:
        return "before remediation closure"
    if assessment.readiness == "research":
        return "before wave scheduling"
    return "before Move staging"


def write_move_plan_csv(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "schema_version",
                "include_in_move_plan",
                "wave",
                "source_vm_id",
                "source_vm_name",
                "owner",
                "target",
                "readiness",
                "risk_score",
                "target_networks",
                "dependency_count",
                "application_owner_approval",
                "rollback_owner",
                "precheck_status",
                "required_actions",
            ],
        )
        writer.writeheader()
        for assessment in assessments:
            workload = workloads.get(assessment.workload_id, {})
            networking = workload.get("networking") if isinstance(workload.get("networking"), dict) else {}
            dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
            governance = workload.get("governance") if isinstance(workload.get("governance"), dict) else {}
            include = assessment.readiness in {"ready", "research"}
            writer.writerow(
                {
                    "schema_version": MOVE_PLAN_SCHEMA_VERSION,
                    "include_in_move_plan": "yes" if include else "no",
                    "wave": wave_by_workload.get(assessment.workload_id, "Unassigned"),
                    "source_vm_id": assessment.workload_id,
                    "source_vm_name": assessment.name,
                    "owner": assessment.owner,
                    "target": assessment.target,
                    "readiness": assessment.readiness,
                    "risk_score": assessment.risk_score,
                    "target_networks": ";".join(str(item) for item in networking.get("vlans", [])),
                    "dependency_count": len(dependencies),
                    "application_owner_approval": governance_status(governance.get("application_owner_approved")),
                    "rollback_owner": str(governance.get("rollback_owner") or "").strip() or "not confirmed",
                    "precheck_status": "ready_for_move_staging" if include else "hold_until_remediated",
                    "required_actions": "; ".join(finding.code for finding in assessment.findings),
                }
            )


def write_evidence_markdown(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    source = redact_dict(inventory.get("source", {}))
    summary = summarize(assessments)
    lines = [
        "# Change Board Evidence",
        "",
        "## Executive Summary",
        "",
        f"- Total workloads assessed: {summary['total']}",
        f"- Ready: {summary['ready']}",
        f"- Research required: {summary['research']}",
        f"- Remediation required: {summary['prepare']}",
        f"- Blocked: {summary['blocked']}",
        f"- Unmatched dependency records: {len(inventory.get('unmatched_dependencies', []))}",
        "",
        "## Source",
        "",
        "```json",
        json.dumps(source, indent=2),
        "```",
        "",
        "## Collection Audit Proof",
        "",
        *collection_audit_markdown_lines(source),
        "",
        "## Migration Waves",
        "",
    ]
    for wave in waves:
        lines.append(f"### {wave.name}")
        lines.append("")
        lines.append(wave.description)
        lines.append("")
        for workload_id in wave.workload_ids:
            assessment = next(item for item in assessments if item.workload_id == workload_id)
            lines.append(
                f"- {assessment.workload_id}: {assessment.name} "
                f"({assessment.readiness}, risk {assessment.risk_score})"
            )
        lines.append("")

    lines.extend(["## Readiness Findings", ""])
    for assessment in assessments:
        lines.append(f"### {assessment.workload_id} - {assessment.name}")
        lines.append("")
        lines.append(f"- Owner: {assessment.owner}")
        lines.append(f"- Target: {assessment.target}")
        lines.append(f"- Readiness: {assessment.readiness}")
        lines.append(f"- Risk score: {assessment.risk_score}")
        workload = next(
            (
                item
                for item in inventory.get("workloads", [])
                if isinstance(item, dict) and str(item.get("id") or item.get("name")) == assessment.workload_id
            ),
            {},
        )
        dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
        lines.append(f"- Dependencies: {len(dependencies)}")
        if assessment.findings:
            for finding in assessment.findings:
                lines.append(f"- [{finding.severity}] {finding.code}: {finding.message}")
                lines.append(f"  Action: {finding.recommended_action}")
        else:
            lines.append("- No readiness findings.")
        lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def write_executive_readiness_brief(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    summary = summarize(assessments)
    ready_names = [assessment.name for assessment in assessments if assessment.readiness in {"ready", "research"}]
    held_names = [assessment.name for assessment in assessments if assessment.readiness in {"prepare", "blocked"}]
    decision = executive_decision(summary)
    lines = [
        "# Executive Readiness Brief",
        "",
        "## Decision Ask",
        "",
        f"- Recommended decision: {decision}",
        f"- Workloads assessed: {summary['total']}",
        f"- Move staging candidates: {len(ready_names)}",
        f"- Held workloads: {len(held_names)}",
        f"- Blocked workloads: {summary['blocked']}",
        f"- Remediation required: {summary['prepare']}",
        "",
        "## Migration Posture",
        "",
        f"- Ready: {summary['ready']}",
        f"- Research required: {summary['research']}",
        f"- Prepare/remediate: {summary['prepare']}",
        f"- Blocked: {summary['blocked']}",
        f"- Unmatched dependency records: {len(inventory.get('unmatched_dependencies', []))}",
        "",
        "## Business Impact",
        "",
        *executive_business_impact_lines(inventory, assessments, waves),
        "",
        "## Wave Decisions",
        "",
        *executive_wave_lines(assessments, waves),
        "",
        "## Top Blockers",
        "",
        *executive_blocker_lines(assessments),
        "",
        "## Required Evidence Before Approval",
        "",
        "- Evidence bundle verifies with `evidence-manifest.json`.",
        "- Redaction review has no findings.",
        "- Remediation tracker rows are closed or formally accepted.",
        "- Owner sign-offs, rollback ownership, backup proof, and operator review are approved.",
        "- Approved Nutanix Move lab appliance proof is supplied before final production handoff.",
        "",
        "## Generated Evidence",
        "",
        "- `business-impact-summary.csv`",
        "- `wave-readiness-summary.csv`",
        "- `compatibility-research.csv`",
        "- `dependency-review.csv`",
        "- `connectivity-checklist.csv`",
        "- `identity-cutover-plan.csv`",
        "- `tools-driver-readiness.csv`",
        "- `storage-posture.csv`",
        "- `recovery-readiness.csv`",
        "- `rollback-plan.csv`",
        "- `move-staging-readiness.csv`",
        "- `migration-execution-queue.csv`",
        "- `migration-risk-register.csv`",
        "- `owner-risk-summary.csv`",
        "- `approval-exceptions.csv`",
        "- `nutanix-move-plan.csv`",
        "- `move-plan-brief.md`",
        "- `workload-validation-checklist.csv`",
        "- `operator-gate-summary.md` when generated by `run-assessment`",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def executive_decision(summary: dict[str, int]) -> str:
    if summary["blocked"]:
        return "Do not approve broad Move staging; clear blocked workloads or approve a limited pilot only."
    if summary["prepare"]:
        return "Approve only ready pilot workloads; hold remediation workloads until closure evidence is supplied."
    if summary["research"]:
        return "Approve conditional planning while compatibility research and owner sign-offs are completed."
    return "Approve controlled Move staging after owner sign-off and final precheck evidence."


def executive_business_impact_lines(inventory: dict[str, Any], assessments: list[WorkloadAssessment], waves: list[Wave]) -> list[str]:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    by_tier: dict[str, list[WorkloadAssessment]] = {}
    for assessment in assessments:
        by_tier.setdefault(normalized_tier(workloads.get(assessment.workload_id, {}).get("tier")), []).append(assessment)

    lines: list[str] = []
    for tier in sorted(by_tier, key=tier_sort_key):
        tier_assessments = by_tier[tier]
        tier_summary = summarize(tier_assessments)
        findings = [finding for assessment in tier_assessments for finding in assessment.findings]
        held = [assessment.name for assessment in tier_assessments if assessment.readiness in {"prepare", "blocked"}]
        lines.append(
            f"- {tier}: {tier_summary['total']} workloads, status `{business_impact_status(tier_summary, findings)}`, "
            f"held `{'; '.join(held) or 'none'}`."
        )
    return lines or ["- No workload tiers were captured."]


def executive_wave_lines(assessments: list[WorkloadAssessment], waves: list[Wave]) -> list[str]:
    assessments_by_id = {assessment.workload_id: assessment for assessment in assessments}
    lines: list[str] = []
    for wave in waves:
        wave_assessments = [assessments_by_id[workload_id] for workload_id in wave.workload_ids if workload_id in assessments_by_id]
        summary = summarize(wave_assessments)
        findings = [finding for assessment in wave_assessments for finding in assessment.findings]
        held = [assessment.name for assessment in wave_assessments if assessment.readiness in {"prepare", "blocked"}]
        lines.append(
            f"- {wave.name}: {summary['total']} workloads, staging `{wave_move_staging_status(summary, findings)}`, "
            f"held `{'; '.join(held) or 'none'}`."
        )
    return lines or ["- No migration waves were generated."]


def executive_blocker_lines(assessments: list[WorkloadAssessment]) -> list[str]:
    rows = [
        (severity_rank(finding.severity), assessment.risk_score, finding.code, finding.severity, assessment.name, finding.recommended_action)
        for assessment in assessments
        for finding in assessment.findings
    ]
    if not rows:
        return ["- No readiness blockers were detected."]
    lines = []
    for _severity_rank, _risk_score, code, severity, workload_name, action in sorted(rows, reverse=True)[:5]:
        lines.append(f"- [{severity}] {code} on {workload_name}: {action}")
    return lines


def write_migration_runbook(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    assessments_by_id = {assessment.workload_id: assessment for assessment in assessments}
    lines = [
        "# Migration Runbook",
        "",
        "## Purpose",
        "",
        "This runbook converts readiness evidence into operator actions for VMware-to-Nutanix migration planning. It is generated locally from the current assessment and must be reviewed before execution.",
        "",
        "## Universal Stop Conditions",
        "",
        "- Stop if a workload marked `prepare` or `blocked` appears in a Move execution list.",
        "- Stop if backup proof, rollback owner, or application owner approval is missing.",
        "- Stop if NSX, firewall, DNS, IPAM, load-balancer, or dependency mapping is unresolved.",
        "- Stop if the operator cannot verify the generated evidence bundle checksum.",
        "",
        "## Wave Execution Plan",
        "",
    ]

    for wave in waves:
        lines.append(f"### {wave.name}")
        lines.append("")
        lines.append(wave.description)
        lines.append("")
        for position, workload_id in enumerate(wave.workload_ids, start=1):
            assessment = assessments_by_id[workload_id]
            workload = workloads.get(workload_id, {})
            lines.extend(runbook_workload_lines(position, assessment, workload))
        lines.append("")

    lines.extend(
        [
            "## Evidence Handoff",
            "",
            "- Attach `assessment.json`, `migration-waves.csv`, `wave-readiness-summary.csv`, `compatibility-research.csv`, `dependency-sequence.csv`, `dependency-review.csv`, `connectivity-checklist.csv`, `identity-cutover-plan.csv`, `tools-driver-readiness.csv`, `storage-posture.csv`, `recovery-readiness.csv`, `rollback-plan.csv`, `move-staging-readiness.csv`, `move-staging-brief.md`, `move-plan-brief.md`, `workload-validation-checklist.csv`, `migration-execution-queue.csv`, `remediation-tracker.csv`, `migration-risk-register.csv`, `owner-risk-summary.csv`, `business-impact-summary.csv`, `owner-signoff-matrix.csv`, `approval-exceptions.csv`, `what-will-break-brief.md`, `nutanix-move-plan.csv`, `executive-readiness-brief.md`, `change-board-evidence.md`, `migration-runbook.md`, `operator-report.html`, `operator-dashboard.html`, `pre-post-validation-checklist.md`, `source-endpoint-evidence-request.md`, `move-lab-closure-checklist.md`, `move-lab-evidence-request.md`, and `evidence-manifest.json` to the approved change workspace.",
            "- Package the evidence bundle and verify it before handoff.",
            "- Keep raw inventory and RVTools exports inside the approved migration workspace.",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def runbook_workload_lines(position: int, assessment: WorkloadAssessment, workload: dict[str, Any]) -> list[str]:
    dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
    networking = workload.get("networking") if isinstance(workload.get("networking"), dict) else {}
    governance = workload.get("governance") if isinstance(workload.get("governance"), dict) else {}
    include = assessment.readiness in {"ready", "research"}
    owner_approval = governance_status(governance.get("application_owner_approved"))
    rollback_owner = str(governance.get("rollback_owner") or "").strip() or "not confirmed"
    lines = [
        f"#### {position}. {assessment.name}",
        "",
        f"- Source VM ID: `{assessment.workload_id}`",
        f"- Owner: {assessment.owner}",
        f"- Target: {assessment.target}",
        f"- Readiness: `{assessment.readiness}`",
        f"- Risk score: {assessment.risk_score}",
        f"- Move staging: {'include after review' if include else 'hold until remediated'}",
        f"- Target network hints: {', '.join(str(item) for item in networking.get('vlans', [])) or 'not captured'}",
        f"- Dependency count: {len(dependencies)}",
        f"- Application owner approval: {owner_approval}",
        f"- Rollback owner: {rollback_owner}",
        "",
        "Required actions:",
    ]
    if assessment.findings:
        for finding in assessment.findings:
            lines.append(f"- [{finding.severity}] {finding.code}: {finding.recommended_action}")
    else:
        lines.append("- Confirm owner approval, backup proof, rollback criteria, and post-cutover health checks.")
    lines.extend(["", "Operator checks:", "- Confirm this workload is in the approved wave."])
    if include:
        lines.append("- Confirm final sync/precheck status in Nutanix Move before cutover.")
    else:
        lines.append("- Do not stage this workload in Nutanix Move until all required actions are cleared.")
        lines.append("- Re-run assessment after remediation and verify the workload leaves hold state.")
    if dependencies:
        lines.extend(["", "Dependency coordination:"])
        for dependency in dependencies:
            if not isinstance(dependency, dict):
                continue
            lines.append(
                "- "
                + "; ".join(
                    [
                        f"name={str(dependency.get('name') or 'unknown')}",
                        f"type={str(dependency.get('type') or 'unspecified')}",
                        f"owner={str(dependency.get('owner') or 'not assigned')}",
                        f"criticality={str(dependency.get('criticality') or 'unspecified')}",
                    ]
                )
            )
    lines.extend(["- Record pre-cutover and post-cutover evidence in the change workspace.", ""])
    return lines


def governance_status(value: Any) -> str:
    if value is True:
        return "confirmed"
    if value is False:
        return "not confirmed"
    return "not supplied"


def write_html_report(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    source = redact_dict(inventory.get("source", {}))
    summary = summarize(assessments)
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    workload_records = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    cards = "\n".join(
        [
            f"""
            <article class="workload {escape(assessment.readiness)}">
              <div>
                <h3>{escape(assessment.name)}</h3>
                <p>{escape(assessment.workload_id)} - {escape(assessment.owner)} - {escape(wave_by_workload.get(assessment.workload_id, "Unassigned"))}</p>
              </div>
              <div class="score">{assessment.risk_score}</div>
              <dl>
                <dt>Readiness</dt><dd>{escape(assessment.readiness)}</dd>
                <dt>Target</dt><dd>{escape(assessment.target)}</dd>
                <dt>Dependencies</dt><dd>{dependency_count(workload_records.get(assessment.workload_id, {}))}</dd>
              </dl>
              <ul>
                {finding_items(assessment)}
              </ul>
            </article>
            """
            for assessment in assessments
        ]
    )
    wave_sections = "\n".join(
        [
            f"""
            <section class="wave">
              <h3>{escape(wave.name)}</h3>
              <p>{escape(wave.description)}</p>
              <p class="ids">{escape(", ".join(wave.workload_ids))}</p>
            </section>
            """
            for wave in waves
        ]
    )
    collection_audit = collection_audit_html(source)
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NMRCP Operator Report</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #16202a;
      --muted: #5b6673;
      --line: #d9dee5;
      --panel: #f7f9fb;
      --ready: #1f7a4d;
      --research: #85620e;
      --prepare: #a24d16;
      --blocked: #a12828;
    }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: white;
    }}
    header {{
      padding: 32px 40px 22px;
      border-bottom: 1px solid var(--line);
    }}
    h1, h2, h3, p {{
      margin-top: 0;
    }}
    h1 {{
      font-size: 30px;
      margin-bottom: 8px;
    }}
    h2 {{
      font-size: 20px;
      margin-bottom: 14px;
    }}
    main {{
      padding: 26px 40px 40px;
      display: grid;
      gap: 28px;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
      gap: 12px;
    }}
    .metric, .wave, .workload, pre {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
    }}
    .metric {{
      padding: 16px;
    }}
    .metric strong {{
      display: block;
      font-size: 28px;
    }}
    .metric span, header p, .workload p, .wave p, dt {{
      color: var(--muted);
    }}
    .workloads {{
      display: grid;
      gap: 14px;
    }}
    .workload {{
      padding: 16px;
      border-left-width: 6px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px 18px;
    }}
    .workload.ready {{ border-left-color: var(--ready); }}
    .workload.research {{ border-left-color: var(--research); }}
    .workload.prepare {{ border-left-color: var(--prepare); }}
    .workload.blocked {{ border-left-color: var(--blocked); }}
    .score {{
      width: 54px;
      height: 54px;
      border-radius: 50%;
      border: 1px solid var(--line);
      display: grid;
      place-items: center;
      font-size: 20px;
      font-weight: 700;
      background: white;
    }}
    dl {{
      grid-column: 1 / -1;
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
      gap: 8px 14px;
      margin: 0;
    }}
    dd {{
      margin: 2px 0 0;
      font-weight: 700;
    }}
    ul {{
      grid-column: 1 / -1;
      margin: 0;
      padding-left: 18px;
    }}
    li {{
      margin: 6px 0;
    }}
    .waves {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
    }}
    .wave {{
      padding: 16px;
    }}
    .ids {{
      word-break: break-word;
    }}
    pre {{
      padding: 16px;
      overflow: auto;
    }}
    .audit {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 16px;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Nutanix Migration Readiness Operator Report</h1>
    <p>Local, redacted readiness evidence for VMware-to-Nutanix planning. Generated from current assessment artifacts.</p>
  </header>
  <main>
    <section>
      <h2>Executive Summary</h2>
      <div class="summary">
        {metric("Total", summary["total"])}
        {metric("Ready", summary["ready"])}
        {metric("Research", summary["research"])}
        {metric("Prepare", summary["prepare"])}
        {metric("Blocked", summary["blocked"])}
        {metric("Unmatched Dependencies", len(inventory.get("unmatched_dependencies", [])))}
      </div>
    </section>
    <section>
      <h2>Migration Waves</h2>
      <div class="waves">{wave_sections}</div>
    </section>
    <section>
      <h2>Collection Audit Proof</h2>
      {collection_audit}
    </section>
    <section>
      <h2>Workload Readiness</h2>
      <div class="workloads">{cards}</div>
    </section>
    <section>
      <h2>Redacted Source</h2>
      <pre>{escape(json.dumps(source, indent=2))}</pre>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")


def write_operator_dashboard(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    payload = dashboard_payload(inventory, assessments, waves)
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NMRCP Operator Dashboard</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #5f6b78;
      --line: #d8dde5;
      --panel: #f6f8fb;
      --surface: #ffffff;
      --ready: #1f7a4d;
      --research: #7b6114;
      --prepare: #9b4a17;
      --blocked: #a12828;
      --focus: #245c85;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: var(--surface);
    }}
    header {{
      padding: 24px 28px 18px;
      border-bottom: 1px solid var(--line);
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 18px;
      align-items: end;
    }}
    h1, h2, h3, p {{ margin-top: 0; }}
    h1 {{ font-size: 26px; margin-bottom: 6px; }}
    h2 {{ font-size: 18px; margin-bottom: 12px; }}
    h3 {{ font-size: 16px; margin-bottom: 6px; }}
    .muted, .meta, label, th {{ color: var(--muted); }}
    main {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(320px, 420px);
      min-height: calc(100vh - 96px);
    }}
    .workspace {{
      padding: 22px 28px 32px;
      display: grid;
      gap: 20px;
      align-content: start;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(118px, 1fr));
      gap: 10px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: var(--panel);
    }}
    .metric strong {{ display: block; font-size: 24px; }}
    .controls {{
      display: grid;
      grid-template-columns: minmax(180px, 1.2fr) repeat(3, minmax(120px, .8fr));
      gap: 10px;
      align-items: end;
    }}
    label {{ display: grid; gap: 5px; font-size: 12px; font-weight: 700; }}
    input, select {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      background: white;
      color: var(--ink);
    }}
    input:focus, select:focus, button:focus {{
      outline: 2px solid var(--focus);
      outline-offset: 2px;
    }}
    .table-wrap {{
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 780px;
    }}
    th, td {{
      padding: 11px 12px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
    }}
    th {{ font-size: 12px; background: var(--panel); }}
    tr:last-child td {{ border-bottom: 0; }}
    tr.selected {{ background: #edf4f9; }}
    button.row-button {{
      border: 0;
      background: transparent;
      color: var(--focus);
      padding: 0;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      text-align: left;
    }}
    .badge {{
      display: inline-block;
      border-radius: 999px;
      padding: 3px 8px;
      color: white;
      font-size: 12px;
      font-weight: 700;
      text-transform: capitalize;
    }}
    .ready {{ background: var(--ready); }}
    .research {{ background: var(--research); }}
    .prepare {{ background: var(--prepare); }}
    .blocked {{ background: var(--blocked); }}
    aside {{
      border-left: 1px solid var(--line);
      background: var(--panel);
      padding: 22px 22px 32px;
      overflow: auto;
    }}
    .detail {{
      display: grid;
      gap: 16px;
    }}
    .section {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
      padding: 14px;
    }}
    dl {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px 14px;
      margin: 0;
    }}
    dt {{ font-size: 12px; }}
    dd {{ margin: 2px 0 0; font-weight: 700; word-break: break-word; }}
    ul {{
      margin: 0;
      padding-left: 18px;
    }}
    li {{ margin: 7px 0; }}
    .empty {{
      border: 1px dashed var(--line);
      border-radius: 8px;
      padding: 18px;
      color: var(--muted);
    }}
    @media (max-width: 920px) {{
      header, main {{ display: block; }}
      .controls {{ grid-template-columns: 1fr; }}
      aside {{ border-left: 0; border-top: 1px solid var(--line); }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Nutanix Migration Readiness Dashboard</h1>
      <p class="muted">Local operator work queue generated from redacted assessment evidence.</p>
    </div>
    <p class="meta" id="generated"></p>
  </header>
  <main>
    <section class="workspace">
      <section>
        <h2>Readiness Summary</h2>
        <div class="summary" id="summary"></div>
      </section>
      <section class="controls" aria-label="Workload filters">
        <label>Search
          <input id="search" type="search" placeholder="Name, owner, finding, network">
        </label>
        <label>Readiness
          <select id="readiness"></select>
        </label>
        <label>Owner
          <select id="owner"></select>
        </label>
        <label>Wave
          <select id="wave"></select>
        </label>
      </section>
      <section>
        <h2>Operator Work Queue</h2>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Workload</th>
                <th>Owner</th>
                <th>Readiness</th>
                <th>Risk</th>
                <th>Wave</th>
                <th>Move staging</th>
                <th>Top finding</th>
              </tr>
            </thead>
            <tbody id="rows"></tbody>
          </table>
        </div>
      </section>
    </section>
    <aside>
      <div class="detail" id="detail"></div>
    </aside>
  </main>
  <script id="dashboard-data" type="application/json">{script_json(payload)}</script>
  <script>
    const data = JSON.parse(document.getElementById("dashboard-data").textContent);
    const state = {{ selectedId: data.workloads[0]?.id || "" }};
    const fields = {{
      search: document.getElementById("search"),
      readiness: document.getElementById("readiness"),
      owner: document.getElementById("owner"),
      wave: document.getElementById("wave"),
      rows: document.getElementById("rows"),
      detail: document.getElementById("detail"),
      summary: document.getElementById("summary"),
      generated: document.getElementById("generated")
    }};

    function text(value) {{
      return String(value ?? "");
    }}

    function esc(value) {{
      return text(value).replace(/[&<>"']/g, char => ({{
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;"
      }}[char]));
    }}

    function optionList(values) {{
      return ["All", ...Array.from(new Set(values.filter(Boolean))).sort((a, b) => a.localeCompare(b))];
    }}

    function fillSelect(select, values) {{
      select.innerHTML = optionList(values).map(value => `<option value="${{esc(value)}}">${{esc(value)}}</option>`).join("");
    }}

    function init() {{
      fields.generated.textContent = `Generated ${{data.generated_at}}`;
      fillSelect(fields.readiness, data.workloads.map(row => row.readiness));
      fillSelect(fields.owner, data.workloads.map(row => row.owner));
      fillSelect(fields.wave, data.workloads.map(row => row.wave));
      for (const field of [fields.search, fields.readiness, fields.owner, fields.wave]) {{
        field.addEventListener("input", render);
      }}
      render();
    }}

    function filteredRows() {{
      const query = fields.search.value.trim().toLowerCase();
      return data.workloads.filter(row => {{
        const matchesQuery = !query || [
          row.id,
          row.name,
          row.owner,
          row.wave,
          row.readiness,
          row.move_staging,
          row.target,
          row.networks.join(" "),
          row.findings.map(finding => `${{finding.code}} ${{finding.message}} ${{finding.action}}`).join(" ")
        ].join(" ").toLowerCase().includes(query);
        const matchesReadiness = fields.readiness.value === "All" || row.readiness === fields.readiness.value;
        const matchesOwner = fields.owner.value === "All" || row.owner === fields.owner.value;
        const matchesWave = fields.wave.value === "All" || row.wave === fields.wave.value;
        return matchesQuery && matchesReadiness && matchesOwner && matchesWave;
      }});
    }}

    function render() {{
      const rows = filteredRows();
      renderSummary(rows);
      renderRows(rows);
      if (!rows.some(row => row.id === state.selectedId)) {{
        state.selectedId = rows[0]?.id || "";
      }}
      renderDetail(rows.find(row => row.id === state.selectedId) || data.workloads.find(row => row.id === state.selectedId));
    }}

    function renderSummary(rows) {{
      const counts = {{ total: rows.length, ready: 0, research: 0, prepare: 0, blocked: 0 }};
      for (const row of rows) counts[row.readiness] = (counts[row.readiness] || 0) + 1;
      fields.summary.innerHTML = [
        ["Total", counts.total],
        ["Ready", counts.ready],
        ["Research", counts.research],
        ["Prepare", counts.prepare],
        ["Blocked", counts.blocked],
        ["Unmatched dependencies", data.unmatched_dependencies]
      ].map(([label, value]) => `<div class="metric"><strong>${{esc(value)}}</strong><span>${{esc(label)}}</span></div>`).join("");
    }}

    function renderRows(rows) {{
      if (!rows.length) {{
        fields.rows.innerHTML = `<tr><td colspan="7"><div class="empty">No workloads match the current filters.</div></td></tr>`;
        return;
      }}
      fields.rows.innerHTML = rows.map(row => {{
        const topFinding = row.findings[0]?.code || "none";
        return `<tr class="${{row.id === state.selectedId ? "selected" : ""}}">
          <td><button class="row-button" type="button" data-id="${{esc(row.id)}}">${{esc(row.name)}}</button><div class="meta">${{esc(row.id)}}</div></td>
          <td>${{esc(row.owner)}}</td>
          <td><span class="badge ${{esc(row.readiness)}}">${{esc(row.readiness)}}</span></td>
          <td>${{esc(row.risk_score)}}</td>
          <td>${{esc(row.wave)}}</td>
          <td>${{esc(row.move_staging)}}</td>
          <td>${{esc(topFinding)}}</td>
        </tr>`;
      }}).join("");
      for (const button of fields.rows.querySelectorAll("button[data-id]")) {{
        button.addEventListener("click", () => {{
          state.selectedId = button.dataset.id;
          render();
        }});
      }}
    }}

    function renderDetail(row) {{
      if (!row) {{
        fields.detail.innerHTML = `<div class="empty">Select a workload to review readiness evidence.</div>`;
        return;
      }}
      const findingItems = row.findings.length
        ? row.findings.map(finding => `<li><strong>${{esc(finding.severity)}} ${{esc(finding.code)}}:</strong> ${{esc(finding.message)}}<br><span class="muted">${{esc(finding.action)}}</span></li>`).join("")
        : "<li>No readiness findings.</li>";
      fields.detail.innerHTML = `
        <section class="section">
          <h2>${{esc(row.name)}}</h2>
          <p class="muted">${{esc(row.id)}}</p>
          <dl>
            <div><dt>Owner</dt><dd>${{esc(row.owner)}}</dd></div>
            <div><dt>Target</dt><dd>${{esc(row.target)}}</dd></div>
            <div><dt>Readiness</dt><dd>${{esc(row.readiness)}}</dd></div>
            <div><dt>Risk</dt><dd>${{esc(row.risk_score)}}</dd></div>
            <div><dt>Wave</dt><dd>${{esc(row.wave)}}</dd></div>
            <div><dt>Move staging</dt><dd>${{esc(row.move_staging)}}</dd></div>
            <div><dt>Dependencies</dt><dd>${{esc(row.dependency_count)}}</dd></div>
            <div><dt>Networks</dt><dd>${{esc(row.networks.join(", ") || "not captured")}}</dd></div>
          </dl>
        </section>
        <section class="section">
          <h2>Required Actions</h2>
          <ul>${{findingItems}}</ul>
        </section>
        <section class="section">
          <h2>Operator Stop Conditions</h2>
          <ul>
            <li>Do not stage prepare or blocked workloads in Nutanix Move.</li>
            <li>Confirm owner approval, backup proof, rollback owner, and network mapping before cutover.</li>
            <li>Re-run assessment after remediation and verify the readiness state changes.</li>
          </ul>
        </section>`;
    }}

    init();
  </script>
</body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")


def dashboard_payload(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
) -> dict[str, Any]:
    wave_by_workload = {
        workload_id: wave.name
        for wave in waves
        for workload_id in wave.workload_ids
    }
    workloads = {
        str(workload.get("id") or workload.get("name")): workload
        for workload in inventory.get("workloads", [])
        if isinstance(workload, dict)
    }
    rows: list[dict[str, Any]] = []
    for assessment in assessments:
        workload = workloads.get(assessment.workload_id, {})
        networking = workload.get("networking") if isinstance(workload.get("networking"), dict) else {}
        dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
        include = assessment.readiness in {"ready", "research"}
        rows.append(
            {
                "id": assessment.workload_id,
                "name": assessment.name,
                "owner": assessment.owner,
                "target": assessment.target,
                "readiness": assessment.readiness,
                "risk_score": assessment.risk_score,
                "wave": wave_by_workload.get(assessment.workload_id, "Unassigned"),
                "move_staging": "include after review" if include else "hold until remediated",
                "dependency_count": len(dependencies),
                "networks": [str(item) for item in networking.get("vlans", [])],
                "findings": [
                    {
                        "severity": finding.severity,
                        "code": finding.code,
                        "message": finding.message,
                        "action": finding.recommended_action,
                    }
                    for finding in assessment.findings
                ],
            }
        )
    return {
        "schema_version": "nmrcp_operator_dashboard_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "summary": summarize(assessments),
        "unmatched_dependencies": len(inventory.get("unmatched_dependencies", [])),
        "workloads": rows,
    }


def script_json(payload: dict[str, Any]) -> str:
    return (
        json.dumps(payload, separators=(",", ":"), ensure_ascii=True)
        .replace("<", "\\u003c")
        .replace(">", "\\u003e")
        .replace("&", "\\u0026")
    )


def collection_audit_markdown_lines(source: dict[str, Any]) -> list[str]:
    audit = source.get("collection_audit") if isinstance(source.get("collection_audit"), dict) else {}
    if not audit:
        return ["- Collection audit metadata: not provided"]
    lines = [
        f"- Schema: `{audit.get('schema', 'unknown')}`",
        f"- Mode: `{audit.get('mode', source.get('mode', 'unknown'))}`",
        f"- Credential storage: `{audit.get('credential_storage', 'unknown')}`",
        f"- Endpoint configured: `{audit.get('endpoint_configured', 'unknown')}`",
        f"- Mutating calls: `{audit.get('mutating_calls', 'unknown')}`",
    ]
    if audit.get("api_paths"):
        lines.append(f"- Read-only API paths: {', '.join(str(path) for path in audit.get('api_paths', []))}")
    if "post_paths_allowlisted" in audit:
        lines.append(f"- POST paths allow-listed: `{audit.get('post_paths_allowlisted')}`")
    for key, label in (
        ("summary_count", "Summary records"),
        ("details_limit", "Detail limit"),
        ("details_count", "Detail records"),
        ("page_size", "Page size"),
        ("max_pages", "Max pages"),
        ("entities_count", "Entities returned"),
        ("workloads_count", "Workloads imported"),
    ):
        if key in audit:
            lines.append(f"- {label}: `{audit[key]}`")
    if audit.get("files_observed"):
        lines.append(f"- Files observed: {', '.join(str(item) for item in audit.get('files_observed', []))}")
    return lines


def collection_audit_html(source: dict[str, Any]) -> str:
    lines = collection_audit_markdown_lines(source)
    items = "\n".join(f"<li>{escape(line.removeprefix('- '))}</li>" for line in lines)
    return f'<div class="audit"><ul>{items}</ul></div>'


def metric(label: str, value: int) -> str:
    return f'<div class="metric"><strong>{value}</strong><span>{escape(label)}</span></div>'


def finding_items(assessment: WorkloadAssessment) -> str:
    if not assessment.findings:
        return "<li>No readiness findings.</li>"
    return "\n".join(
        f"<li><strong>{escape(finding.severity)} - {escape(finding.code)}</strong>: "
        f"{escape(finding.message)} Action: {escape(finding.recommended_action)}</li>"
        for finding in assessment.findings
    )


def dependency_count(workload: dict[str, Any]) -> int:
    dependencies = workload.get("dependencies") if isinstance(workload.get("dependencies"), list) else []
    return len(dependencies)


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def write_evidence_manifest(path: Path, out_dir: Path) -> None:
    artifact_paths = sorted(
        item
        for item in out_dir.iterdir()
        if item.is_file() and item.name != path.name
    )
    manifest = {
        "schema_version": "nmrcp_evidence_manifest_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "artifacts": [
            {
                "name": artifact.name,
                "size_bytes": artifact.stat().st_size,
                "sha256": sha256_file(artifact),
            }
            for artifact in artifact_paths
        ],
    }
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_validation_checklist(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "# Pre/Post Migration Validation Checklist",
                "",
                "## Pre-Migration",
                "",
                "- Confirm source VM owner and application owner.",
                "- Confirm recent recoverable backup and restore point.",
                "- Confirm guest OS and application vendor support for target.",
                "- Confirm network mapping, VLAN, IPAM, DNS, firewall, and load-balancer dependencies.",
                "- Confirm snapshots are removed or consolidated.",
                "- Confirm Nutanix VirtIO readiness where required.",
                "- Confirm migration window, rollback owner, and rollback stop condition.",
                "- Export preflight evidence pack and attach it to the change request.",
                "",
                "## Cutover",
                "",
                "- Capture source VM power state and final sync status.",
                "- Execute migration only for workloads cleared for the selected wave.",
                "- Stop if an excluded or blocked workload appears in the execution list.",
                "- Record start time, operator, source, target, and migration tool run identifier.",
                "",
                "## Post-Migration",
                "",
                "- Confirm VM power state, IP configuration, DNS, time sync, and tools/drivers.",
                "- Confirm application health check from the application owner.",
                "- Confirm backup policy on target.",
                "- Confirm monitoring, alerting, and log collection on target.",
                "- Capture post-cutover evidence and close or roll back per change criteria.",
            ]
        ),
        encoding="utf-8",
    )
