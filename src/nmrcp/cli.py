from __future__ import annotations

import argparse
import getpass
import json
import os
from pathlib import Path

from .assessment_intake import validate_assessment_intake, write_assessment_intake_template
from .approval_exceptions import validate_approval_exception_approvals, validate_approval_exceptions
from .app_map import read_app_map, write_dependency_csv
from .business_impact import validate_business_impact_summary
from .capacity import normalize_prism_capacity, validate_capacity_fit, write_capacity_fit_csv
from .change_board_evidence import validate_change_board_evidence
from .collection_audit import validate_collection_audit_file
from .collection_proof_report import validate_collection_proof_report, write_collection_proof_report
from .collection_workflow import collect_sources
from .compatibility_research import validate_compatibility_research
from .connectors import EndpointConfig, PrismCentralClient, VCenterClient
from .change_gate import run_change_gate
from .connectivity_checklist import validate_connectivity_checklist
from .dependency_sequence import validate_dependency_sequence
from .dependency_review import validate_dependency_review
from .dependencies import apply_dependency_readiness_gates, merge_dependencies, read_dependency_csv
from .doctor import run_doctor
from .evidence_bundle import package_evidence, verify_evidence, verify_evidence_bundle
from .executive_brief import validate_executive_brief
from .external_proof_plan import build_external_proof_plan, validate_external_proof_plan
from .gate_summary import validate_operator_gate_summary, write_operator_gate_summary
from .github_readiness import DEFAULT_REPO_URL, check_github_readiness, validate_github_publication_review
from .evidence import write_assessment
from .handoff_package import package_handoff, verify_handoff_package
from .identity_cutover_plan import validate_identity_cutover_plan
from .inventory import normalize_prism_inventory, normalize_vcenter_inventory
from .inventory_coverage import validate_inventory_coverage_csv
from .inventory_validation import validate_inventory, validate_inventory_file
from .launch_readiness import build_launch_readiness_report, validate_launch_readiness_report, write_launch_readiness_report
from .live_readiness import run_live_readiness
from .live_proof import validate_live_proof
from .metadata import import_cmdb_metadata_csv, merge_metadata, read_metadata_csv, write_metadata_csv
from .migration_execution_queue import validate_migration_execution_queue
from .migration_waves import validate_migration_waves
from .mvp_audit import audit_mvp
from .mvp_proof_bundle import (
    build_mvp_closure_report,
    package_mvp_proof,
    summarize_mvp_proof_package,
    validate_mvp_closure_report,
    validate_mvp_proof_summary,
    verify_mvp_proof_package,
    write_mvp_closure_report,
    write_mvp_proof_summary,
)
from .move_plan import validate_move_plan
from .move_plan_brief import validate_move_plan_brief, write_move_plan_brief
from .move_payload import build_move_payload
from .migration_runbook import validate_migration_runbook
from .move_lab_capture_kit import validate_move_lab_capture_kit, write_move_lab_capture_kit
from .move_lab_evidence_intake import validate_move_lab_evidence_intake, validate_move_lab_evidence_preflight
from .move_lab_evidence_request import validate_move_lab_evidence_request
from .move_lab_proof import validate_move_lab_proof, write_approved_move_lab_proof, write_move_lab_proof_template
from .move_lab_readiness_packet import validate_move_lab_readiness_packet, write_move_lab_readiness_packet
from .move_lab_runbook import validate_move_lab_runbook, write_move_lab_runbook
from .move_lab_transcript import validate_move_lab_transcript
from .move_staging_readiness import validate_move_staging_brief, validate_move_staging_readiness
from .move_submit_readiness import validate_move_submit_readiness
from .network_mapping import validate_network_mappings, write_network_mapping_csv
from .operator_review import validate_operator_review, write_operator_review_template
from .operator_report import validate_operator_report
from .operator_dashboard import validate_operator_dashboard
from .operator_portal import validate_operator_portal
from .operations_console import validate_operations_console
from .owner_risk import validate_owner_risk_summary
from .partner_handoff_matrix import validate_partner_handoff_matrix
from .prism_categories import validate_prism_category_mapping
from .product_readiness import check_product_readiness, validate_product_readiness_report
from .publication_handoff import build_publication_handoff, validate_publication_handoff
from .publication_staging import build_publication_staging_manifest, validate_publication_staging_manifest
from .pull_request_readiness import build_pull_request_readiness, validate_pull_request_readiness
from .redaction_review import review_evidence_dir
from .recovery_readiness import validate_recovery_readiness
from .remediation import validate_remediation_tracker, validate_remediation_tracker_contract
from .risk_register import validate_risk_register
from .rollback_plan import validate_rollback_plan
from .rvtools import import_rvtools_directory
from .scoring import assess_inventory, load_readiness_policy
from .server import prepare_console_site, serve_console
from .signoff import validate_signoff_matrix_contract, validate_signoffs
from .source_endpoint_evidence_request import validate_source_endpoint_evidence_request
from .source_collection_plan import validate_source_collection_plan, write_source_collection_plan
from .source_networks import (
    validate_source_network_validation_csv,
    validate_source_networks,
    write_source_network_validation_csv,
)
from .stakeholder_comms import validate_stakeholder_comms
from .storage_posture import validate_storage_posture
from .target_comparison import validate_target_readiness_comparison
from .target_reconciliation import (
    reconcile_target_inventory,
    validate_target_reconciliation_csv,
    write_target_reconciliation_csv,
)
from .tools_driver_readiness import validate_tools_driver_readiness
from .validation_checklist import validate_validation_checklist
from .validation_results import validate_validation_results, write_validation_template
from .vault_readiness import DEFAULT_VAULT_PATH, check_vault_readiness
from .wave_execution_calendar import validate_wave_execution_calendar
from .wave_summary import validate_wave_readiness_summary
from .waves import plan_waves
from .warning_acceptance import validate_warning_acceptance
from .workload_validation_checklist import validate_workload_validation_checklist
from .what_will_break import validate_what_will_break, validate_what_will_break_brief
from .workflow import run_assessment_workflow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="nmrcp",
        description="Nutanix Migration & Readiness Control Plane local CLI",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    assess = subparsers.add_parser("assess", help="Score a normalized inventory and export evidence")
    assess.add_argument("--inventory", required=True, type=Path, help="Path to normalized inventory JSON")
    assess.add_argument("--metadata", type=Path, help="Optional workload metadata CSV to merge before scoring")
    assess.add_argument("--dependencies", type=Path, help="Optional dependency CSV to merge before scoring")
    assess.add_argument("--out", required=True, type=Path, help="Output directory for evidence artifacts")
    assess.add_argument("--target", default="ahv", choices=["ahv", "nc2"], help="Migration target")
    assess.add_argument("--policy", type=Path, help="Optional readiness policy JSON file")
    assess.add_argument("--capacity", type=Path, help="Optional target capacity JSON for capacity-fit evidence")
    assess.add_argument("--strict-inventory", action="store_true", help="Fail assessment when inventory warnings exist")

    workflow = subparsers.add_parser("run-assessment", help="Run the full local assessment-to-handoff workflow")
    workflow.add_argument("--inventory", required=True, type=Path, help="Path to normalized inventory JSON")
    workflow.add_argument("--metadata", type=Path, help="Optional workload metadata CSV to merge before scoring")
    workflow.add_argument("--dependencies", type=Path, help="Optional dependency CSV to merge before scoring")
    workflow.add_argument("--out", required=True, type=Path, help="Assessment output directory")
    workflow.add_argument("--target", default="ahv", choices=["ahv", "nc2"], help="Migration target")
    workflow.add_argument("--policy", type=Path, help="Optional readiness policy JSON file")
    workflow.add_argument("--capacity", type=Path, help="Optional target capacity JSON for capacity-fit evidence")
    workflow.add_argument("--prism-inventory", type=Path, help="Optional Prism inventory JSON for target reconciliation")
    workflow.add_argument("--source-networks", type=Path, help="Optional vCenter network inventory JSON for source network validation")
    workflow.add_argument("--strict-inventory", action="store_true", help="Fail workflow when inventory warnings exist")
    workflow.add_argument("--move-config", type=Path, help="Optional Move payload config JSON")
    workflow.add_argument("--move-payload-out", type=Path, help="Optional dry-run Move payload JSON path")
    workflow.add_argument("--validation-results", type=Path, help="Optional final validation results CSV for closure gate")
    workflow.add_argument("--remediation-tracker", type=Path, help="Optional final remediation tracker CSV for closure gate")
    workflow.add_argument("--signoffs", type=Path, help="Optional final owner sign-off matrix CSV for closure gate")
    workflow.add_argument("--approval-exceptions", type=Path, help="Optional final approval exceptions CSV for closure gate")
    workflow.add_argument("--operator-review", type=Path, help="Optional approved operator assessment review CSV")
    workflow.add_argument("--move-lab-capture-kit", type=Path, help="Optional Move lab capture kit directory")
    workflow.add_argument("--move-lab-capture-validation", type=Path, help="Optional Move lab capture kit validation JSON")
    workflow.add_argument("--move-lab-proof", type=Path, help="Optional approved Move lab proof validation JSON")
    workflow.add_argument("--move-lab-readiness-packet", type=Path, help="Optional pre-lab Move readiness packet JSON")
    workflow.add_argument("--move-lab-evidence-intake", type=Path, help="Optional final Move lab evidence intake JSON")
    workflow.add_argument("--validation-template-out", type=Path, help="Optional validation results template CSV path")
    workflow.add_argument("--bundle-out", type=Path, help="Optional evidence bundle zip path")
    workflow.add_argument("--handoff-out", type=Path, help="Optional handoff package zip path")
    workflow.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    inventory_validate = subparsers.add_parser("validate-inventory", help="Validate normalized inventory JSON")
    inventory_validate.add_argument("--inventory", required=True, type=Path, help="Path to normalized inventory JSON")
    inventory_validate.add_argument("--strict", action="store_true", help="Return failure on warnings")

    coverage_validate = subparsers.add_parser("validate-inventory-coverage", help="Validate inventory-coverage.csv")
    coverage_validate.add_argument("--coverage", required=True, type=Path, help="Path to inventory-coverage.csv")
    coverage_validate.add_argument("--move-plan", type=Path, help="Optional nutanix-move-plan.csv for included-workload gap checks")
    coverage_validate.add_argument("--minimum-coverage-percent", type=int, default=90, help="Warn when coverage falls below this percent")

    audit_validate = subparsers.add_parser("validate-collection-audit", help="Validate non-secret inventory collection audit metadata")
    audit_validate.add_argument("--inventory", required=True, type=Path, help="Path to normalized inventory JSON")

    rvtools = subparsers.add_parser("import-rvtools", help="Import RVTools CSV export files into normalized inventory JSON")
    rvtools.add_argument("--dir", required=True, type=Path, help="Directory containing RVTools CSV files")
    rvtools.add_argument("--out", required=True, type=Path, help="Normalized inventory JSON output path")
    rvtools.add_argument("--source-name", default="rvtools-export", help="Source label written to inventory metadata")

    vcenter = subparsers.add_parser("collect-vcenter", help="Collect read-only vCenter VM inventory")
    vcenter.add_argument("--endpoint", default=os.getenv("NMRCP_VCENTER_URL"), help="vCenter base URL")
    vcenter.add_argument("--username", default=os.getenv("NMRCP_VCENTER_USERNAME"), help="vCenter username")
    vcenter.add_argument("--password-env", default="NMRCP_VCENTER_PASSWORD", help="Environment variable holding password")
    vcenter.add_argument("--out", required=True, type=Path, help="Normalized inventory JSON output path")
    vcenter.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    vcenter.add_argument("--details-limit", type=int, default=250, help="Maximum VMs to enrich with detail calls")

    probe_vcenter = subparsers.add_parser("probe-vcenter", help="Probe vCenter read-only API reachability")
    probe_vcenter.add_argument("--endpoint", default=os.getenv("NMRCP_VCENTER_URL"), help="vCenter base URL")
    probe_vcenter.add_argument("--username", default=os.getenv("NMRCP_VCENTER_USERNAME"), help="vCenter username")
    probe_vcenter.add_argument("--password-env", default="NMRCP_VCENTER_PASSWORD", help="Environment variable holding password")
    probe_vcenter.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")

    prism = subparsers.add_parser("collect-prism", help="Collect read-only Prism Central VM inventory")
    prism.add_argument("--endpoint", default=os.getenv("NMRCP_PRISM_URL"), help="Prism Central base URL")
    prism.add_argument("--username", default=os.getenv("NMRCP_PRISM_USERNAME"), help="Prism Central username")
    prism.add_argument("--password-env", default="NMRCP_PRISM_PASSWORD", help="Environment variable holding password")
    prism.add_argument("--out", required=True, type=Path, help="Normalized inventory JSON output path")
    prism.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    prism.add_argument("--page-size", type=int, default=500, help="Prism v3 page size")
    prism.add_argument("--max-pages", type=int, default=20, help="Maximum pages to request")

    prism_capacity = subparsers.add_parser("collect-prism-capacity", help="Draft target capacity JSON from read-only Prism Central cluster inventory")
    prism_capacity.add_argument("--endpoint", default=os.getenv("NMRCP_PRISM_URL"), help="Prism Central base URL")
    prism_capacity.add_argument("--username", default=os.getenv("NMRCP_PRISM_USERNAME"), help="Prism Central username")
    prism_capacity.add_argument("--password-env", default="NMRCP_PRISM_PASSWORD", help="Environment variable holding password")
    prism_capacity.add_argument("--out", required=True, type=Path, help="Target capacity JSON output path")
    prism_capacity.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    prism_capacity.add_argument("--page-size", type=int, default=100, help="Prism cluster list page size")
    prism_capacity.add_argument("--target", default="ahv", choices=["ahv", "nc2"], help="Capacity target label")
    prism_capacity.add_argument("--cpu-reserved-percent", type=float, default=20, help="CPU capacity reserved for headroom")
    prism_capacity.add_argument("--memory-reserved-percent", type=float, default=25, help="Memory capacity reserved for headroom")
    prism_capacity.add_argument("--storage-reserved-percent", type=float, default=30, help="Storage capacity reserved for headroom")
    prism_capacity.add_argument("--cpu-overcommit-ratio", type=float, default=1.0, help="Approved CPU overcommit ratio for planning")

    collect_sources_parser = subparsers.add_parser("collect-sources", help="Collect vCenter inventory, Prism inventory, and Prism capacity")
    collect_sources_parser.add_argument("--vcenter-endpoint", default=os.getenv("NMRCP_VCENTER_URL"), help="vCenter base URL")
    collect_sources_parser.add_argument("--vcenter-username", default=os.getenv("NMRCP_VCENTER_USERNAME"), help="vCenter username")
    collect_sources_parser.add_argument("--vcenter-password-env", default="NMRCP_VCENTER_PASSWORD", help="Environment variable holding vCenter password")
    collect_sources_parser.add_argument("--prism-endpoint", default=os.getenv("NMRCP_PRISM_URL"), help="Prism Central base URL")
    collect_sources_parser.add_argument("--prism-username", default=os.getenv("NMRCP_PRISM_USERNAME"), help="Prism Central username")
    collect_sources_parser.add_argument("--prism-password-env", default="NMRCP_PRISM_PASSWORD", help="Environment variable holding Prism Central password")
    collect_sources_parser.add_argument("--out-dir", required=True, type=Path, help="Directory for collected source artifacts")
    collect_sources_parser.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    collect_sources_parser.add_argument("--vcenter-details-limit", type=int, default=250, help="Maximum vCenter VMs to enrich with detail calls")
    collect_sources_parser.add_argument("--prism-page-size", type=int, default=500, help="Prism VM list page size")
    collect_sources_parser.add_argument("--prism-max-pages", type=int, default=20, help="Maximum Prism VM pages to request")
    collect_sources_parser.add_argument("--prism-capacity-page-size", type=int, default=100, help="Prism cluster list page size")
    collect_sources_parser.add_argument("--target", default="ahv", choices=["ahv", "nc2"], help="Capacity target label")
    collect_sources_parser.add_argument("--assessment-intake", type=Path, help="Optional validated assessment intake CSV to bind into collection proof")
    collect_sources_parser.add_argument("--cpu-reserved-percent", type=float, default=20, help="CPU capacity reserved for headroom")
    collect_sources_parser.add_argument("--memory-reserved-percent", type=float, default=25, help="Memory capacity reserved for headroom")
    collect_sources_parser.add_argument("--storage-reserved-percent", type=float, default=30, help="Storage capacity reserved for headroom")
    collect_sources_parser.add_argument("--cpu-overcommit-ratio", type=float, default=1.0, help="Approved CPU overcommit ratio for planning")
    collect_sources_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    intake_template = subparsers.add_parser("generate-assessment-intake", help="Generate customer/partner assessment intake template")
    intake_template.add_argument("--out", required=True, type=Path, help="Assessment intake CSV output path")

    intake_validate = subparsers.add_parser("validate-assessment-intake", help="Validate customer/partner assessment intake before collection")
    intake_validate.add_argument("--intake", required=True, type=Path, help="Assessment intake CSV path")
    intake_validate.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    source_collection_plan = subparsers.add_parser("source-collection-plan", help="Generate a credential-safe read-only source collection plan from completed intake")
    source_collection_plan.add_argument("--intake", required=True, type=Path, help="Completed assessment intake CSV path")
    source_collection_plan.add_argument("--out", required=True, type=Path, help="Source collection plan Markdown output path")

    validate_source_collection_plan_parser = subparsers.add_parser("validate-source-collection-plan", help="Validate source collection plan against completed intake")
    validate_source_collection_plan_parser.add_argument("--plan", required=True, type=Path, help="Source collection plan Markdown path")
    validate_source_collection_plan_parser.add_argument("--intake", required=True, type=Path, help="Completed assessment intake CSV path")

    collection_proof_report = subparsers.add_parser("collection-proof-report", help="Generate a redacted Markdown report from collection-summary.json")
    collection_proof_report.add_argument("--collection-summary", required=True, type=Path, help="Collection summary JSON path")
    collection_proof_report.add_argument("--out", required=True, type=Path, help="Collection proof report Markdown output path")

    validate_collection_proof_report_parser = subparsers.add_parser("validate-collection-proof-report", help="Validate collection proof report Markdown")
    validate_collection_proof_report_parser.add_argument("--report", required=True, type=Path, help="Collection proof report Markdown path")
    validate_collection_proof_report_parser.add_argument("--collection-summary", type=Path, help="Optional collection summary JSON path for cross-checks")

    probe_prism = subparsers.add_parser("probe-prism", help="Probe Prism Central read-only API reachability")
    probe_prism.add_argument("--endpoint", default=os.getenv("NMRCP_PRISM_URL"), help="Prism Central base URL")
    probe_prism.add_argument("--username", default=os.getenv("NMRCP_PRISM_USERNAME"), help="Prism Central username")
    probe_prism.add_argument("--password-env", default="NMRCP_PRISM_PASSWORD", help="Environment variable holding password")
    probe_prism.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")

    live = subparsers.add_parser("live-readiness", help="Run redacted read-only vCenter and Prism Central readiness checks")
    live.add_argument("--out", type=Path, help="Optional JSON proof output path")
    live.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    live.add_argument("--require-vcenter", action="store_true", help="Fail if vCenter env vars or probe are unavailable")
    live.add_argument("--require-prism", action="store_true", help="Fail if Prism Central env vars or probe are unavailable")
    live.add_argument("--insecure", action="store_true", help="Disable TLS certificate verification")
    live.add_argument("--prism-page-size", type=int, default=100, help="Prism list page size for the readiness probe")
    live.add_argument("--prism-max-pages", type=int, default=1, help="Maximum Prism VM pages to count")

    live_proof = subparsers.add_parser("validate-live-proof", help="Validate redacted live endpoint and collection proof artifacts")
    live_proof.add_argument("--live-readiness", required=True, type=Path, help="Path to live-readiness JSON proof")
    live_proof.add_argument("--collection-summary", type=Path, help="Optional collection-summary.json proof")
    live_proof.add_argument("--source-dir", type=Path, help="Optional directory containing source collection artifacts")
    live_proof.add_argument("--out", type=Path, help="Optional JSON validation proof output path")
    live_proof.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    enrich = subparsers.add_parser("enrich-dependencies", help="Merge dependency CSV data into inventory JSON")
    enrich.add_argument("--inventory", required=True, type=Path, help="Path to normalized inventory JSON")
    enrich.add_argument("--dependencies", required=True, type=Path, help="Dependency CSV path")
    enrich.add_argument("--out", required=True, type=Path, help="Enriched inventory JSON output path")

    app_map = subparsers.add_parser("import-app-map", help="Convert an application dependency map JSON into dependency CSV")
    app_map.add_argument("--map", required=True, type=Path, help="Path to nmrcp_app_map_v1 JSON")
    app_map.add_argument("--out", required=True, type=Path, help="Dependency CSV output path")

    enrich_metadata = subparsers.add_parser("enrich-metadata", help="Merge workload metadata CSV into inventory JSON")
    enrich_metadata.add_argument("--inventory", required=True, type=Path, help="Path to normalized inventory JSON")
    enrich_metadata.add_argument("--metadata", required=True, type=Path, help="Workload metadata CSV path")
    enrich_metadata.add_argument("--out", required=True, type=Path, help="Enriched inventory JSON output path")

    cmdb_metadata = subparsers.add_parser("import-cmdb-metadata", help="Convert generic CMDB/application-owner CSV exports into workload metadata CSV")
    cmdb_metadata.add_argument("--export", required=True, type=Path, help="Generic CMDB or application-owner CSV export path")
    cmdb_metadata.add_argument("--out", required=True, type=Path, help="Normalized workload metadata CSV output path")

    validate = subparsers.add_parser("validate-move-plan", help="Validate an nmrcp Move staging CSV")
    validate.add_argument("--plan", required=True, type=Path, help="Path to nutanix-move-plan.csv")
    validate.add_argument("--assessment", type=Path, help="Optional assessment.json for source-bound validation")

    move_plan_brief = subparsers.add_parser("move-plan-brief", help="Generate a reviewer Markdown brief from nutanix-move-plan.csv")
    move_plan_brief.add_argument("--plan", required=True, type=Path, help="Path to nutanix-move-plan.csv")
    move_plan_brief.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")
    move_plan_brief.add_argument("--out", required=True, type=Path, help="Move plan brief Markdown output path")

    validate_move_plan_brief_parser = subparsers.add_parser("validate-move-plan-brief", help="Validate move-plan-brief.md against nutanix-move-plan.csv and assessment.json")
    validate_move_plan_brief_parser.add_argument("--brief", required=True, type=Path, help="Path to move-plan-brief.md")
    validate_move_plan_brief_parser.add_argument("--plan", required=True, type=Path, help="Path to nutanix-move-plan.csv")
    validate_move_plan_brief_parser.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    capacity = subparsers.add_parser("validate-capacity", help="Validate Move staging plan resource fit against target capacity JSON")
    capacity.add_argument("--inventory", required=True, type=Path, help="Path to normalized inventory JSON")
    capacity.add_argument("--plan", required=True, type=Path, help="Path to nutanix-move-plan.csv")
    capacity.add_argument("--capacity", required=True, type=Path, help="Path to target capacity JSON")
    capacity.add_argument("--out", type=Path, help="Optional target-capacity-fit.csv output path")

    network_mapping = subparsers.add_parser("validate-network-mappings", help="Validate included Move workloads against target network mapping config")
    network_mapping.add_argument("--plan", required=True, type=Path, help="Path to nutanix-move-plan.csv")
    network_mapping.add_argument("--config", required=True, type=Path, help="Move payload config JSON")
    network_mapping.add_argument("--out", type=Path, help="Optional target-network-mapping.csv output path")

    source_networks = subparsers.add_parser("validate-source-networks", help="Validate included Move source networks against vCenter network inventory")
    source_networks.add_argument("--plan", required=True, type=Path, help="Path to nutanix-move-plan.csv")
    source_networks.add_argument("--networks", required=True, type=Path, help="Path to vcenter-networks.json")
    source_networks.add_argument("--out", type=Path, help="Optional source-network-validation.csv output path")

    source_networks_validate = subparsers.add_parser("validate-source-network-results", help="Validate source-network-validation.csv")
    source_networks_validate.add_argument("--results", required=True, type=Path, help="Path to source-network-validation.csv")

    target_reconciliation = subparsers.add_parser("reconcile-target", help="Compare source Move plan workloads with Prism target inventory")
    target_reconciliation.add_argument("--inventory", required=True, type=Path, help="Path to source normalized inventory JSON")
    target_reconciliation.add_argument("--target-inventory", required=True, type=Path, help="Path to Prism normalized inventory JSON")
    target_reconciliation.add_argument("--plan", required=True, type=Path, help="Path to nutanix-move-plan.csv")
    target_reconciliation.add_argument("--out", type=Path, help="Optional target-reconciliation.csv output path")

    target_reconciliation_validate = subparsers.add_parser("validate-target-reconciliation", help="Validate target-reconciliation.csv")
    target_reconciliation_validate.add_argument("--reconciliation", required=True, type=Path, help="Path to target-reconciliation.csv")

    gate_summary = subparsers.add_parser("summarize-gates", help="Write operator-gate-summary.md for optional evidence gates")
    gate_summary.add_argument("--dir", required=True, type=Path, help="Assessment output directory")
    gate_summary.add_argument("--out", type=Path, help="Optional gate summary Markdown path")
    gate_summary.add_argument("--validation-results", type=Path, help="Optional final validation results CSV")
    gate_summary.add_argument("--remediation-tracker", type=Path, help="Optional final remediation tracker CSV")
    gate_summary.add_argument("--signoffs", type=Path, help="Optional final owner sign-off matrix CSV")
    gate_summary.add_argument("--approval-exceptions", type=Path, help="Optional final approval exceptions CSV")
    gate_summary.add_argument("--operator-review", type=Path, help="Optional operator assessment review CSV")
    gate_summary.add_argument("--move-lab-capture-validation", type=Path, help="Optional Move lab capture kit validation JSON")
    gate_summary.add_argument("--move-lab-proof", type=Path, help="Optional approved Move lab proof validation JSON")
    gate_summary.add_argument("--move-lab-evidence-intake", type=Path, help="Optional final Move lab evidence intake JSON")

    validate_gate_summary = subparsers.add_parser("validate-operator-gate-summary", help="Validate operator-gate-summary.md")
    validate_gate_summary.add_argument("--summary", required=True, type=Path, help="Path to operator-gate-summary.md")

    validation_template = subparsers.add_parser("generate-validation-template", help="Generate pre/post validation results CSV template from a Move plan")
    validation_template.add_argument("--plan", required=True, type=Path, help="Path to nutanix-move-plan.csv")
    validation_template.add_argument("--out", required=True, type=Path, help="Validation results CSV template output path")

    operator_review_template = subparsers.add_parser("generate-operator-review", help="Generate operator assessment review CSV template")
    operator_review_template.add_argument("--dir", required=True, type=Path, help="Assessment output directory")
    operator_review_template.add_argument("--out", required=True, type=Path, help="Operator review CSV output path")

    operator_review = subparsers.add_parser("validate-operator-review", help="Validate filled operator assessment review CSV")
    operator_review.add_argument("--review", required=True, type=Path, help="Path to operator review CSV")
    operator_review.add_argument("--allow-draft", action="store_true", help="Allow draft, rejected, or needs_changes review rows")

    partner_handoff = subparsers.add_parser("validate-partner-handoff", help="Validate partner-handoff-matrix.csv against assessment.json")
    partner_handoff.add_argument("--matrix", required=True, type=Path, help="Path to partner-handoff-matrix.csv")
    partner_handoff.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    validation_results = subparsers.add_parser("validate-validation-results", help="Validate filled pre/post validation results CSV")
    validation_results.add_argument("--results", required=True, type=Path, help="Path to validation results CSV")
    validation_results.add_argument("--allow-open", action="store_true", help="Allow failed or not_checked rows during draft review")

    validation_checklist = subparsers.add_parser("validate-validation-checklist", help="Validate generated pre-post-validation-checklist.md")
    validation_checklist.add_argument("--checklist", required=True, type=Path, help="Path to pre-post-validation-checklist.md")

    workload_validation = subparsers.add_parser("validate-workload-validation-checklist", help="Validate workload-validation-checklist.csv against assessment.json")
    workload_validation.add_argument("--checklist", required=True, type=Path, help="Path to workload-validation-checklist.csv")
    workload_validation.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    execution_queue = subparsers.add_parser("validate-migration-execution-queue", help="Validate migration-execution-queue.csv against assessment.json")
    execution_queue.add_argument("--queue", required=True, type=Path, help="Path to migration-execution-queue.csv")
    execution_queue.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    prism_categories = subparsers.add_parser("validate-prism-categories", help="Validate prism-category-mapping.csv against assessment.json")
    prism_categories.add_argument("--mapping", required=True, type=Path, help="Path to prism-category-mapping.csv")
    prism_categories.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    stakeholder_comms = subparsers.add_parser("validate-stakeholder-comms", help="Validate stakeholder-communication-plan.csv against assessment.json")
    stakeholder_comms.add_argument("--plan", required=True, type=Path, help="Path to stakeholder-communication-plan.csv")
    stakeholder_comms.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    what_will_break = subparsers.add_parser("validate-what-will-break", help="Validate what-will-break-report.csv against assessment.json")
    what_will_break.add_argument("--report", required=True, type=Path, help="Path to what-will-break-report.csv")
    what_will_break.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    what_will_break_brief = subparsers.add_parser("validate-what-will-break-brief", help="Validate what-will-break-brief.md against assessment.json")
    what_will_break_brief.add_argument("--brief", required=True, type=Path, help="Path to what-will-break-brief.md")
    what_will_break_brief.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    connectivity_checklist = subparsers.add_parser("validate-connectivity-checklist", help="Validate connectivity-checklist.csv against assessment.json")
    connectivity_checklist.add_argument("--checklist", required=True, type=Path, help="Path to connectivity-checklist.csv")
    connectivity_checklist.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    identity_cutover = subparsers.add_parser("validate-identity-cutover-plan", help="Validate identity-cutover-plan.csv against assessment.json")
    identity_cutover.add_argument("--plan", required=True, type=Path, help="Path to identity-cutover-plan.csv")
    identity_cutover.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    compatibility_research = subparsers.add_parser("validate-compatibility-research", help="Validate compatibility-research.csv against assessment.json")
    compatibility_research.add_argument("--research", required=True, type=Path, help="Path to compatibility-research.csv")
    compatibility_research.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    rollback_plan = subparsers.add_parser("validate-rollback-plan", help="Validate rollback-plan.csv against assessment.json")
    rollback_plan.add_argument("--plan", required=True, type=Path, help="Path to rollback-plan.csv")
    rollback_plan.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    remediation = subparsers.add_parser("validate-remediation", help="Validate filled remediation tracker CSV")
    remediation.add_argument("--tracker", required=True, type=Path, help="Path to remediation-tracker.csv")
    remediation.add_argument("--allow-open", action="store_true", help="Allow open rows during draft review")

    remediation_tracker = subparsers.add_parser("validate-remediation-tracker", help="Validate generated remediation-tracker.csv against assessment.json")
    remediation_tracker.add_argument("--tracker", required=True, type=Path, help="Path to remediation-tracker.csv")
    remediation_tracker.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    signoffs = subparsers.add_parser("validate-signoffs", help="Validate filled owner sign-off matrix CSV")
    signoffs.add_argument("--signoffs", required=True, type=Path, help="Path to owner-signoff-matrix.csv")
    signoffs.add_argument("--allow-pending", action="store_true", help="Allow pending rows during draft review")

    signoff_matrix = subparsers.add_parser("validate-signoff-matrix", help="Validate generated owner-signoff-matrix.csv against assessment.json")
    signoff_matrix.add_argument("--matrix", required=True, type=Path, help="Path to owner-signoff-matrix.csv")
    signoff_matrix.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    approval_exceptions = subparsers.add_parser("validate-approval-exceptions", help="Validate approval-exceptions.csv against assessment.json")
    approval_exceptions.add_argument("--exceptions", required=True, type=Path, help="Path to approval-exceptions.csv")
    approval_exceptions.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    approval_exception_approvals = subparsers.add_parser("validate-approval-exception-approvals", help="Validate filled approval exceptions CSV")
    approval_exception_approvals.add_argument("--exceptions", required=True, type=Path, help="Path to filled approval-exceptions.csv")
    approval_exception_approvals.add_argument("--assessment", type=Path, help="Optional assessment.json to verify exception rows against")
    approval_exception_approvals.add_argument("--allow-required", action="store_true", help="Allow unresolved required approvals during draft review")

    executive_brief = subparsers.add_parser("validate-executive-brief", help="Validate executive-readiness-brief.md against assessment.json")
    executive_brief.add_argument("--brief", required=True, type=Path, help="Path to executive-readiness-brief.md")
    executive_brief.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    change_board_evidence = subparsers.add_parser("validate-change-board-evidence", help="Validate change-board-evidence.md against assessment.json")
    change_board_evidence.add_argument("--evidence", required=True, type=Path, help="Path to change-board-evidence.md")
    change_board_evidence.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    operator_report = subparsers.add_parser("validate-operator-report", help="Validate operator-report.html against assessment.json")
    operator_report.add_argument("--report", required=True, type=Path, help="Path to operator-report.html")
    operator_report.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    operator_portal = subparsers.add_parser("validate-operator-portal", help="Validate operator-portal.html against assessment.json")
    operator_portal.add_argument("--portal", required=True, type=Path, help="Path to operator-portal.html")
    operator_portal.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    operations_console = subparsers.add_parser("validate-operations-console", help="Validate operations-console.html against assessment.json")
    operations_console.add_argument("--console", required=True, type=Path, help="Path to operations-console.html")
    operations_console.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    operator_dashboard = subparsers.add_parser("validate-operator-dashboard", help="Validate operator-dashboard.html against assessment.json")
    operator_dashboard.add_argument("--dashboard", required=True, type=Path, help="Path to operator-dashboard.html")
    operator_dashboard.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    wave_summary = subparsers.add_parser("validate-wave-summary", help="Validate wave-readiness-summary.csv against assessment.json")
    wave_summary.add_argument("--summary", required=True, type=Path, help="Path to wave-readiness-summary.csv")
    wave_summary.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    wave_calendar = subparsers.add_parser("validate-wave-execution-calendar", help="Validate wave-execution-calendar.csv against assessment.json")
    wave_calendar.add_argument("--calendar", required=True, type=Path, help="Path to wave-execution-calendar.csv")
    wave_calendar.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    migration_waves = subparsers.add_parser("validate-migration-waves", help="Validate migration-waves.csv against assessment.json")
    migration_waves.add_argument("--waves", required=True, type=Path, help="Path to migration-waves.csv")
    migration_waves.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    migration_runbook = subparsers.add_parser("validate-migration-runbook", help="Validate migration-runbook.md against assessment.json")
    migration_runbook.add_argument("--runbook", required=True, type=Path, help="Path to migration-runbook.md")
    migration_runbook.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    dependency_sequence = subparsers.add_parser("validate-dependency-sequence", help="Validate dependency-sequence.csv against assessment.json")
    dependency_sequence.add_argument("--sequence", required=True, type=Path, help="Path to dependency-sequence.csv")
    dependency_sequence.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    dependency_review = subparsers.add_parser("validate-dependency-review", help="Validate dependency-review.csv against assessment.json")
    dependency_review.add_argument("--review", required=True, type=Path, help="Path to dependency-review.csv")
    dependency_review.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    tools_driver = subparsers.add_parser("validate-tools-driver-readiness", help="Validate tools-driver-readiness.csv against assessment.json")
    tools_driver.add_argument("--readiness", required=True, type=Path, help="Path to tools-driver-readiness.csv")
    tools_driver.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    storage_posture = subparsers.add_parser("validate-storage-posture", help="Validate storage-posture.csv against assessment.json")
    storage_posture.add_argument("--posture", required=True, type=Path, help="Path to storage-posture.csv")
    storage_posture.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    recovery_readiness = subparsers.add_parser("validate-recovery-readiness", help="Validate recovery-readiness.csv against assessment.json")
    recovery_readiness.add_argument("--readiness", required=True, type=Path, help="Path to recovery-readiness.csv")
    recovery_readiness.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    move_staging_readiness = subparsers.add_parser("validate-move-staging-readiness", help="Validate move-staging-readiness.csv against assessment.json")
    move_staging_readiness.add_argument("--readiness", required=True, type=Path, help="Path to move-staging-readiness.csv")
    move_staging_readiness.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    move_staging_brief = subparsers.add_parser("validate-move-staging-brief", help="Validate move-staging-brief.md against assessment.json")
    move_staging_brief.add_argument("--brief", required=True, type=Path, help="Path to move-staging-brief.md")
    move_staging_brief.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    business_impact = subparsers.add_parser("validate-business-impact", help="Validate business-impact-summary.csv against assessment.json")
    business_impact.add_argument("--summary", required=True, type=Path, help="Path to business-impact-summary.csv")
    business_impact.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    target_comparison = subparsers.add_parser("validate-target-comparison", help="Validate target-readiness-comparison.csv against assessment.json")
    target_comparison.add_argument("--comparison", required=True, type=Path, help="Path to target-readiness-comparison.csv")
    target_comparison.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    risk_register = subparsers.add_parser("validate-risk-register", help="Validate migration-risk-register.csv against assessment.json")
    risk_register.add_argument("--register", required=True, type=Path, help="Path to migration-risk-register.csv")
    risk_register.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    owner_risk = subparsers.add_parser("validate-owner-risk-summary", help="Validate owner-risk-summary.csv against assessment.json")
    owner_risk.add_argument("--summary", required=True, type=Path, help="Path to owner-risk-summary.csv")
    owner_risk.add_argument("--assessment", required=True, type=Path, help="Path to assessment.json")

    payload = subparsers.add_parser("generate-move-payload", help="Generate a dry-run-only Move API payload")
    payload.add_argument("--plan", required=True, type=Path, help="Path to validated nutanix-move-plan.csv")
    payload.add_argument("--config", required=True, type=Path, help="Move payload config JSON")
    payload.add_argument("--out", required=True, type=Path, help="Dry-run payload JSON output path")

    move_submit_readiness = subparsers.add_parser("validate-move-submit-readiness", help="Fail-closed lab-only readiness gate for reviewed Move API payloads")
    move_submit_readiness.add_argument("--payload", required=True, type=Path, help="Path to dry-run Move API payload JSON")
    move_submit_readiness.add_argument("--review", required=True, type=Path, help="Path to Move submit review JSON")
    move_submit_readiness.add_argument("--lab-ack-env", default="NMRCP_MOVE_LAB_ACK", help="Environment variable that must equal I_UNDERSTAND_LAB_ONLY")
    move_submit_readiness.add_argument("--out", type=Path, help="Optional JSON readiness proof output path")
    move_submit_readiness.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    move_lab_proof = subparsers.add_parser("validate-move-lab-proof", help="Validate redacted lab Move appliance proof")
    move_lab_proof.add_argument("--proof", required=True, type=Path, help="Path to nmrcp_move_lab_proof_v1 JSON")
    move_lab_proof.add_argument("--payload", required=True, type=Path, help="Path to dry-run Move API payload JSON")
    move_lab_proof.add_argument("--review", required=True, type=Path, help="Path to Move submit review JSON")
    move_lab_proof.add_argument("--transcript-validation", type=Path, help="Required for approved proof: move-lab-transcript-validation.json")
    move_lab_proof.add_argument("--lab-ack-env", default="NMRCP_MOVE_LAB_ACK", help="Environment variable that must equal I_UNDERSTAND_LAB_ONLY")
    move_lab_proof.add_argument("--out", type=Path, help="Optional JSON validation proof output path")
    move_lab_proof.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    move_lab_transcript = subparsers.add_parser("validate-move-lab-transcript", help="Validate redacted real lab Move appliance API transcript")
    move_lab_transcript.add_argument("--transcript", required=True, type=Path, help="Path to nmrcp_move_lab_transcript_v1 JSON")
    move_lab_transcript.add_argument("--payload", required=True, type=Path, help="Path to dry-run Move API payload JSON")
    move_lab_transcript.add_argument("--review", required=True, type=Path, help="Path to Move submit review JSON")
    move_lab_transcript.add_argument("--lab-ack-env", default="NMRCP_MOVE_LAB_ACK", help="Environment variable that must equal I_UNDERSTAND_LAB_ONLY")
    move_lab_transcript.add_argument("--out", type=Path, help="Optional JSON validation proof output path")
    move_lab_transcript.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    move_lab_capture_kit = subparsers.add_parser("generate-move-lab-capture-kit", help="Generate redacted Move lab transcript capture template and checklist")
    move_lab_capture_kit.add_argument("--payload", required=True, type=Path, help="Path to dry-run Move API payload JSON")
    move_lab_capture_kit.add_argument("--review", required=True, type=Path, help="Path to Move submit review JSON")
    move_lab_capture_kit.add_argument("--lab-ack-env", default="NMRCP_MOVE_LAB_ACK", help="Environment variable that must equal I_UNDERSTAND_LAB_ONLY")
    move_lab_capture_kit.add_argument("--out-dir", required=True, type=Path, help="Directory for the capture kit files")
    move_lab_capture_kit.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    validate_move_lab_capture = subparsers.add_parser("validate-move-lab-capture-kit", help="Validate a generated Move lab capture kit")
    validate_move_lab_capture.add_argument("--kit-dir", required=True, type=Path, help="Directory containing the Move lab capture kit")
    validate_move_lab_capture.add_argument("--payload", required=True, type=Path, help="Path to reviewed dry-run Move API payload JSON")
    validate_move_lab_capture.add_argument("--out", type=Path, help="Optional JSON validation proof output path")
    validate_move_lab_capture.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    move_lab_intake = subparsers.add_parser("validate-move-lab-evidence-intake", help="Validate final approved Move lab evidence intake")
    move_lab_intake.add_argument("--payload", required=True, type=Path, help="Path to reviewed dry-run Move payload JSON")
    move_lab_intake.add_argument("--review", required=True, type=Path, help="Path to Move submit review JSON")
    move_lab_intake.add_argument("--transcript", required=True, type=Path, help="Path to captured approved Move lab transcript JSON")
    move_lab_intake.add_argument("--transcript-validation", required=True, type=Path, help="Path to transcript validation JSON")
    move_lab_intake.add_argument("--proof", required=True, type=Path, help="Path to completed approved Move lab proof JSON")
    move_lab_intake.add_argument("--proof-validation", required=True, type=Path, help="Path to approved Move lab proof validation JSON")
    move_lab_intake.add_argument("--capture-kit-validation", required=True, type=Path, help="Path to Move lab capture kit validation JSON")
    move_lab_intake.add_argument("--lab-ack-env", default="NMRCP_MOVE_LAB_ACK", help="Environment variable that must equal I_UNDERSTAND_LAB_ONLY")
    move_lab_intake.add_argument("--out", type=Path, help="Optional JSON evidence intake output path")
    move_lab_intake.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    move_lab_preflight = subparsers.add_parser("move-lab-evidence-preflight", help="Preflight approved Move lab evidence capture inputs")
    move_lab_preflight.add_argument("--payload", required=True, type=Path, help="Path to reviewed dry-run Move API payload JSON")
    move_lab_preflight.add_argument("--review", required=True, type=Path, help="Path to Move submit review JSON")
    move_lab_preflight.add_argument("--capture-kit-validation", required=True, type=Path, help="Path to Move lab capture kit validation JSON")
    move_lab_preflight.add_argument("--transcript", required=True, type=Path, help="Planned approved Move lab transcript JSON path")
    move_lab_preflight.add_argument("--transcript-validation", required=True, type=Path, help="Planned transcript validation JSON path")
    move_lab_preflight.add_argument("--proof", required=True, type=Path, help="Planned completed approved Move lab proof JSON path")
    move_lab_preflight.add_argument("--proof-validation", required=True, type=Path, help="Planned proof validation JSON path")
    move_lab_preflight.add_argument("--evidence-intake", required=True, type=Path, help="Planned final Move lab evidence intake JSON path")
    move_lab_preflight.add_argument("--lab-ack-env", default="NMRCP_MOVE_LAB_ACK", help="Environment variable that must equal I_UNDERSTAND_LAB_ONLY")
    move_lab_preflight.add_argument("--out", type=Path, help="Optional JSON preflight output path")
    move_lab_preflight.add_argument("--report", type=Path, help="Optional Markdown preflight report path")
    move_lab_preflight.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    move_lab_request = subparsers.add_parser("validate-move-lab-evidence-request", help="Validate generated Move lab evidence request")
    move_lab_request.add_argument("--request", required=True, type=Path, help="Path to move-lab-evidence-request.md")

    move_lab_readiness_packet = subparsers.add_parser("move-lab-readiness-packet", help="Generate a pre-lab Move operator readiness packet")
    move_lab_readiness_packet.add_argument("--payload", required=True, type=Path, help="Path to reviewed dry-run Move API payload JSON")
    move_lab_readiness_packet.add_argument("--review", required=True, type=Path, help="Path to Move submit review JSON")
    move_lab_readiness_packet.add_argument("--move-submit-readiness", required=True, type=Path, help="Path to Move submit readiness JSON")
    move_lab_readiness_packet.add_argument("--capture-kit", required=True, type=Path, help="Path to generated Move lab capture kit directory")
    move_lab_readiness_packet.add_argument("--capture-kit-validation", required=True, type=Path, help="Path to Move lab capture kit validation JSON")
    move_lab_readiness_packet.add_argument("--evidence-preflight", required=True, type=Path, help="Path to Move lab evidence preflight JSON")
    move_lab_readiness_packet.add_argument("--evidence-preflight-report", required=True, type=Path, help="Path to Move lab evidence preflight Markdown report")
    move_lab_readiness_packet.add_argument("--runbook", required=True, type=Path, help="Path to Move lab execution runbook Markdown")
    move_lab_readiness_packet.add_argument("--evidence-request", required=True, type=Path, help="Path to Move lab evidence request Markdown")
    move_lab_readiness_packet.add_argument("--closure-checklist", required=True, type=Path, help="Path to Move lab closure checklist Markdown")
    move_lab_readiness_packet.add_argument("--lab-ack-env", default="NMRCP_MOVE_LAB_ACK", help="Environment variable that must equal I_UNDERSTAND_LAB_ONLY")
    move_lab_readiness_packet.add_argument("--out", required=True, type=Path, help="Move lab readiness packet JSON output path")
    move_lab_readiness_packet.add_argument("--report", type=Path, help="Optional Markdown readiness packet report path")
    move_lab_readiness_packet.add_argument("--json", action="store_true", help="Emit machine-readable validation JSON")

    validate_move_lab_readiness_packet_parser = subparsers.add_parser("validate-move-lab-readiness-packet", help="Validate a pre-lab Move operator readiness packet")
    validate_move_lab_readiness_packet_parser.add_argument("--packet", required=True, type=Path, help="Path to Move lab readiness packet JSON")
    validate_move_lab_readiness_packet_parser.add_argument("--report", type=Path, help="Optional Move lab readiness packet Markdown report")
    validate_move_lab_readiness_packet_parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    source_endpoint_request = subparsers.add_parser("validate-source-endpoint-evidence-request", help="Validate generated source endpoint evidence request")
    source_endpoint_request.add_argument("--request", required=True, type=Path, help="Path to source-endpoint-evidence-request.md")

    move_lab_proof_template = subparsers.add_parser("generate-move-lab-proof-template", help="Generate Move lab proof JSON template")
    move_lab_proof_template.add_argument("--payload", required=True, type=Path, help="Path to dry-run Move API payload JSON")
    move_lab_proof_template.add_argument("--review", required=True, type=Path, help="Path to Move submit review JSON")
    move_lab_proof_template.add_argument(
        "--proof-scope",
        default="simulated_contract",
        choices=["simulated_contract", "approved_lab_move_appliance"],
        help="Proof scope to draft",
    )
    move_lab_proof_template.add_argument("--out", required=True, type=Path, help="Move lab proof JSON output path")

    approved_move_lab_proof = subparsers.add_parser("generate-approved-move-lab-proof", help="Generate approved Move lab proof JSON from clean transcript evidence")
    approved_move_lab_proof.add_argument("--payload", required=True, type=Path, help="Path to reviewed dry-run Move API payload JSON")
    approved_move_lab_proof.add_argument("--review", required=True, type=Path, help="Path to Move submit review JSON")
    approved_move_lab_proof.add_argument("--transcript", required=True, type=Path, help="Path to captured approved Move lab transcript JSON")
    approved_move_lab_proof.add_argument("--transcript-validation", required=True, type=Path, help="Path to passing Move lab transcript validation JSON")
    approved_move_lab_proof.add_argument("--approved-by", required=True, help="Person approving the completed Move lab proof")
    approved_move_lab_proof.add_argument("--notes", default="", help="Optional approved proof notes")
    approved_move_lab_proof.add_argument("--lab-ack-env", default="NMRCP_MOVE_LAB_ACK", help="Environment variable that must equal I_UNDERSTAND_LAB_ONLY")
    approved_move_lab_proof.add_argument("--out", required=True, type=Path, help="Approved Move lab proof JSON output path")

    move_lab_runbook = subparsers.add_parser("generate-move-lab-runbook", help="Generate a redacted lab execution runbook for Move proof")
    move_lab_runbook.add_argument("--payload", required=True, type=Path, help="Path to dry-run Move API payload JSON")
    move_lab_runbook.add_argument("--review", required=True, type=Path, help="Path to Move submit review JSON")
    move_lab_runbook.add_argument("--proof-template", type=Path, help="Optional generated Move lab proof template JSON")
    move_lab_runbook.add_argument("--out", required=True, type=Path, help="Move lab execution runbook Markdown output path")

    validate_move_lab_runbook_parser = subparsers.add_parser("validate-move-lab-runbook", help="Validate generated Move lab execution runbook")
    validate_move_lab_runbook_parser.add_argument("--runbook", required=True, type=Path, help="Path to move-lab-execution-runbook.md")

    doctor = subparsers.add_parser("doctor", help="Run local preflight checks without contacting endpoints")
    doctor.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    serve = subparsers.add_parser("serve", help="Serve the local operations console over HTTP")
    serve.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    serve.add_argument("--port", type=int, default=8080, help="TCP port to bind")
    serve.add_argument("--site-dir", type=Path, default=Path("outputs/console-site"), help="Writable console site directory")
    serve.add_argument("--inventory", type=Path, default=Path("examples/sample_inventory.json"), help="Inventory JSON used to seed the console")
    serve.add_argument("--generate-only", action="store_true", help="Generate the console site and exit without serving HTTP")

    github_readiness = subparsers.add_parser("github-readiness", help="Check local GitHub publication readiness")
    github_readiness.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    github_readiness.add_argument("--expected-remote", default=DEFAULT_REPO_URL, help="Expected GitHub origin URL")
    github_readiness.add_argument("--out", type=Path, help="Optional Markdown publication review output path")
    github_readiness.add_argument("--json-out", type=Path, help="Optional machine-readable publication review JSON output path")
    github_readiness.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    validate_github_review = subparsers.add_parser("validate-github-publication-review", help="Validate GitHub publication review outputs against current readiness")
    validate_github_review.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    validate_github_review.add_argument("--expected-remote", default=DEFAULT_REPO_URL, help="Expected GitHub origin URL")
    validate_github_review.add_argument("--json-report", required=True, type=Path, help="GitHub publication review JSON path")
    validate_github_review.add_argument("--report", type=Path, help="Optional GitHub publication review Markdown path")

    vault_readiness = subparsers.add_parser("vault-readiness", help="Check Obsidian vault documentation coverage")
    vault_readiness.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    vault_readiness.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH, help="Obsidian vault path")
    vault_readiness.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    product_readiness = subparsers.add_parser("product-readiness", help="Run aggregate MVP, GitHub, and vault readiness gates")
    product_readiness.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    product_readiness.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH, help="Obsidian vault path")
    product_readiness.add_argument("--expected-remote", default=DEFAULT_REPO_URL, help="Expected GitHub origin URL")
    product_readiness.add_argument("--assessment-dir", type=Path, help="Optional assessment directory for generated artifact checks")
    product_readiness.add_argument("--assessment-intake", type=Path, help="Optional completed assessment intake CSV bound to live collection proof")
    product_readiness.add_argument("--live-proof", type=Path, help="Optional validated live endpoint proof JSON")
    product_readiness.add_argument("--move-proof", type=Path, help="Optional validated approved lab Move proof JSON")
    product_readiness.add_argument("--evidence-bundle", type=Path, help="Optional verified evidence bundle zip for handoff gate")
    product_readiness.add_argument("--validation-results", type=Path, help="Optional final validation results CSV for handoff gate")
    product_readiness.add_argument("--remediation-tracker", type=Path, help="Optional final remediation tracker CSV for handoff gate")
    product_readiness.add_argument("--signoffs", type=Path, help="Optional final owner sign-off matrix CSV for handoff gate")
    product_readiness.add_argument("--approval-exceptions", type=Path, help="Optional final approval exceptions CSV for handoff gate")
    product_readiness.add_argument("--operator-review", type=Path, help="Optional approved operator review CSV for handoff gate")
    product_readiness.add_argument("--move-lab-capture-validation", type=Path, help="Optional Move lab capture kit validation JSON for handoff gate")
    product_readiness.add_argument("--move-lab-evidence-intake", type=Path, help="Optional final Move lab evidence intake JSON for handoff gate")
    product_readiness.add_argument("--warning-acceptance", type=Path, help="Optional accepted change-gate warning register for handoff gate")
    product_readiness.add_argument("--mvp-proof-package", type=Path, help="Optional verified MVP proof package zip for aggregate package evidence")
    product_readiness.add_argument("--github-publication-review", type=Path, help="Optional GitHub publication review Markdown for aggregate publication evidence")
    product_readiness.add_argument("--github-publication-review-json", type=Path, help="Optional GitHub publication review JSON for aggregate publication evidence")
    product_readiness.add_argument("--publication-staging-manifest", type=Path, help="Optional publication staging manifest Markdown for aggregate publication evidence")
    product_readiness.add_argument("--publication-staging-manifest-json", type=Path, help="Optional publication staging manifest JSON for aggregate publication evidence")
    product_readiness.add_argument("--out", type=Path, help="Optional Markdown product readiness report output path")
    product_readiness.add_argument("--json-out", type=Path, help="Optional machine-readable product readiness report JSON output path")
    product_readiness.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    validate_product_report = subparsers.add_parser("validate-product-readiness-report", help="Validate product readiness report outputs against current aggregate readiness")
    validate_product_report.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    validate_product_report.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH, help="Obsidian vault path")
    validate_product_report.add_argument("--expected-remote", default=DEFAULT_REPO_URL, help="Expected GitHub origin URL")
    validate_product_report.add_argument("--json-report", required=True, type=Path, help="Product readiness JSON report")
    validate_product_report.add_argument("--report", type=Path, help="Optional Product readiness Markdown report")
    validate_product_report.add_argument("--assessment-dir", type=Path, help="Optional assessment directory for generated artifact checks")
    validate_product_report.add_argument("--assessment-intake", type=Path, help="Optional completed assessment intake CSV bound to live collection proof")
    validate_product_report.add_argument("--live-proof", type=Path, help="Optional validated live endpoint proof JSON")
    validate_product_report.add_argument("--move-proof", type=Path, help="Optional validated approved lab Move proof JSON")
    validate_product_report.add_argument("--evidence-bundle", type=Path, help="Optional verified evidence bundle zip for handoff gate")
    validate_product_report.add_argument("--validation-results", type=Path, help="Optional final validation results CSV for handoff gate")
    validate_product_report.add_argument("--remediation-tracker", type=Path, help="Optional final remediation tracker CSV for handoff gate")
    validate_product_report.add_argument("--signoffs", type=Path, help="Optional final owner sign-off matrix CSV for handoff gate")
    validate_product_report.add_argument("--approval-exceptions", type=Path, help="Optional final approval exceptions CSV for handoff gate")
    validate_product_report.add_argument("--operator-review", type=Path, help="Optional approved operator review CSV for handoff gate")
    validate_product_report.add_argument("--move-lab-capture-validation", type=Path, help="Optional Move lab capture kit validation JSON for handoff gate")
    validate_product_report.add_argument("--move-lab-evidence-intake", type=Path, help="Optional final Move lab evidence intake JSON for handoff gate")
    validate_product_report.add_argument("--warning-acceptance", type=Path, help="Optional accepted change-gate warning register for handoff gate")
    validate_product_report.add_argument("--mvp-proof-package", type=Path, help="Optional verified MVP proof package zip for aggregate package evidence")
    validate_product_report.add_argument("--github-publication-review", type=Path, help="Optional GitHub publication review Markdown for aggregate publication evidence")
    validate_product_report.add_argument("--github-publication-review-json", type=Path, help="Optional GitHub publication review JSON for aggregate publication evidence")
    validate_product_report.add_argument("--publication-staging-manifest", type=Path, help="Optional publication staging manifest Markdown for aggregate publication evidence")
    validate_product_report.add_argument("--publication-staging-manifest-json", type=Path, help="Optional publication staging manifest JSON for aggregate publication evidence")

    publication_handoff = subparsers.add_parser("publication-handoff", help="Build branch-owner publication handoff evidence from current readiness reports")
    publication_handoff.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    publication_handoff.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH, help="Obsidian vault path")
    publication_handoff.add_argument("--expected-remote", default=DEFAULT_REPO_URL, help="Expected GitHub origin URL")
    publication_handoff.add_argument("--github-publication-review", required=True, type=Path, help="GitHub publication review Markdown")
    publication_handoff.add_argument("--github-publication-review-json", required=True, type=Path, help="GitHub publication review JSON")
    publication_handoff.add_argument("--product-readiness-report", required=True, type=Path, help="Product readiness Markdown report")
    publication_handoff.add_argument("--product-readiness-report-json", required=True, type=Path, help="Product readiness JSON report")
    publication_handoff.add_argument("--smoke-log", required=True, type=Path, help="Smoke-test transcript log")
    publication_handoff.add_argument("--security-scan-status", default="pass", help="Latest security scan status, usually pass")
    publication_handoff.add_argument("--out", type=Path, help="Optional Markdown publication handoff output path")
    publication_handoff.add_argument("--json-out", type=Path, help="Optional machine-readable publication handoff JSON output path")
    publication_handoff.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    validate_publication_handoff_parser = subparsers.add_parser("validate-publication-handoff", help="Validate publication handoff outputs against current readiness artifacts")
    validate_publication_handoff_parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    validate_publication_handoff_parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH, help="Obsidian vault path")
    validate_publication_handoff_parser.add_argument("--expected-remote", default=DEFAULT_REPO_URL, help="Expected GitHub origin URL")
    validate_publication_handoff_parser.add_argument("--github-publication-review", required=True, type=Path, help="GitHub publication review Markdown")
    validate_publication_handoff_parser.add_argument("--github-publication-review-json", required=True, type=Path, help="GitHub publication review JSON")
    validate_publication_handoff_parser.add_argument("--product-readiness-report", required=True, type=Path, help="Product readiness Markdown report")
    validate_publication_handoff_parser.add_argument("--product-readiness-report-json", required=True, type=Path, help="Product readiness JSON report")
    validate_publication_handoff_parser.add_argument("--smoke-log", required=True, type=Path, help="Smoke-test transcript log")
    validate_publication_handoff_parser.add_argument("--security-scan-status", default="pass", help="Latest security scan status, usually pass")
    validate_publication_handoff_parser.add_argument("--report", type=Path, help="Optional publication handoff Markdown report")
    validate_publication_handoff_parser.add_argument("--json-report", required=True, type=Path, help="Publication handoff JSON report")

    publication_staging = subparsers.add_parser("publication-staging-manifest", help="Build a non-mutating Git publication staging manifest")
    publication_staging.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    publication_staging.add_argument("--out", type=Path, help="Optional Markdown staging manifest output path")
    publication_staging.add_argument("--json-out", type=Path, help="Optional machine-readable staging manifest JSON output path")
    publication_staging.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    validate_publication_staging = subparsers.add_parser("validate-publication-staging-manifest", help="Validate publication staging manifest against current files")
    validate_publication_staging.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    validate_publication_staging.add_argument("--json-report", required=True, type=Path, help="Publication staging manifest JSON report")
    validate_publication_staging.add_argument("--report", type=Path, help="Optional publication staging manifest Markdown report")

    pull_request_readiness = subparsers.add_parser("pull-request-readiness", help="Build a branch-owner pull request readiness packet")
    pull_request_readiness.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    pull_request_readiness.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH, help="Obsidian vault path")
    pull_request_readiness.add_argument("--expected-remote", default=DEFAULT_REPO_URL, help="Expected GitHub origin URL")
    pull_request_readiness.add_argument("--github-publication-review", required=True, type=Path, help="GitHub publication review Markdown")
    pull_request_readiness.add_argument("--github-publication-review-json", required=True, type=Path, help="GitHub publication review JSON")
    pull_request_readiness.add_argument("--product-readiness-report", required=True, type=Path, help="Product readiness Markdown report")
    pull_request_readiness.add_argument("--product-readiness-report-json", required=True, type=Path, help="Product readiness JSON report")
    pull_request_readiness.add_argument("--publication-handoff", required=True, type=Path, help="Publication handoff Markdown")
    pull_request_readiness.add_argument("--publication-handoff-json", required=True, type=Path, help="Publication handoff JSON")
    pull_request_readiness.add_argument("--publication-staging-manifest", required=True, type=Path, help="Publication staging manifest Markdown")
    pull_request_readiness.add_argument("--publication-staging-manifest-json", required=True, type=Path, help="Publication staging manifest JSON")
    pull_request_readiness.add_argument("--smoke-log", required=True, type=Path, help="Smoke-test transcript log")
    pull_request_readiness.add_argument("--security-scan-status", default="pass", help="Latest security scan status, usually pass")
    pull_request_readiness.add_argument("--out", type=Path, help="Optional Markdown pull request readiness packet output path")
    pull_request_readiness.add_argument("--json-out", type=Path, help="Optional machine-readable pull request readiness packet JSON output path")
    pull_request_readiness.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    validate_pull_request_readiness_parser = subparsers.add_parser("validate-pull-request-readiness", help="Validate pull request readiness packet against current artifacts")
    validate_pull_request_readiness_parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    validate_pull_request_readiness_parser.add_argument("--vault", type=Path, default=DEFAULT_VAULT_PATH, help="Obsidian vault path")
    validate_pull_request_readiness_parser.add_argument("--expected-remote", default=DEFAULT_REPO_URL, help="Expected GitHub origin URL")
    validate_pull_request_readiness_parser.add_argument("--github-publication-review", required=True, type=Path, help="GitHub publication review Markdown")
    validate_pull_request_readiness_parser.add_argument("--github-publication-review-json", required=True, type=Path, help="GitHub publication review JSON")
    validate_pull_request_readiness_parser.add_argument("--product-readiness-report", required=True, type=Path, help="Product readiness Markdown report")
    validate_pull_request_readiness_parser.add_argument("--product-readiness-report-json", required=True, type=Path, help="Product readiness JSON report")
    validate_pull_request_readiness_parser.add_argument("--publication-handoff", required=True, type=Path, help="Publication handoff Markdown")
    validate_pull_request_readiness_parser.add_argument("--publication-handoff-json", required=True, type=Path, help="Publication handoff JSON")
    validate_pull_request_readiness_parser.add_argument("--publication-staging-manifest", required=True, type=Path, help="Publication staging manifest Markdown")
    validate_pull_request_readiness_parser.add_argument("--publication-staging-manifest-json", required=True, type=Path, help="Publication staging manifest JSON")
    validate_pull_request_readiness_parser.add_argument("--smoke-log", required=True, type=Path, help="Smoke-test transcript log")
    validate_pull_request_readiness_parser.add_argument("--security-scan-status", default="pass", help="Latest security scan status, usually pass")
    validate_pull_request_readiness_parser.add_argument("--report", type=Path, help="Optional pull request readiness Markdown report")
    validate_pull_request_readiness_parser.add_argument("--json-report", required=True, type=Path, help="Pull request readiness JSON report")

    external_proof_plan = subparsers.add_parser("external-proof-plan", help="Build the approved endpoint and Move proof closeout plan")
    external_proof_plan.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    external_proof_plan.add_argument("--assessment-intake", type=Path, help="Optional completed assessment intake CSV bound to live collection proof")
    external_proof_plan.add_argument("--live-proof", type=Path, help="Optional validated live endpoint proof JSON")
    external_proof_plan.add_argument("--move-proof", type=Path, help="Optional validated approved lab Move proof JSON")
    external_proof_plan.add_argument("--move-lab-evidence-intake", type=Path, help="Optional final Move lab evidence intake JSON")
    external_proof_plan.add_argument("--out", type=Path, help="Optional Markdown external proof plan output path")
    external_proof_plan.add_argument("--json-out", type=Path, help="Optional machine-readable external proof plan JSON output path")
    external_proof_plan.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    validate_external_proof_plan_parser = subparsers.add_parser("validate-external-proof-plan", help="Validate the external proof closeout plan against current MVP proof gaps")
    validate_external_proof_plan_parser.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    validate_external_proof_plan_parser.add_argument("--assessment-intake", type=Path, help="Optional completed assessment intake CSV bound to live collection proof")
    validate_external_proof_plan_parser.add_argument("--live-proof", type=Path, help="Optional validated live endpoint proof JSON")
    validate_external_proof_plan_parser.add_argument("--move-proof", type=Path, help="Optional validated approved lab Move proof JSON")
    validate_external_proof_plan_parser.add_argument("--move-lab-evidence-intake", type=Path, help="Optional final Move lab evidence intake JSON")
    validate_external_proof_plan_parser.add_argument("--report", type=Path, help="Optional external proof plan Markdown report")
    validate_external_proof_plan_parser.add_argument("--json-report", required=True, type=Path, help="External proof plan JSON report")

    mvp_audit = subparsers.add_parser("mvp-audit", help="Audit local MVP requirement evidence and remaining proof gaps")
    mvp_audit.add_argument("--repo-root", type=Path, default=Path.cwd(), help="Repository root to inspect")
    mvp_audit.add_argument("--assessment-dir", type=Path, help="Optional assessment directory for generated artifact checks")
    mvp_audit.add_argument("--assessment-intake", type=Path, help="Optional completed assessment intake CSV bound to live collection proof")
    mvp_audit.add_argument("--live-proof", type=Path, help="Optional validated live endpoint proof JSON")
    mvp_audit.add_argument("--move-proof", type=Path, help="Optional validated approved lab Move proof JSON")
    mvp_audit.add_argument("--evidence-bundle", type=Path, help="Optional verified evidence bundle zip for handoff gate")
    mvp_audit.add_argument("--validation-results", type=Path, help="Optional final validation results CSV for handoff gate")
    mvp_audit.add_argument("--remediation-tracker", type=Path, help="Optional final remediation tracker CSV for handoff gate")
    mvp_audit.add_argument("--signoffs", type=Path, help="Optional final owner sign-off matrix CSV for handoff gate")
    mvp_audit.add_argument("--approval-exceptions", type=Path, help="Optional final approval exceptions CSV for handoff gate")
    mvp_audit.add_argument("--operator-review", type=Path, help="Optional approved operator review CSV for handoff gate")
    mvp_audit.add_argument("--move-lab-capture-validation", type=Path, help="Optional Move lab capture kit validation JSON for handoff gate")
    mvp_audit.add_argument("--move-lab-evidence-intake", type=Path, help="Optional final Move lab evidence intake JSON for handoff gate")
    mvp_audit.add_argument("--warning-acceptance", type=Path, help="Optional accepted change-gate warning register for handoff gate")
    mvp_audit.add_argument("--out", type=Path, help="Optional JSON audit output path")
    mvp_audit.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    package = subparsers.add_parser("package-evidence", help="Package assessment evidence from a manifest into a zip")
    package.add_argument("--dir", required=True, type=Path, help="Assessment output directory")
    package.add_argument("--out", required=True, type=Path, help="Evidence bundle zip path")

    verify = subparsers.add_parser("verify-evidence", help="Verify evidence artifacts or bundle against manifest")
    verify.add_argument("--dir", type=Path, help="Assessment output directory")
    verify.add_argument("--bundle", type=Path, help="Evidence bundle zip path")

    review = subparsers.add_parser("review-evidence", help="Scan assessment evidence for redaction leaks")
    review.add_argument("--dir", required=True, type=Path, help="Assessment output directory")

    handoff = subparsers.add_parser("package-handoff", help="Package assessment, validation, and Move handoff artifacts")
    handoff.add_argument("--dir", required=True, type=Path, help="Assessment output directory")
    handoff.add_argument("--out", required=True, type=Path, help="Handoff package zip path")
    handoff.add_argument("--bundle", type=Path, help="Optional verified evidence bundle zip path")
    handoff.add_argument("--validation-results", type=Path, help="Optional final validation results CSV")
    handoff.add_argument("--remediation-tracker", type=Path, help="Optional final remediation tracker CSV")
    handoff.add_argument("--signoffs", type=Path, help="Optional final owner sign-off matrix CSV")
    handoff.add_argument("--approval-exceptions", type=Path, help="Optional final approval exceptions CSV")
    handoff.add_argument("--operator-review", type=Path, help="Optional approved operator assessment review CSV")
    handoff.add_argument("--move-lab-proof", type=Path, help="Optional approved Move lab proof validation JSON")
    handoff.add_argument("--move-lab-readiness-packet", type=Path, help="Optional pre-lab Move readiness packet JSON")
    handoff.add_argument("--move-lab-evidence-intake", type=Path, help="Optional final Move lab evidence intake JSON")
    handoff.add_argument("--move-lab-capture-kit", type=Path, help="Optional Move lab capture kit directory")
    handoff.add_argument("--move-lab-capture-validation", type=Path, help="Optional Move lab capture kit validation JSON")
    handoff.add_argument("--source-collection-plan", type=Path, help="Optional source collection plan Markdown")
    handoff.add_argument("--move-payload", type=Path, help="Optional dry-run Move payload JSON")

    verify_handoff = subparsers.add_parser("verify-handoff", help="Verify a handoff package zip")
    verify_handoff.add_argument("--package", required=True, type=Path, help="Handoff package zip path")

    mvp_proof = subparsers.add_parser("package-mvp-proof", help="Package MVP readiness proof artifacts into a verified zip")
    mvp_proof.add_argument("--mvp-audit", required=True, type=Path, help="Path to mvp-audit JSON")
    mvp_proof.add_argument("--live-proof", type=Path, help="Optional live endpoint proof validation JSON")
    mvp_proof.add_argument("--move-submit-readiness", type=Path, help="Optional Move submit readiness JSON")
    mvp_proof.add_argument("--move-lab-transcript", type=Path, help="Optional Move lab transcript validation JSON")
    mvp_proof.add_argument("--move-lab-proof", type=Path, help="Optional Move lab proof validation JSON")
    mvp_proof.add_argument("--move-lab-runbook", type=Path, help="Optional Move lab execution runbook Markdown")
    mvp_proof.add_argument("--move-lab-closure-checklist", type=Path, help="Optional Move lab closure checklist Markdown")
    mvp_proof.add_argument("--move-lab-capture-kit", type=Path, help="Optional Move lab capture kit directory")
    mvp_proof.add_argument("--move-lab-capture-validation", type=Path, help="Optional Move lab capture kit validation JSON")
    mvp_proof.add_argument("--move-lab-readiness-packet", type=Path, help="Optional Move lab readiness packet JSON")
    mvp_proof.add_argument("--move-lab-evidence-intake", type=Path, help="Optional Move lab evidence intake JSON")
    mvp_proof.add_argument("--source-collection-plan", type=Path, help="Optional source collection plan Markdown")
    mvp_proof.add_argument("--source-endpoint-evidence-request", type=Path, help="Optional source endpoint evidence request Markdown")
    mvp_proof.add_argument("--move-lab-evidence-request", type=Path, help="Optional Move lab evidence request Markdown")
    mvp_proof.add_argument("--external-proof-plan", type=Path, help="Optional external proof gap plan JSON")
    mvp_proof.add_argument("--operator-gate-summary", type=Path, help="Optional operator gate summary Markdown")
    mvp_proof.add_argument("--handoff-package", type=Path, help="Optional handoff package zip")
    mvp_proof.add_argument("--out", required=True, type=Path, help="MVP proof package zip path")

    verify_mvp_proof = subparsers.add_parser("verify-mvp-proof", help="Verify an MVP proof package zip")
    verify_mvp_proof.add_argument("--package", required=True, type=Path, help="MVP proof package zip path")

    summarize_mvp_proof = subparsers.add_parser("summarize-mvp-proof", help="Summarize an MVP proof package for reviewers")
    summarize_mvp_proof.add_argument("--package", required=True, type=Path, help="MVP proof package zip path")
    summarize_mvp_proof.add_argument("--out", type=Path, help="Optional Markdown summary output path")
    summarize_mvp_proof.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    validate_mvp_summary = subparsers.add_parser("validate-mvp-proof-summary", help="Validate MVP proof summary Markdown against an MVP proof package")
    validate_mvp_summary.add_argument("--package", required=True, type=Path, help="MVP proof package zip path")
    validate_mvp_summary.add_argument("--summary", required=True, type=Path, help="MVP proof summary Markdown path")

    closure_mvp_proof = subparsers.add_parser("mvp-closure-report", help="Write reviewer closure actions from an MVP proof package")
    closure_mvp_proof.add_argument("--package", required=True, type=Path, help="MVP proof package zip path")
    closure_mvp_proof.add_argument("--out", type=Path, help="Optional Markdown closure report output path")
    closure_mvp_proof.add_argument("--json-out", type=Path, help="Optional machine-readable closure report JSON output path")
    closure_mvp_proof.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    validate_closure_mvp_proof = subparsers.add_parser("validate-mvp-closure-report", help="Validate MVP closure report outputs against an MVP proof package")
    validate_closure_mvp_proof.add_argument("--package", required=True, type=Path, help="MVP proof package zip path")
    validate_closure_mvp_proof.add_argument("--json-report", required=True, type=Path, help="MVP closure JSON report")
    validate_closure_mvp_proof.add_argument("--report", type=Path, help="Optional Markdown MVP closure report")

    launch_readiness = subparsers.add_parser("launch-readiness-report", help="Write partner/customer launch readiness from an MVP proof package")
    launch_readiness.add_argument("--package", required=True, type=Path, help="MVP proof package zip path")
    launch_readiness.add_argument("--out", type=Path, help="Optional Markdown launch readiness report output path")
    launch_readiness.add_argument("--json-out", type=Path, help="Optional machine-readable launch readiness JSON output path")
    launch_readiness.add_argument("--repo-url", default="", help="Optional GitHub repository URL to show in the report")
    launch_readiness.add_argument("--audience", default="partners, MSPs, migration operators, and change boards", help="Audience label to show in the report")
    launch_readiness.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    validate_launch_readiness = subparsers.add_parser("validate-launch-readiness-report", help="Validate launch readiness report outputs against an MVP proof package")
    validate_launch_readiness.add_argument("--package", required=True, type=Path, help="MVP proof package zip path")
    validate_launch_readiness.add_argument("--json-report", required=True, type=Path, help="Launch readiness JSON report")
    validate_launch_readiness.add_argument("--report", type=Path, help="Optional Markdown launch readiness report")

    warning_acceptance = subparsers.add_parser("validate-warning-acceptance", help="Validate accepted change-gate warnings")
    warning_acceptance.add_argument("--acceptance", required=True, type=Path, help="Warning acceptance CSV")
    warning_acceptance.add_argument("--warnings", required=True, type=Path, help="Change-gate JSON file containing warnings")

    gate = subparsers.add_parser("change-gate", help="Run change-board readiness checks over assessment evidence")
    gate.add_argument("--dir", required=True, type=Path, help="Assessment output directory")
    gate.add_argument("--bundle", type=Path, help="Optional evidence bundle zip path")
    gate.add_argument("--validation-results", type=Path, help="Optional final validation results CSV")
    gate.add_argument("--remediation-tracker", type=Path, help="Optional final remediation tracker CSV")
    gate.add_argument("--signoffs", type=Path, help="Optional filled owner sign-off matrix CSV")
    gate.add_argument("--approval-exceptions", type=Path, help="Optional filled approval exceptions CSV")
    gate.add_argument("--operator-review", type=Path, help="Optional filled operator assessment review CSV")
    gate.add_argument("--move-lab-capture-validation", type=Path, help="Optional Move lab capture kit validation JSON")
    gate.add_argument("--move-lab-proof", type=Path, help="Optional approved Move lab proof validation JSON")
    gate.add_argument("--move-lab-evidence-intake", type=Path, help="Optional final Move lab evidence intake JSON")
    gate.add_argument("--allow-pending-signoffs", action="store_true", help="Allow pending sign-off rows during draft review")
    gate.add_argument("--allow-draft-operator-review", action="store_true", help="Allow draft operator review rows during draft review")
    gate.add_argument("--json", action="store_true", help="Emit machine-readable JSON")

    args = parser.parse_args(argv)
    if args.command == "assess":
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        if args.metadata:
            inventory = merge_metadata(inventory, read_metadata_csv(args.metadata))
        if args.dependencies:
            inventory = merge_dependencies(inventory, read_dependency_csv(args.dependencies))
        inventory_validation = validate_inventory(inventory)
        if not inventory_validation.ok or (args.strict_inventory and inventory_validation.warnings):
            print(inventory_validation.summary())
            for warning in inventory_validation.warnings:
                print(f"WARNING: {warning}")
            for error in inventory_validation.errors:
                print(f"ERROR: {error}")
            return 1
        policy = load_readiness_policy(args.policy)
        assessments = assess_inventory(inventory, target=args.target, policy=policy)
        assessments = apply_dependency_readiness_gates(inventory, assessments)
        waves = plan_waves(assessments, inventory)
        write_assessment(inventory, assessments, waves, args.out, policy=policy.to_dict())
        if args.capacity:
            capacity_result = validate_capacity_fit(args.inventory, args.out / "nutanix-move-plan.csv", args.capacity)
            write_capacity_fit_csv(capacity_result, args.out / "target-capacity-fit.csv")
            from .evidence import write_evidence_manifest

            write_evidence_manifest(args.out / "evidence-manifest.json", args.out)
            print(capacity_result.summary())
            for warning in capacity_result.warnings:
                print(f"WARNING: {warning}")
            for error in capacity_result.errors:
                print(f"ERROR: {error}")
            if not capacity_result.ok:
                return 1
        print(f"Assessed {len(assessments)} workloads into {args.out}")
        return 0
    if args.command == "run-assessment":
        result = run_assessment_workflow(
            args.inventory,
            args.out,
            metadata_path=args.metadata,
            dependencies_path=args.dependencies,
            target=args.target,
            policy_path=args.policy,
            capacity_path=args.capacity,
            prism_inventory_path=args.prism_inventory,
            source_networks_path=args.source_networks,
            strict_inventory=args.strict_inventory,
            move_config_path=args.move_config,
            validation_results_path=args.validation_results,
            remediation_tracker_path=args.remediation_tracker,
            signoffs_path=args.signoffs,
            approval_exceptions_path=args.approval_exceptions,
            operator_review_path=args.operator_review,
            move_lab_capture_kit_dir=args.move_lab_capture_kit,
            move_lab_capture_validation_path=args.move_lab_capture_validation,
            move_lab_proof_path=args.move_lab_proof,
            move_lab_readiness_packet_path=args.move_lab_readiness_packet,
            move_lab_evidence_intake_path=args.move_lab_evidence_intake,
            validation_template_out=args.validation_template_out,
            bundle_out=args.bundle_out,
            handoff_out=args.handoff_out,
            move_payload_out=args.move_payload_out,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"NMRCP assessment workflow: {result['status'].upper()}")
            for check in result["checks"]:
                print(f"[{check['status']}] {check['name']}: {check['detail']}")
            for warning in result["warnings"]:
                print(f"WARNING: {warning}")
            for error in result["errors"]:
                print(f"ERROR: {error}")
            print(f"Assessment directory: {result['paths']['assessment_dir']}")
            print(f"Evidence bundle: {result['paths']['evidence_bundle']}")
            print(f"Handoff package: {result['paths']['handoff_package']}")
        return 0 if result["status"] == "pass" else 1
    if args.command == "validate-inventory":
        result = validate_inventory_file(args.inventory)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok and (not args.strict or not result.warnings) else 1
    if args.command == "validate-inventory-coverage":
        result = validate_inventory_coverage_csv(
            args.coverage,
            args.move_plan,
            minimum_coverage_percent=args.minimum_coverage_percent,
        )
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-collection-audit":
        result = validate_collection_audit_file(args.inventory)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "import-rvtools":
        inventory = import_rvtools_directory(args.dir, source_name=args.source_name)
        write_json(args.out, inventory)
        print(f"Imported {len(inventory['workloads'])} RVTools workloads into {args.out}")
        return 0
    if args.command == "collect-vcenter":
        config = endpoint_config(args.endpoint, args.username, args.password_env, not args.insecure)
        client = VCenterClient(config)
        vm_summaries = client.list_vms()
        details_by_vm = {}
        for vm in vm_summaries[: args.details_limit]:
            vm_id = vm.get("vm")
            if isinstance(vm_id, str):
                details_by_vm[vm_id] = client.get_vm_details(vm_id)
        networks = client.list_networks()
        inventory = normalize_vcenter_inventory(
            config.base_url,
            vm_summaries,
            details_by_vm,
            details_limit=args.details_limit,
            network_count=len(networks),
        )
        write_json(args.out, inventory)
        print(f"Collected {len(inventory['workloads'])} vCenter workloads into {args.out}")
        return 0
    if args.command == "probe-vcenter":
        config = endpoint_config(args.endpoint, args.username, args.password_env, not args.insecure)
        client = VCenterClient(config)
        client.login()
        vm_count = len(client.list_vms())
        print(f"PASS: vCenter probe succeeded; vm_count={vm_count}; endpoint_configured=yes")
        return 0
    if args.command == "collect-prism":
        config = endpoint_config(args.endpoint, args.username, args.password_env, not args.insecure)
        client = PrismCentralClient(config)
        entities = client.list_vms(page_size=args.page_size, max_pages=args.max_pages)
        inventory = normalize_prism_inventory(config.base_url, entities, page_size=args.page_size, max_pages=args.max_pages)
        write_json(args.out, inventory)
        print(f"Collected {len(inventory['workloads'])} Prism workloads into {args.out}")
        return 0
    if args.command == "collect-prism-capacity":
        config = endpoint_config(args.endpoint, args.username, args.password_env, not args.insecure)
        client = PrismCentralClient(config)
        clusters = client.list_clusters(page_size=args.page_size)
        capacity = normalize_prism_capacity(
            clusters,
            target=args.target,
            cpu_reserved_percent=args.cpu_reserved_percent,
            memory_reserved_percent=args.memory_reserved_percent,
            storage_reserved_percent=args.storage_reserved_percent,
            cpu_overcommit_ratio=args.cpu_overcommit_ratio,
        )
        write_json(args.out, capacity)
        print(f"Collected Prism target capacity for {len(clusters)} clusters into {args.out}")
        return 0
    if args.command == "collect-sources":
        vcenter_config = endpoint_config(args.vcenter_endpoint, args.vcenter_username, args.vcenter_password_env, not args.insecure)
        prism_config = endpoint_config(args.prism_endpoint, args.prism_username, args.prism_password_env, not args.insecure)
        try:
            result = collect_sources(
                vcenter_config,
                prism_config,
                args.out_dir,
                vcenter_details_limit=args.vcenter_details_limit,
                prism_page_size=args.prism_page_size,
                prism_max_pages=args.prism_max_pages,
                prism_capacity_page_size=args.prism_capacity_page_size,
                target=args.target,
                cpu_reserved_percent=args.cpu_reserved_percent,
                memory_reserved_percent=args.memory_reserved_percent,
                storage_reserved_percent=args.storage_reserved_percent,
                cpu_overcommit_ratio=args.cpu_overcommit_ratio,
                assessment_intake_path=args.assessment_intake,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 1
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"Collected read-only source artifacts into {args.out_dir}")
            for check in result["checks"]:
                count = check.get("workloads", check.get("networks", check.get("targets", 0)))
                print(f"[{check['status']}] {check['name']}: count={count}; mutating_calls={check['mutating_calls']}")
            print(f"Summary: {args.out_dir / 'collection-summary.json'}")
            print(f"Proof manifest: {args.out_dir / 'collection-proof-manifest.json'}")
            print(f"Proof report: {args.out_dir / 'collection-proof-report.md'}")
            if result.get("governance", {}).get("assessment_intake"):
                print("Assessment intake: validated and bound by checksum")
        return 0
    if args.command == "generate-assessment-intake":
        output = write_assessment_intake_template(args.out)
        print(f"Generated assessment intake template into {output}")
        return 0
    if args.command == "validate-assessment-intake":
        result = validate_assessment_intake(args.intake)
        if args.json:
            print(
                json.dumps(
                    {
                        "schema_version": "nmrcp_assessment_intake_validation_v1",
                        "status": "pass" if result.ok else "fail",
                        "rows": result.rows,
                        "errors": list(result.errors),
                        "warnings": list(result.warnings),
                    },
                    indent=2,
                )
            )
        else:
            print(result.summary())
            for warning in result.warnings:
                print(f"WARNING: {warning}")
            for error in result.errors:
                print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "source-collection-plan":
        result = write_source_collection_plan(args.intake, args.out)
        print(result.summary())
        if result.ok:
            print(f"Wrote source collection plan: {args.out}")
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-source-collection-plan":
        result = validate_source_collection_plan(args.plan, args.intake)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "collection-proof-report":
        result = write_collection_proof_report(args.collection_summary, args.out)
        print(result.summary())
        if result.ok:
            print(f"Wrote collection proof report: {args.out}")
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-collection-proof-report":
        result = validate_collection_proof_report(args.report, collection_summary_path=args.collection_summary)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "probe-prism":
        config = endpoint_config(args.endpoint, args.username, args.password_env, not args.insecure)
        client = PrismCentralClient(config)
        cluster_count = len(client.list_clusters())
        vm_count = len(client.list_vms(page_size=1, max_pages=1))
        print(
            f"PASS: Prism Central probe succeeded; cluster_count={cluster_count}; "
            f"sample_vm_count={vm_count}; endpoint_configured=yes"
        )
        return 0
    if args.command == "live-readiness":
        result = run_live_readiness(
            vcenter_config=optional_endpoint_config(
                os.getenv("NMRCP_VCENTER_URL"),
                os.getenv("NMRCP_VCENTER_USERNAME"),
                "NMRCP_VCENTER_PASSWORD",
                verify_tls=not args.insecure,
            ),
            prism_config=optional_endpoint_config(
                os.getenv("NMRCP_PRISM_URL"),
                os.getenv("NMRCP_PRISM_USERNAME"),
                "NMRCP_PRISM_PASSWORD",
                verify_tls=not args.insecure,
            ),
            require_vcenter=args.require_vcenter,
            require_prism=args.require_prism,
            prism_page_size=args.prism_page_size,
            prism_max_pages=args.prism_max_pages,
        )
        if args.out:
            write_json(args.out, result)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"NMRCP live readiness: {result['status'].upper()}")
            for check in result["checks"]:
                counts = check.get("counts", {})
                detail = check.get("detail") or ", ".join(f"{key}={value}" for key, value in counts.items())
                print(f"[{check['status']}] {check['name']}: configured={check['configured']}; {detail}")
            if args.out:
                print(f"Wrote redacted live readiness proof: {args.out}")
        return 0 if result["status"] != "fail" else 1
    if args.command == "validate-live-proof":
        result = validate_live_proof(
            args.live_readiness,
            collection_summary_path=args.collection_summary,
            source_dir=args.source_dir,
        )
        if args.out:
            write_json(args.out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            for check in result.checks:
                print(f"[{check['status']}] {check['name']}: {check['detail']}")
            for warning in result.warnings:
                print(f"WARNING: {warning}")
            for error in result.errors:
                print(f"ERROR: {error}")
            if args.out:
                print(f"Wrote live proof validation: {args.out}")
        return 0 if result.ok else 1
    if args.command == "enrich-dependencies":
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        dependencies = read_dependency_csv(args.dependencies)
        enriched = merge_dependencies(inventory, dependencies)
        write_json(args.out, enriched)
        print(
            f"Merged {len(dependencies)} dependency records into {args.out}; "
            f"unmatched={len(enriched.get('unmatched_dependencies', []))}"
        )
        return 0
    if args.command == "import-app-map":
        records = read_app_map(args.map)
        write_dependency_csv(records, args.out)
        print(f"Imported {len(records)} app-map dependency records into {args.out}")
        return 0
    if args.command == "enrich-metadata":
        inventory = json.loads(args.inventory.read_text(encoding="utf-8"))
        metadata = read_metadata_csv(args.metadata)
        enriched = merge_metadata(inventory, metadata)
        write_json(args.out, enriched)
        print(
            f"Merged {len(metadata)} metadata records into {args.out}; "
            f"unmatched={len(enriched.get('unmatched_metadata', []))}"
        )
        return 0
    if args.command == "import-cmdb-metadata":
        records = import_cmdb_metadata_csv(args.export)
        write_metadata_csv(records, args.out)
        print(f"Imported {len(records)} CMDB metadata records into {args.out}")
        return 0
    if args.command == "validate-move-plan":
        result = validate_move_plan(args.plan, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "move-plan-brief":
        result = write_move_plan_brief(args.plan, args.assessment, args.out)
        print(result.summary())
        if result.ok:
            print(f"Wrote Move plan brief: {args.out}")
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-move-plan-brief":
        result = validate_move_plan_brief(args.brief, args.plan, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-capacity":
        result = validate_capacity_fit(args.inventory, args.plan, args.capacity)
        if args.out:
            write_capacity_fit_csv(result, args.out)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-network-mappings":
        result = validate_network_mappings(args.plan, args.config)
        if args.out:
            write_network_mapping_csv(result, args.out)
            manifest = args.out.parent / "evidence-manifest.json"
            if manifest.exists():
                from .evidence import write_evidence_manifest

                write_evidence_manifest(manifest, args.out.parent)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-source-networks":
        result = validate_source_networks(args.plan, args.networks)
        if args.out:
            write_source_network_validation_csv(result, args.out)
            manifest = args.out.parent / "evidence-manifest.json"
            if manifest.exists():
                from .evidence import write_evidence_manifest

                write_evidence_manifest(manifest, args.out.parent)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-source-network-results":
        result = validate_source_network_validation_csv(args.results)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "reconcile-target":
        result = reconcile_target_inventory(args.inventory, args.target_inventory, args.plan)
        if args.out:
            write_target_reconciliation_csv(result, args.out)
            manifest = args.out.parent / "evidence-manifest.json"
            if manifest.exists():
                from .evidence import write_evidence_manifest

                write_evidence_manifest(manifest, args.out.parent)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-target-reconciliation":
        result = validate_target_reconciliation_csv(args.reconciliation)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "summarize-gates":
        output = write_operator_gate_summary(
            args.dir,
            out_path=args.out,
            validation_results_path=args.validation_results,
            remediation_tracker_path=args.remediation_tracker,
            signoffs_path=args.signoffs,
            approval_exceptions_path=args.approval_exceptions,
            operator_review_path=args.operator_review,
            move_lab_capture_validation_path=args.move_lab_capture_validation,
            move_lab_proof_path=args.move_lab_proof,
            move_lab_evidence_intake_path=args.move_lab_evidence_intake,
        )
        manifest = args.dir / "evidence-manifest.json"
        if output.parent == args.dir and manifest.exists():
            from .evidence import write_evidence_manifest

            write_evidence_manifest(manifest, args.dir)
        print(f"Wrote operator gate summary: {output}")
        return 0
    if args.command == "validate-operator-gate-summary":
        result = validate_operator_gate_summary(args.summary)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "generate-validation-template":
        write_validation_template(args.plan, args.out)
        print(f"Generated validation results template into {args.out}")
        return 0
    if args.command == "generate-operator-review":
        write_operator_review_template(args.dir, args.out)
        print(f"Generated operator review template into {args.out}")
        return 0
    if args.command == "validate-operator-review":
        result = validate_operator_review(args.review, allow_draft=args.allow_draft)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-partner-handoff":
        result = validate_partner_handoff_matrix(args.matrix, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-validation-results":
        result = validate_validation_results(args.results, allow_open=args.allow_open)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-validation-checklist":
        result = validate_validation_checklist(args.checklist)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-workload-validation-checklist":
        result = validate_workload_validation_checklist(args.checklist, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-migration-execution-queue":
        result = validate_migration_execution_queue(args.queue, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-prism-categories":
        result = validate_prism_category_mapping(args.mapping, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-stakeholder-comms":
        result = validate_stakeholder_comms(args.plan, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-what-will-break":
        result = validate_what_will_break(args.report, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-what-will-break-brief":
        result = validate_what_will_break_brief(args.brief, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-connectivity-checklist":
        result = validate_connectivity_checklist(args.checklist, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-identity-cutover-plan":
        result = validate_identity_cutover_plan(args.plan, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-compatibility-research":
        result = validate_compatibility_research(args.research, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-rollback-plan":
        result = validate_rollback_plan(args.plan, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-remediation":
        result = validate_remediation_tracker(args.tracker, allow_open=args.allow_open)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-remediation-tracker":
        result = validate_remediation_tracker_contract(args.tracker, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-signoffs":
        result = validate_signoffs(args.signoffs, allow_pending=args.allow_pending)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-signoff-matrix":
        result = validate_signoff_matrix_contract(args.matrix, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-approval-exceptions":
        result = validate_approval_exceptions(args.exceptions, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-approval-exception-approvals":
        result = validate_approval_exception_approvals(
            args.exceptions,
            allow_required=args.allow_required,
            assessment_path=args.assessment,
        )
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-executive-brief":
        result = validate_executive_brief(args.brief, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-change-board-evidence":
        result = validate_change_board_evidence(args.evidence, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-operator-report":
        result = validate_operator_report(args.report, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-operator-portal":
        result = validate_operator_portal(args.portal, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-operations-console":
        result = validate_operations_console(args.console, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-operator-dashboard":
        result = validate_operator_dashboard(args.dashboard, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-wave-summary":
        result = validate_wave_readiness_summary(args.summary, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-wave-execution-calendar":
        result = validate_wave_execution_calendar(args.calendar, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-migration-waves":
        result = validate_migration_waves(args.waves, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-migration-runbook":
        result = validate_migration_runbook(args.runbook, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-dependency-sequence":
        result = validate_dependency_sequence(args.sequence, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-dependency-review":
        result = validate_dependency_review(args.review, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-tools-driver-readiness":
        result = validate_tools_driver_readiness(args.readiness, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-storage-posture":
        result = validate_storage_posture(args.posture, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-recovery-readiness":
        result = validate_recovery_readiness(args.readiness, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-move-staging-readiness":
        result = validate_move_staging_readiness(args.readiness, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-move-staging-brief":
        result = validate_move_staging_brief(args.brief, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-business-impact":
        result = validate_business_impact_summary(args.summary, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-target-comparison":
        result = validate_target_readiness_comparison(args.comparison, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-risk-register":
        result = validate_risk_register(args.register, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-owner-risk-summary":
        result = validate_owner_risk_summary(args.summary, args.assessment)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "generate-move-payload":
        payload = build_move_payload(args.plan, args.config)
        write_json(args.out, payload)
        print(
            f"Generated dry-run Move payload with {len(payload['workloads'])} workloads into {args.out}"
        )
        return 0
    if args.command == "validate-move-submit-readiness":
        result = validate_move_submit_readiness(args.payload, args.review, lab_ack_env=args.lab_ack_env)
        if args.out:
            write_json(args.out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            for check in result.checks:
                print(f"[{check['status']}] {check['name']}: {check['detail']}")
            for warning in result.warnings:
                print(f"WARNING: {warning}")
            for error in result.errors:
                print(f"ERROR: {error}")
            if args.out:
                print(f"Wrote Move submit readiness proof: {args.out}")
        return 0 if result.ok else 1
    if args.command == "validate-move-lab-proof":
        result = validate_move_lab_proof(
            args.proof,
            args.payload,
            args.review,
            transcript_validation_path=args.transcript_validation,
            lab_ack_env=args.lab_ack_env,
        )
        if args.out:
            write_json(args.out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            for check in result.checks:
                print(f"[{check['status']}] {check['name']}: {check['detail']}")
            for warning in result.warnings:
                print(f"WARNING: {warning}")
            for error in result.errors:
                print(f"ERROR: {error}")
            if args.out:
                print(f"Wrote Move lab proof validation: {args.out}")
        return 0 if result.ok else 1
    if args.command == "validate-move-lab-transcript":
        result = validate_move_lab_transcript(args.transcript, args.payload, args.review, lab_ack_env=args.lab_ack_env)
        if args.out:
            write_json(args.out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            for check in result.checks:
                print(f"[{check['status']}] {check['name']}: {check['detail']}")
            for warning in result.warnings:
                print(f"WARNING: {warning}")
            for error in result.errors:
                print(f"ERROR: {error}")
            if args.out:
                print(f"Wrote Move lab transcript validation: {args.out}")
        return 0 if result.ok else 1
    if args.command == "generate-move-lab-capture-kit":
        try:
            output = write_move_lab_capture_kit(
                args.payload,
                args.review,
                args.out_dir,
                lab_ack_env=args.lab_ack_env,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 1
        if args.json:
            print(json.dumps(output.to_dict(), indent=2))
        else:
            print(f"Generated Move lab capture kit into {output.out_dir}")
            print(f"Transcript template: {output.transcript_template_path}")
            print(f"Capture checklist: {output.checklist_path}")
        return 0
    if args.command == "validate-move-lab-capture-kit":
        result = validate_move_lab_capture_kit(args.kit_dir, args.payload)
        if args.out:
            write_json(args.out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            for check in result.checks:
                print(f"[{check['status']}] {check['name']}: {check['detail']}")
            for warning in result.warnings:
                print(f"WARNING: {warning}")
            for error in result.errors:
                print(f"ERROR: {error}")
            if args.out:
                print(f"Wrote Move lab capture kit validation: {args.out}")
        return 0 if result.ok else 1
    if args.command == "validate-move-lab-evidence-intake":
        result = validate_move_lab_evidence_intake(
            args.payload,
            args.review,
            args.transcript,
            args.transcript_validation,
            args.proof,
            args.proof_validation,
            capture_kit_validation_path=args.capture_kit_validation,
            lab_ack_env=args.lab_ack_env,
        )
        if args.out:
            write_json(args.out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            for check in result.checks:
                print(f"[{check['status']}] {check['name']}: {check['detail']}")
            for warning in result.warnings:
                print(f"WARNING: {warning}")
            for error in result.errors:
                print(f"ERROR: {error}")
            if args.out:
                print(f"Wrote Move lab evidence intake: {args.out}")
        return 0 if result.ok else 1
    if args.command == "move-lab-evidence-preflight":
        result = validate_move_lab_evidence_preflight(
            args.payload,
            args.review,
            args.capture_kit_validation,
            args.transcript,
            args.transcript_validation,
            args.proof,
            args.proof_validation,
            args.evidence_intake,
            lab_ack_env=args.lab_ack_env,
        )
        if args.out:
            write_json(args.out, result.to_dict())
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(result.to_markdown(), encoding="utf-8")
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            for check in result.checks:
                print(f"[{check['status']}] {check['name']}: {check['detail']}")
            for artifact in result.required_artifacts:
                print(f"[artifact] {artifact['role']}: {artifact['state']} {artifact['path']}")
            for warning in result.warnings:
                print(f"WARNING: {warning}")
            for error in result.errors:
                print(f"ERROR: {error}")
            if args.out:
                print(f"Wrote Move lab evidence preflight: {args.out}")
            if args.report:
                print(f"Wrote Move lab evidence preflight report: {args.report}")
        return 0 if result.ok else 1
    if args.command == "validate-move-lab-evidence-request":
        result = validate_move_lab_evidence_request(args.request)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "move-lab-readiness-packet":
        result = write_move_lab_readiness_packet(
            payload_path=args.payload,
            review_path=args.review,
            move_submit_readiness_path=args.move_submit_readiness,
            capture_kit_dir=args.capture_kit,
            capture_kit_validation_path=args.capture_kit_validation,
            evidence_preflight_path=args.evidence_preflight,
            evidence_preflight_report_path=args.evidence_preflight_report,
            runbook_path=args.runbook,
            evidence_request_path=args.evidence_request,
            closure_checklist_path=args.closure_checklist,
            out_path=args.out,
            report_path=args.report,
            lab_ack_env=args.lab_ack_env,
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            for check in result.checks:
                print(f"[{check['status']}] {check['name']}: {check['detail']}")
            for warning in result.warnings:
                print(f"WARNING: {warning}")
            for error in result.errors:
                print(f"ERROR: {error}")
            print(f"Wrote Move lab readiness packet: {args.out}")
            if args.report:
                print(f"Wrote Move lab readiness packet report: {args.report}")
        return 0 if result.ok else 1
    if args.command == "validate-move-lab-readiness-packet":
        result = validate_move_lab_readiness_packet(args.packet, report_path=args.report)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            for check in result.checks:
                print(f"[{check['status']}] {check['name']}: {check['detail']}")
            for warning in result.warnings:
                print(f"WARNING: {warning}")
            for error in result.errors:
                print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-source-endpoint-evidence-request":
        result = validate_source_endpoint_evidence_request(args.request)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "generate-move-lab-proof-template":
        output = write_move_lab_proof_template(
            args.payload,
            args.review,
            args.out,
            proof_scope=args.proof_scope,
        )
        print(f"Generated Move lab proof template into {output}")
        return 0
    if args.command == "generate-approved-move-lab-proof":
        try:
            output = write_approved_move_lab_proof(
                args.payload,
                args.review,
                args.transcript,
                args.transcript_validation,
                args.out,
                approved_by=args.approved_by,
                notes=args.notes,
                lab_ack_env=args.lab_ack_env,
            )
        except ValueError as exc:
            print(f"ERROR: {exc}")
            return 1
        print(f"Generated approved Move lab proof into {output}")
        return 0
    if args.command == "generate-move-lab-runbook":
        output = write_move_lab_runbook(
            args.payload,
            args.review,
            args.out,
            proof_template_path=args.proof_template,
        )
        manifest = args.out.parent / "evidence-manifest.json"
        if manifest.exists():
            from .evidence import write_evidence_manifest

            write_evidence_manifest(manifest, args.out.parent)
        print(f"Generated Move lab execution runbook into {output}")
        return 0
    if args.command == "validate-move-lab-runbook":
        result = validate_move_lab_runbook(args.runbook)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "doctor":
        result = run_doctor(Path.cwd())
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(f"NMRCP doctor: {result['status'].upper()}")
            for check in result["checks"]:
                print(f"[{check['status']}] {check['name']}: {check['detail']}")
        return 0 if result["status"] == "pass" else 1
    if args.command == "serve":
        if args.generate_only:
            manifest = prepare_console_site(args.site_dir, inventory_path=args.inventory)
            print(json.dumps(manifest, indent=2))
            return 0
        serve_console(args.site_dir, host=args.host, port=args.port, inventory_path=args.inventory)
        return 0
    if args.command == "mvp-audit":
        result = audit_mvp(
            args.repo_root,
            assessment_dir=args.assessment_dir,
            assessment_intake_path=args.assessment_intake,
            live_proof_path=args.live_proof,
            move_proof_path=args.move_proof,
            evidence_bundle_path=args.evidence_bundle,
            validation_results_path=args.validation_results,
            remediation_tracker_path=args.remediation_tracker,
            signoffs_path=args.signoffs,
            approval_exceptions_path=args.approval_exceptions,
            operator_review_path=args.operator_review,
            move_lab_capture_validation_path=args.move_lab_capture_validation,
            move_lab_evidence_intake_path=args.move_lab_evidence_intake,
            warning_acceptance_path=args.warning_acceptance,
        )
        if args.out:
            write_json(args.out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"NMRCP MVP audit: {result.status.upper()}")
            for requirement in result.requirements:
                print(f"[{requirement.status}] {requirement.id}: {requirement.requirement}")
                for warning in requirement.warnings:
                    print(f"WARNING: {requirement.id}: {warning}")
                for error in requirement.errors:
                    print(f"ERROR: {requirement.id}: {error}")
            if args.out:
                print(f"Wrote MVP audit: {args.out}")
        return 0 if result.ok else 1
    if args.command == "github-readiness":
        result = check_github_readiness(args.repo_root, expected_remote=args.expected_remote)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(result.to_markdown(), encoding="utf-8")
        if args.json_out:
            write_json(args.json_out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            if args.out:
                print(f"Wrote GitHub publication review: {args.out}")
            if args.json_out:
                print(f"Wrote GitHub publication review JSON: {args.json_out}")
            for check in result.checks:
                print(f"[{check.status}] {check.name}: {check.detail}")
            for action in result.next_actions:
                print(f"NEXT: {action}")
        return 0 if result.ok else 1
    if args.command == "validate-github-publication-review":
        result = validate_github_publication_review(
            args.repo_root,
            args.json_report,
            markdown_report_path=args.report,
            expected_remote=args.expected_remote,
        )
        print(result.summary())
        for error in result.errors:
            print(f"ERROR: {error}")
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        return 0 if result.ok else 1
    if args.command == "vault-readiness":
        result = check_vault_readiness(args.repo_root, vault_path=args.vault)
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            for check in result.checks:
                print(f"[{check.status}] {check.name}: {check.detail}")
        return 0 if result.ok else 1
    if args.command == "product-readiness":
        result = check_product_readiness(
            args.repo_root,
            vault_path=args.vault,
            expected_remote=args.expected_remote,
            assessment_dir=args.assessment_dir,
            assessment_intake_path=args.assessment_intake,
            live_proof_path=args.live_proof,
            move_proof_path=args.move_proof,
            evidence_bundle_path=args.evidence_bundle,
            validation_results_path=args.validation_results,
            remediation_tracker_path=args.remediation_tracker,
            signoffs_path=args.signoffs,
            approval_exceptions_path=args.approval_exceptions,
            operator_review_path=args.operator_review,
            move_lab_capture_validation_path=args.move_lab_capture_validation,
            move_lab_evidence_intake_path=args.move_lab_evidence_intake,
            warning_acceptance_path=args.warning_acceptance,
            mvp_proof_package_path=args.mvp_proof_package,
            github_publication_review_path=args.github_publication_review,
            github_publication_review_json_path=args.github_publication_review_json,
            publication_staging_manifest_path=args.publication_staging_manifest,
            publication_staging_manifest_json_path=args.publication_staging_manifest_json,
            publication_staging_ignored_paths=tuple(path for path in (args.out, args.json_out) if path),
        )
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(result.to_markdown(), encoding="utf-8")
        if args.json_out:
            write_json(args.json_out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            if args.out:
                print(f"Wrote product readiness report: {args.out}")
            if args.json_out:
                print(f"Wrote product readiness report JSON: {args.json_out}")
            for gate in result.gates:
                print(f"[{gate.status}] {gate.name}: {gate.summary}")
                for blocker in gate.blockers:
                    print(f"BLOCKER: {gate.name}: {blocker}")
            for action in result.next_actions:
                print(f"NEXT: {action}")
        return 0 if result.ok else 1
    if args.command == "validate-product-readiness-report":
        result = validate_product_readiness_report(
            args.repo_root,
            args.json_report,
            markdown_report_path=args.report,
            vault_path=args.vault,
            expected_remote=args.expected_remote,
            assessment_dir=args.assessment_dir,
            assessment_intake_path=args.assessment_intake,
            live_proof_path=args.live_proof,
            move_proof_path=args.move_proof,
            evidence_bundle_path=args.evidence_bundle,
            validation_results_path=args.validation_results,
            remediation_tracker_path=args.remediation_tracker,
            signoffs_path=args.signoffs,
            approval_exceptions_path=args.approval_exceptions,
            operator_review_path=args.operator_review,
            move_lab_capture_validation_path=args.move_lab_capture_validation,
            move_lab_evidence_intake_path=args.move_lab_evidence_intake,
            warning_acceptance_path=args.warning_acceptance,
            mvp_proof_package_path=args.mvp_proof_package,
            github_publication_review_path=args.github_publication_review,
            github_publication_review_json_path=args.github_publication_review_json,
            publication_staging_manifest_path=args.publication_staging_manifest,
            publication_staging_manifest_json_path=args.publication_staging_manifest_json,
        )
        print(result.summary())
        for error in result.errors:
            print(f"ERROR: {error}")
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        return 0 if result.ok else 1
    if args.command == "publication-handoff":
        result = build_publication_handoff(
            args.repo_root,
            github_report_path=args.github_publication_review,
            github_json_path=args.github_publication_review_json,
            product_report_path=args.product_readiness_report,
            product_json_path=args.product_readiness_report_json,
            smoke_log_path=args.smoke_log,
            security_scan_status=args.security_scan_status,
            vault_path=args.vault,
            expected_remote=args.expected_remote,
        )
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(result.to_markdown(), encoding="utf-8")
        if args.json_out:
            write_json(args.json_out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            if args.out:
                print(f"Wrote publication handoff: {args.out}")
            if args.json_out:
                print(f"Wrote publication handoff JSON: {args.json_out}")
            for check in result.checks:
                print(f"[{check.status}] {check.name}: {check.detail}")
            for action in result.next_actions:
                print(f"NEXT: {action}")
        return 0 if result.ok else 1
    if args.command == "validate-publication-handoff":
        result = validate_publication_handoff(
            args.repo_root,
            args.json_report,
            markdown_report_path=args.report,
            github_report_path=args.github_publication_review,
            github_json_path=args.github_publication_review_json,
            product_report_path=args.product_readiness_report,
            product_json_path=args.product_readiness_report_json,
            smoke_log_path=args.smoke_log,
            security_scan_status=args.security_scan_status,
            vault_path=args.vault,
            expected_remote=args.expected_remote,
        )
        print(result.summary())
        for error in result.errors:
            print(f"ERROR: {error}")
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        return 0 if result.ok else 1
    if args.command == "publication-staging-manifest":
        ignored_paths = tuple(path for path in (args.out, args.json_out) if path)
        result = build_publication_staging_manifest(args.repo_root, ignored_forbidden_paths=ignored_paths)
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(result.to_markdown(), encoding="utf-8")
        if args.json_out:
            write_json(args.json_out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            if args.out:
                print(f"Wrote publication staging manifest: {args.out}")
            if args.json_out:
                print(f"Wrote publication staging manifest JSON: {args.json_out}")
            print(f"STAGE: {result.staging_command}")
            for entry in result.entries:
                print(f"[{entry.status}] {entry.path}: tracked={entry.tracked}; sha256={entry.sha256 or 'none'}")
            for path in result.forbidden_candidates:
                print(f"FORBIDDEN-CANDIDATE: {console_safe(path)}")
            for action in result.next_actions:
                print(f"NEXT: {action}")
        return 0 if result.ok else 1
    if args.command == "validate-publication-staging-manifest":
        result = validate_publication_staging_manifest(
            args.repo_root,
            args.json_report,
            markdown_report_path=args.report,
        )
        print(result.summary())
        for error in result.errors:
            print(f"ERROR: {error}")
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        return 0 if result.ok else 1
    if args.command == "pull-request-readiness":
        ignored_paths = tuple(path for path in (args.out, args.json_out) if path)
        result = build_pull_request_readiness(
            args.repo_root,
            github_report_path=args.github_publication_review,
            github_json_path=args.github_publication_review_json,
            product_report_path=args.product_readiness_report,
            product_json_path=args.product_readiness_report_json,
            publication_handoff_path=args.publication_handoff,
            publication_handoff_json_path=args.publication_handoff_json,
            staging_manifest_path=args.publication_staging_manifest,
            staging_manifest_json_path=args.publication_staging_manifest_json,
            smoke_log_path=args.smoke_log,
            security_scan_status=args.security_scan_status,
            vault_path=args.vault,
            expected_remote=args.expected_remote,
            ignored_staging_forbidden_paths=ignored_paths,
        )
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(result.to_markdown(), encoding="utf-8")
        if args.json_out:
            write_json(args.json_out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            if args.out:
                print(f"Wrote pull request readiness packet: {args.out}")
            if args.json_out:
                print(f"Wrote pull request readiness packet JSON: {args.json_out}")
            for check in result.checks:
                print(f"[{check.status}] {check.name}: {check.detail}")
            for action in result.next_actions:
                print(f"NEXT: {action}")
        return 0 if result.ok else 1
    if args.command == "validate-pull-request-readiness":
        result = validate_pull_request_readiness(
            args.repo_root,
            args.json_report,
            markdown_report_path=args.report,
            github_report_path=args.github_publication_review,
            github_json_path=args.github_publication_review_json,
            product_report_path=args.product_readiness_report,
            product_json_path=args.product_readiness_report_json,
            publication_handoff_path=args.publication_handoff,
            publication_handoff_json_path=args.publication_handoff_json,
            staging_manifest_path=args.publication_staging_manifest,
            staging_manifest_json_path=args.publication_staging_manifest_json,
            smoke_log_path=args.smoke_log,
            security_scan_status=args.security_scan_status,
            vault_path=args.vault,
            expected_remote=args.expected_remote,
        )
        print(result.summary())
        for error in result.errors:
            print(f"ERROR: {error}")
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        return 0 if result.ok else 1
    if args.command == "external-proof-plan":
        result = build_external_proof_plan(
            args.repo_root,
            assessment_intake_path=args.assessment_intake,
            live_proof_path=args.live_proof,
            move_proof_path=args.move_proof,
            move_lab_evidence_intake_path=args.move_lab_evidence_intake,
        )
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(result.to_markdown(), encoding="utf-8")
        if args.json_out:
            write_json(args.json_out, result.to_dict())
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(result.summary())
            if args.out:
                print(f"Wrote external proof plan: {args.out}")
            if args.json_out:
                print(f"Wrote external proof plan JSON: {args.json_out}")
            for step in result.steps:
                print(f"[{step.status}] {step.name}: {step.current_gap}")
            for boundary in result.operator_boundaries:
                print(f"BOUNDARY: {boundary}")
        return 0
    if args.command == "validate-external-proof-plan":
        result = validate_external_proof_plan(
            args.repo_root,
            args.json_report,
            markdown_report_path=args.report,
            assessment_intake_path=args.assessment_intake,
            live_proof_path=args.live_proof,
            move_proof_path=args.move_proof,
            move_lab_evidence_intake_path=args.move_lab_evidence_intake,
        )
        print(result.summary())
        for error in result.errors:
            print(f"ERROR: {error}")
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        return 0 if result.ok else 1
    if args.command == "package-evidence":
        package_evidence(args.dir, args.out)
        result = verify_evidence_bundle(args.out)
        print(f"Packaged evidence bundle: {args.out}")
        print(result.summary())
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "verify-evidence":
        if bool(args.dir) == bool(args.bundle):
            print("ERROR: pass exactly one of --dir or --bundle")
            return 1
        result = verify_evidence(args.dir) if args.dir else verify_evidence_bundle(args.bundle)
        print(result.summary())
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "review-evidence":
        result = review_evidence_dir(args.dir)
        print(result.summary())
        for finding in result.findings:
            print(f"ERROR: {finding}")
        return 0 if result.ok else 1
    if args.command == "package-handoff":
        package_handoff(
            args.dir,
            args.out,
            bundle_path=args.bundle,
            validation_results_path=args.validation_results,
            remediation_tracker_path=args.remediation_tracker,
            signoffs_path=args.signoffs,
            approval_exceptions_path=args.approval_exceptions,
            operator_review_path=args.operator_review,
            move_lab_proof_path=args.move_lab_proof,
            move_lab_readiness_packet_path=args.move_lab_readiness_packet,
            move_lab_evidence_intake_path=args.move_lab_evidence_intake,
            move_lab_capture_kit_dir=args.move_lab_capture_kit,
            move_lab_capture_validation_path=args.move_lab_capture_validation,
            source_collection_plan_path=args.source_collection_plan,
            move_payload_path=args.move_payload,
        )
        result = verify_handoff_package(args.out)
        print(f"Packaged handoff bundle: {args.out}")
        print(result.summary())
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "verify-handoff":
        result = verify_handoff_package(args.package)
        print(result.summary())
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "package-mvp-proof":
        package_mvp_proof(
            args.out,
            mvp_audit_path=args.mvp_audit,
            live_proof_path=args.live_proof,
            move_submit_readiness_path=args.move_submit_readiness,
            move_lab_transcript_path=args.move_lab_transcript,
            move_lab_proof_path=args.move_lab_proof,
            move_lab_runbook_path=args.move_lab_runbook,
            move_lab_closure_checklist_path=args.move_lab_closure_checklist,
            move_lab_capture_kit_dir=args.move_lab_capture_kit,
            move_lab_capture_validation_path=args.move_lab_capture_validation,
            move_lab_readiness_packet_path=args.move_lab_readiness_packet,
            move_lab_evidence_intake_path=args.move_lab_evidence_intake,
            source_collection_plan_path=args.source_collection_plan,
            source_endpoint_evidence_request_path=args.source_endpoint_evidence_request,
            move_lab_evidence_request_path=args.move_lab_evidence_request,
            external_proof_plan_path=args.external_proof_plan,
            operator_gate_summary_path=args.operator_gate_summary,
            handoff_package_path=args.handoff_package,
        )
        result = verify_mvp_proof_package(args.out)
        print(f"Packaged MVP proof bundle: {args.out}")
        print(result.summary())
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "verify-mvp-proof":
        result = verify_mvp_proof_package(args.package)
        print(result.summary())
        for role in result.roles:
            print(f"[role] {role}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "summarize-mvp-proof":
        summary = write_mvp_proof_summary(args.package, args.out) if args.out else summarize_mvp_proof_package(args.package)
        if args.json:
            print(json.dumps(summary.to_dict(), indent=2))
        else:
            if args.out:
                print(f"Wrote MVP proof package summary: {args.out}")
            print(summary.verification.summary())
            print(f"MVP status: {summary.mvp_status}")
            print(f"Move lab scope: {summary.move_lab_scope}")
            print(f"Nested handoff roles: {len(summary.handoff_roles)}")
            print(f"Handoff readiness packet: {summary.to_dict()['proof_status'].get('handoff_move_lab_readiness_packet', 'unknown')}")
            if summary.move_lab_scope != "approved_lab_move_appliance" or summary.move_lab_status != "pass":
                print("WARNING: Real approved Nutanix Move appliance proof remains unproven")
        return 0 if summary.verification.ok else 1
    if args.command == "validate-mvp-proof-summary":
        result = validate_mvp_proof_summary(args.package, args.summary)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "mvp-closure-report":
        report = (
            write_mvp_closure_report(args.package, args.out, json_out_path=args.json_out)
            if args.out
            else build_mvp_closure_report(args.package)
        )
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            if args.out:
                print(f"Wrote MVP closure report: {args.out}")
            if args.json_out:
                print(f"Wrote MVP closure report JSON: {args.json_out}")
            print(f"MVP closure report: {report.overall_status.upper()}")
            print(f"Ready for external handoff: {'yes' if report.ready_for_external_handoff else 'no'}")
            print(f"Nested handoff roles: {len(report.handoff_roles)}")
            print(f"Handoff readiness packet: {handoff_role_count_status(report.handoff_role_counts, 'move_lab_readiness_packet')}")
            print(f"Open items: {len(report.open_items)}")
            print(f"Blocking open items: {report.closure_summary.get('blocking_open_items', 0)}")
            print(f"Required evidence IDs: {report.closure_summary.get('required_evidence_id_count', 0)}")
            print(f"Required evidence ID list: {evidence_id_list(report.closure_summary)}")
            for item in report.open_items:
                print(f"[{item.status}] {item.area}: {item.action}")
        return 0 if report.overall_status != "fail" else 1
    if args.command == "validate-mvp-closure-report":
        result = validate_mvp_closure_report(args.package, args.json_report, markdown_report_path=args.report)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "launch-readiness-report":
        report = (
            write_launch_readiness_report(
                args.package,
                args.out,
                json_out_path=args.json_out,
                repo_url=args.repo_url,
                audience=args.audience,
            )
            if args.out
            else build_launch_readiness_report(args.package, repo_url=args.repo_url, audience=args.audience)
        )
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            if args.out:
                print(f"Wrote launch readiness report: {args.out}")
            if args.json_out:
                print(f"Wrote launch readiness JSON: {args.json_out}")
            print(f"Launch readiness: {report.readiness}")
            print(f"Package verification: {report.package_verification_status}")
            print(f"Ready for external handoff: {'yes' if report.ready_for_external_handoff else 'no'}")
            print(f"External handoff decision: {report.external_handoff_decision}")
            print(f"Nested handoff roles: {len(report.handoff_roles)}")
            print(f"Handoff readiness packet: {handoff_role_count_status(report.handoff_role_counts, 'move_lab_readiness_packet')}")
            print(f"Blocking open items: {report.closure_summary.get('blocking_open_items', 0)}")
            print(f"Required evidence IDs: {report.closure_summary.get('required_evidence_id_count', 0)}")
            print(f"Required evidence ID list: {evidence_id_list(report.closure_summary)}")
            for item in report.open_items:
                if item.get("blocking"):
                    print(f"[blocking] {item.get('area')}: {item.get('action')}")
        return 0 if report.ok else 1
    if args.command == "validate-launch-readiness-report":
        result = validate_launch_readiness_report(args.package, args.json_report, markdown_report_path=args.report)
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "validate-warning-acceptance":
        try:
            payload = json.loads(args.warnings.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: could not read warnings JSON: {exc}")
            return 1
        raw_warnings = payload.get("warnings") if isinstance(payload, dict) else payload
        if not isinstance(raw_warnings, list):
            print("ERROR: warnings JSON must be a list or an object with a warnings list")
            return 1
        result = validate_warning_acceptance(args.acceptance, tuple(str(warning) for warning in raw_warnings))
        print(result.summary())
        for warning in result.warnings:
            print(f"WARNING: {warning}")
        for error in result.errors:
            print(f"ERROR: {error}")
        return 0 if result.ok else 1
    if args.command == "change-gate":
        result = run_change_gate(
            args.dir,
            bundle_path=args.bundle,
            validation_results_path=args.validation_results,
            remediation_tracker_path=args.remediation_tracker,
            signoffs_path=args.signoffs,
            approval_exceptions_path=args.approval_exceptions,
            operator_review_path=args.operator_review,
            move_lab_capture_validation_path=args.move_lab_capture_validation,
            move_lab_proof_path=args.move_lab_proof,
            move_lab_evidence_intake_path=args.move_lab_evidence_intake,
            allow_pending_signoffs=args.allow_pending_signoffs,
            allow_draft_operator_review=args.allow_draft_operator_review,
        )
        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"NMRCP change gate: {result.status.upper()}")
            for check in result.checks:
                print(f"[{check['status']}] {check['name']}: {check['detail']}")
            for warning in result.warnings:
                print(f"WARNING: {warning}")
            for error in result.errors:
                print(f"ERROR: {error}")
        return 0 if result.ok else 1

    parser.error("Unknown command")
    return 2


def endpoint_config(endpoint: str | None, username: str | None, password_env: str, verify_tls: bool) -> EndpointConfig:
    if not endpoint:
        raise SystemExit("Missing endpoint. Pass --endpoint or set the matching NMRCP_*_URL variable.")
    if not username:
        raise SystemExit("Missing username. Pass --username or set the matching NMRCP_*_USERNAME variable.")
    password = os.getenv(password_env)
    if password is None:
        password = getpass.getpass(f"Password for {username} at {endpoint}: ")
    try:
        return EndpointConfig(endpoint, username, password, verify_tls=verify_tls)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def optional_endpoint_config(endpoint: str | None, username: str | None, password_env: str, verify_tls: bool) -> EndpointConfig | None:
    password = os.getenv(password_env)
    if not endpoint or not username or not password:
        return None
    try:
        return EndpointConfig(endpoint, username, password, verify_tls=verify_tls)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


def write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def console_safe(value: object) -> str:
    return str(value).encode("ascii", errors="backslashreplace").decode("ascii")


def handoff_role_count_status(role_counts: dict[str, int], role: str) -> str:
    count = int(role_counts.get(role, 0))
    return f"present ({count})" if count else "missing"


def evidence_id_list(closure_summary: dict[str, object]) -> str:
    ids = closure_summary.get("required_evidence_ids")
    if not isinstance(ids, list) or not ids:
        return "none"
    return ", ".join(str(item) for item in ids)


if __name__ == "__main__":
    raise SystemExit(main())
