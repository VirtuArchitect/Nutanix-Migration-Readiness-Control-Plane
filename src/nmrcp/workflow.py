from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .capacity import validate_capacity_fit, write_capacity_fit_csv
from .change_gate import run_change_gate
from .dependencies import apply_dependency_readiness_gates, merge_dependencies, read_dependency_csv
from .evidence import write_assessment
from .evidence import write_evidence_manifest
from .evidence_bundle import package_evidence, verify_evidence
from .handoff_package import package_handoff, verify_handoff_package
from .gate_summary import write_operator_gate_summary
from .inventory_validation import validate_inventory
from .metadata import merge_metadata, read_metadata_csv
from .move_plan import validate_move_plan
from .move_payload import build_move_payload
from .network_mapping import validate_network_mappings, write_network_mapping_csv
from .redaction_review import review_evidence_dir
from .scoring import assess_inventory, load_readiness_policy
from .source_networks import validate_source_networks, write_source_network_validation_csv
from .target_reconciliation import reconcile_target_inventory, write_target_reconciliation_csv
from .validation_results import write_validation_template
from .waves import plan_waves


@dataclass(frozen=True)
class WorkflowPaths:
    assessment_dir: Path
    validation_template: Path
    evidence_bundle: Path
    handoff_package: Path
    move_payload: Path | None


def run_assessment_workflow(
    inventory_path: Path,
    out_dir: Path,
    metadata_path: Path | None = None,
    dependencies_path: Path | None = None,
    source: str = "vmware_vcenter",
    target: str = "ahv",
    policy_path: Path | None = None,
    capacity_path: Path | None = None,
    prism_inventory_path: Path | None = None,
    source_networks_path: Path | None = None,
    strict_inventory: bool = False,
    move_config_path: Path | None = None,
    validation_results_path: Path | None = None,
    remediation_tracker_path: Path | None = None,
    signoffs_path: Path | None = None,
    approval_exceptions_path: Path | None = None,
    operator_review_path: Path | None = None,
    move_lab_capture_kit_dir: Path | None = None,
    move_lab_capture_validation_path: Path | None = None,
    move_lab_proof_path: Path | None = None,
    move_lab_readiness_packet_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
    validation_template_out: Path | None = None,
    bundle_out: Path | None = None,
    handoff_out: Path | None = None,
    move_payload_out: Path | None = None,
) -> dict[str, Any]:
    paths = workflow_paths(
        out_dir,
        validation_template_out=validation_template_out,
        bundle_out=bundle_out,
        handoff_out=handoff_out,
        move_payload_out=move_payload_out or (out_dir / "move-api-payload.dry-run.json" if move_config_path else None),
    )
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    if metadata_path:
        inventory = merge_metadata(inventory, read_metadata_csv(metadata_path))
    if dependencies_path:
        inventory = merge_dependencies(inventory, read_dependency_csv(dependencies_path))

    inventory_result = validate_inventory(inventory)
    if not inventory_result.ok or (strict_inventory and inventory_result.warnings):
        return workflow_result(
            "fail",
            paths,
            checks=[
                {
                    "name": "inventory-validation",
                    "status": "fail",
                    "detail": inventory_result.summary(),
                    "errors": list(inventory_result.errors),
                    "warnings": list(inventory_result.warnings),
                }
            ],
        )

    policy = load_readiness_policy(policy_path)
    assessments = assess_inventory(inventory, source=source, target=target, policy=policy)
    assessments = apply_dependency_readiness_gates(inventory, assessments)
    waves = plan_waves(assessments, inventory)
    write_assessment(inventory, assessments, waves, out_dir, policy=policy.to_dict())
    write_validation_template(out_dir / "nutanix-move-plan.csv", paths.validation_template)

    checks: list[dict[str, Any]] = [
        {
            "name": "inventory-validation",
            "status": "pass",
            "detail": inventory_result.summary(),
            "warnings": list(inventory_result.warnings),
        }
    ]

    move_plan_result = validate_move_plan(out_dir / "nutanix-move-plan.csv", out_dir / "assessment.json")
    checks.append({"name": "move-plan", "status": "pass" if move_plan_result.ok else "fail", "detail": move_plan_result.summary()})
    if not move_plan_result.ok:
        return workflow_result("fail", paths, checks=checks)

    if capacity_path:
        capacity_result = validate_capacity_fit(inventory_path, out_dir / "nutanix-move-plan.csv", capacity_path)
        write_capacity_fit_csv(capacity_result, out_dir / "target-capacity-fit.csv")
        write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)
        checks.append(
            {
                "name": "capacity-fit",
                "status": "pass" if capacity_result.ok else "fail",
                "detail": capacity_result.summary(),
                "warnings": list(capacity_result.warnings),
                "errors": list(capacity_result.errors),
            }
        )
        if not capacity_result.ok:
            return workflow_result(
                "fail",
                paths,
                checks=checks,
                warnings=list(capacity_result.warnings),
                errors=list(capacity_result.errors),
            )

    if prism_inventory_path:
        target_reconciliation = reconcile_target_inventory(
            inventory_path,
            prism_inventory_path,
            out_dir / "nutanix-move-plan.csv",
        )
        write_target_reconciliation_csv(target_reconciliation, out_dir / "target-reconciliation.csv")
        write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)
        checks.append(
            {
                "name": "target-reconciliation",
                "status": "pass" if target_reconciliation.ok else "fail",
                "detail": target_reconciliation.summary(),
                "warnings": list(target_reconciliation.warnings),
                "errors": list(target_reconciliation.errors),
            }
        )
        if not target_reconciliation.ok:
            return workflow_result(
                "fail",
                paths,
                checks=checks,
                warnings=list(target_reconciliation.warnings),
                errors=list(target_reconciliation.errors),
            )

    if source_networks_path:
        source_network_result = validate_source_networks(out_dir / "nutanix-move-plan.csv", source_networks_path)
        write_source_network_validation_csv(source_network_result, out_dir / "source-network-validation.csv")
        write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)
        checks.append(
            {
                "name": "source-network-validation",
                "status": "pass" if source_network_result.ok else "fail",
                "detail": source_network_result.summary(),
                "warnings": list(source_network_result.warnings),
                "errors": list(source_network_result.errors),
            }
        )
        if not source_network_result.ok:
            return workflow_result(
                "fail",
                paths,
                checks=checks,
                warnings=list(source_network_result.warnings),
                errors=list(source_network_result.errors),
            )

    if move_config_path:
        network_mapping_result = validate_network_mappings(out_dir / "nutanix-move-plan.csv", move_config_path)
        write_network_mapping_csv(network_mapping_result, out_dir / "target-network-mapping.csv")
        write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)
        checks.append(
            {
                "name": "network-mapping",
                "status": "pass" if network_mapping_result.ok else "fail",
                "detail": network_mapping_result.summary(),
                "warnings": list(network_mapping_result.warnings),
                "errors": list(network_mapping_result.errors),
            }
        )
        if not network_mapping_result.ok:
            return workflow_result(
                "fail",
                paths,
                checks=checks,
                warnings=list(network_mapping_result.warnings),
                errors=list(network_mapping_result.errors),
            )
        payload = build_move_payload(out_dir / "nutanix-move-plan.csv", move_config_path)
        if paths.move_payload is None:
            raise ValueError("Move payload path was not resolved")
        paths.move_payload.parent.mkdir(parents=True, exist_ok=True)
        paths.move_payload.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        checks.append({"name": "move-payload", "status": "pass", "detail": f"workloads={len(payload['workloads'])}"})

    write_operator_gate_summary(
        out_dir,
        validation_results_path=validation_results_path,
        remediation_tracker_path=remediation_tracker_path,
        signoffs_path=signoffs_path,
        approval_exceptions_path=approval_exceptions_path,
        operator_review_path=operator_review_path,
        move_lab_capture_validation_path=move_lab_capture_validation_path,
        move_lab_proof_path=move_lab_proof_path,
        move_lab_evidence_intake_path=move_lab_evidence_intake_path,
    )
    write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)
    checks.append({"name": "operator-gate-summary", "status": "pass", "detail": str(out_dir / "operator-gate-summary.md")})

    evidence_result = verify_evidence(out_dir)
    checks.append({"name": "evidence-manifest", "status": "pass" if evidence_result.ok else "fail", "detail": evidence_result.summary()})
    if not evidence_result.ok:
        return workflow_result("fail", paths, checks=checks)

    redaction_result = review_evidence_dir(out_dir)
    checks.append({"name": "redaction-review", "status": "pass" if redaction_result.ok else "fail", "detail": redaction_result.summary()})
    if not redaction_result.ok:
        return workflow_result("fail", paths, checks=checks, errors=list(redaction_result.findings))

    package_evidence(out_dir, paths.evidence_bundle)
    checks.append({"name": "evidence-bundle", "status": "pass", "detail": str(paths.evidence_bundle)})

    gate = run_change_gate(
        out_dir,
        bundle_path=paths.evidence_bundle,
        validation_results_path=validation_results_path,
        remediation_tracker_path=remediation_tracker_path,
        signoffs_path=signoffs_path,
        approval_exceptions_path=approval_exceptions_path,
        operator_review_path=operator_review_path,
        move_lab_capture_validation_path=move_lab_capture_validation_path,
        move_lab_proof_path=move_lab_proof_path,
        move_lab_evidence_intake_path=move_lab_evidence_intake_path,
    )
    checks.append({"name": "change-gate", "status": "pass" if gate.ok else "fail", "detail": gate.summary()})
    if not gate.ok:
        return workflow_result("fail", paths, checks=checks, warnings=list(gate.warnings), errors=list(gate.errors))

    package_handoff(
        out_dir,
        paths.handoff_package,
        bundle_path=paths.evidence_bundle,
        validation_results_path=validation_results_path,
        remediation_tracker_path=remediation_tracker_path,
        signoffs_path=signoffs_path,
        approval_exceptions_path=approval_exceptions_path,
        move_payload_path=paths.move_payload,
        operator_review_path=operator_review_path,
        move_lab_capture_kit_dir=move_lab_capture_kit_dir,
        move_lab_capture_validation_path=move_lab_capture_validation_path if move_lab_capture_kit_dir else None,
        move_lab_proof_path=move_lab_proof_path,
        move_lab_readiness_packet_path=move_lab_readiness_packet_path,
        move_lab_evidence_intake_path=move_lab_evidence_intake_path,
    )
    handoff_result = verify_handoff_package(paths.handoff_package)
    checks.append(
        {
            "name": "handoff-package",
            "status": "pass" if handoff_result.ok else "fail",
            "detail": handoff_result.summary(),
        }
    )
    if not handoff_result.ok:
        return workflow_result("fail", paths, checks=checks)

    return workflow_result("pass", paths, checks=checks, warnings=list(gate.warnings))


def workflow_paths(
    out_dir: Path,
    validation_template_out: Path | None = None,
    bundle_out: Path | None = None,
    handoff_out: Path | None = None,
    move_payload_out: Path | None = None,
) -> WorkflowPaths:
    default_prefix = out_dir.parent / out_dir.name
    return WorkflowPaths(
        assessment_dir=out_dir,
        validation_template=validation_template_out or (out_dir / "validation-results.template.csv"),
        evidence_bundle=bundle_out or default_prefix.with_name(f"{default_prefix.name}-evidence-bundle.zip"),
        handoff_package=handoff_out or default_prefix.with_name(f"{default_prefix.name}-handoff-package.zip"),
        move_payload=move_payload_out,
    )


def workflow_result(
    status: str,
    paths: WorkflowPaths,
    checks: list[dict[str, Any]],
    warnings: list[str] | None = None,
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": "nmrcp_assessment_workflow_v1",
        "status": status,
        "paths": {
            "assessment_dir": str(paths.assessment_dir),
            "validation_template": str(paths.validation_template),
            "evidence_bundle": str(paths.evidence_bundle),
            "handoff_package": str(paths.handoff_package),
            "move_payload": str(paths.move_payload) if paths.move_payload else None,
        },
        "checks": checks,
        "warnings": warnings or [],
        "errors": errors or [],
    }
