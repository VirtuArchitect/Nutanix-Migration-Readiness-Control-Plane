from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .evidence import sha256_file
from .external_proof_plan import EXTERNAL_PROOF_PLAN_SCHEMA_VERSION
from .gate_summary import validate_operator_gate_summary
from .move_lab_closure_checklist import validate_move_lab_closure_checklist
from .move_lab_evidence_request import validate_move_lab_evidence_request
from .move_lab_readiness_packet import validate_move_lab_readiness_packet
from .move_lab_runbook import validate_move_lab_runbook
from .source_collection_plan import validate_source_collection_plan_text
from .source_endpoint_evidence_request import validate_source_endpoint_evidence_request


MVP_PROOF_MANIFEST_SCHEMA = "nmrcp_mvp_proof_manifest_v1"
ROLE_ARCHIVE_PATHS = {
    "mvp_audit": "proof/mvp-audit.json",
    "live_endpoint_proof": "proof/live-proof-validation.json",
    "move_submit_readiness": "proof/move-submit-readiness.json",
    "move_lab_transcript": "proof/move-lab-transcript-validation.json",
    "move_lab_proof": "proof/move-lab-proof-validation.json",
    "move_lab_runbook": "proof/move-lab-execution-runbook.md",
    "move_lab_closure_checklist": "proof/move-lab-closure-checklist.md",
    "move_lab_capture_template": "proof/move-lab-transcript.template.json",
    "move_lab_capture_checklist": "proof/move-lab-capture-checklist.md",
    "move_lab_capture_validation": "proof/move-lab-capture-kit-validation.json",
    "move_lab_readiness_packet": "proof/move-lab-readiness-packet.json",
    "move_lab_evidence_intake": "proof/move-lab-evidence-intake.json",
    "source_collection_plan": "proof/source-collection-plan.md",
    "source_endpoint_evidence_request": "proof/source-endpoint-evidence-request.md",
    "move_lab_evidence_request": "proof/move-lab-evidence-request.md",
    "external_proof_plan": "proof/external-proof-plan.json",
    "operator_gate_summary": "proof/operator-gate-summary.md",
    "handoff_package": "handoff/handoff-package.zip",
}
REQUIRED_ROLES = {"mvp_audit"}


@dataclass(frozen=True)
class MvpProofVerification:
    checked: int
    roles: tuple[str, ...]
    errors: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"{status}: checked={self.checked}, roles={len(self.roles)}, errors={len(self.errors)}"


@dataclass(frozen=True)
class MvpProofSummary:
    package_path: Path
    verification: MvpProofVerification
    generated_at: str
    roles: tuple[str, ...]
    mvp_status: str
    mvp_counts: dict[str, int]
    requirements: tuple[dict[str, Any], ...]
    live_proof_status: str
    move_submit_status: str
    move_lab_transcript_status: str
    move_lab_status: str
    move_lab_scope: str
    has_runbook: bool
    has_closure_checklist: bool
    has_capture_kit: bool
    move_lab_capture_validation_status: str
    move_lab_readiness_packet_status: str
    move_lab_evidence_intake_status: str
    has_source_collection_plan: bool
    has_source_endpoint_evidence_request: bool
    has_move_lab_evidence_request: bool
    external_proof_plan_status: str
    has_operator_summary: bool
    has_handoff: bool
    handoff_verification_status: str
    handoff_roles: tuple[str, ...]
    handoff_role_counts: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "nmrcp_mvp_proof_summary_v1",
            "package": str(self.package_path),
            "generated_at": self.generated_at,
            "verification": {
                "status": "pass" if self.verification.ok else "fail",
                "checked": self.verification.checked,
                "roles": list(self.verification.roles),
                "errors": list(self.verification.errors),
            },
            "mvp_status": self.mvp_status,
            "mvp_counts": self.mvp_counts,
            "requirements": list(self.requirements),
            "proof_status": {
                "live_endpoint_proof": self.live_proof_status,
                "move_submit_readiness": self.move_submit_status,
                "move_lab_transcript": self.move_lab_transcript_status,
                "move_lab_proof": self.move_lab_status,
                "move_lab_scope": self.move_lab_scope,
                "move_lab_runbook": "present" if self.has_runbook else "missing",
                "move_lab_closure_checklist": "present" if self.has_closure_checklist else "missing",
                "move_lab_capture_kit": "present" if self.has_capture_kit else "missing",
                "move_lab_capture_validation": self.move_lab_capture_validation_status,
                "move_lab_readiness_packet": self.move_lab_readiness_packet_status,
                "move_lab_evidence_intake": self.move_lab_evidence_intake_status,
                "source_collection_plan": "present" if self.has_source_collection_plan else "missing",
                "source_endpoint_evidence_request": "present" if self.has_source_endpoint_evidence_request else "missing",
                "move_lab_evidence_request": "present" if self.has_move_lab_evidence_request else "missing",
                "external_proof_plan": self.external_proof_plan_status,
                "operator_gate_summary": "present" if self.has_operator_summary else "missing",
                "handoff_package": self.handoff_verification_status,
                "handoff_move_lab_readiness_packet": handoff_role_status(self.handoff_roles, "move_lab_readiness_packet"),
            },
            "handoff_roles": list(self.handoff_roles),
            "handoff_role_counts": dict(self.handoff_role_counts),
        }

    def to_markdown(self) -> str:
        lines = [
            "# MVP Proof Package Summary",
            "",
            f"- Package verification: `{'pass' if self.verification.ok else 'fail'}`",
            f"- Files checked: `{self.verification.checked}`",
            f"- Roles present: `{len(self.roles)}`",
            f"- MVP status: `{self.mvp_status}`",
            f"- Requirement counts: `pass={self.mvp_counts.get('pass', 0)}, partial={self.mvp_counts.get('partial', 0)}, fail={self.mvp_counts.get('fail', 0)}`",
            f"- Live endpoint proof: `{self.live_proof_status}`",
            f"- Move submit readiness: `{self.move_submit_status}`",
            f"- Move lab transcript: `{self.move_lab_transcript_status}`",
            f"- Move lab proof: `{self.move_lab_status}`",
            f"- Move lab scope: `{self.move_lab_scope}`",
            f"- Move lab runbook: `{'present' if self.has_runbook else 'missing'}`",
            f"- Move lab closure checklist: `{'present' if self.has_closure_checklist else 'missing'}`",
            f"- Move lab capture kit: `{'present' if self.has_capture_kit else 'missing'}`",
            f"- Move lab capture validation: `{self.move_lab_capture_validation_status}`",
            f"- Move lab readiness packet: `{self.move_lab_readiness_packet_status}`",
            f"- Move lab evidence intake: `{self.move_lab_evidence_intake_status}`",
            f"- Source collection plan: `{'present' if self.has_source_collection_plan else 'missing'}`",
            f"- Source endpoint evidence request: `{'present' if self.has_source_endpoint_evidence_request else 'missing'}`",
            f"- Move lab evidence request: `{'present' if self.has_move_lab_evidence_request else 'missing'}`",
            f"- External proof plan: `{self.external_proof_plan_status}`",
            f"- Operator gate summary: `{'present' if self.has_operator_summary else 'missing'}`",
            f"- Handoff package: `{self.handoff_verification_status}`",
            f"- Handoff roles: `{len(self.handoff_roles)}`",
            "",
            "## Roles",
            "",
            "| Role | Archive Path |",
            "| --- | --- |",
        ]
        for role in self.roles:
            lines.append(f"| `{role}` | `{ROLE_ARCHIVE_PATHS.get(role, 'unknown')}` |")
        lines.extend(["", "## Handoff Package Roles", ""])
        if self.handoff_role_counts:
            lines.extend(["| Role | Count |", "| --- | ---: |"])
            for role, count in sorted(self.handoff_role_counts.items()):
                lines.append(f"| `{role}` | `{count}` |")
        elif self.has_handoff:
            lines.append("- Handoff package roles could not be read.")
        else:
            lines.append("- No handoff package was included.")
        lines.extend(
            [
                "",
                "## MVP Requirements",
                "",
                "| Requirement | Status | Notes |",
                "| --- | --- | --- |",
            ]
        )
        for requirement in self.requirements:
            notes = "; ".join(str(item) for item in requirement.get("warnings", []) or requirement.get("errors", [])) or ""
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{requirement.get('id', 'unknown')}`",
                        f"`{requirement.get('status', 'unknown')}`",
                        notes.replace("|", "\\|"),
                    ]
                )
                + " |"
            )
        lines.extend(
            [
                "",
                "## Residual Risk",
                "",
            ]
        )
        if self.move_lab_scope != "approved_lab_move_appliance" or self.move_lab_status != "pass":
            lines.append("- Real approved Nutanix Move appliance proof remains unproven.")
        if not self.verification.ok:
            lines.append("- Package integrity or role validation failed; do not use this package for review.")
        if self.handoff_verification_status == "invalid":
            lines.append("- Nested handoff package failed semantic handoff verification.")
        if self.mvp_status == "partial":
            lines.append("- MVP status is partial; review requirement notes before external handoff.")
        if not lines[-1].startswith("-"):
            lines.append("- No residual risk was detected by the package summary.")
        lines.append("")
        return "\n".join(lines)


@dataclass(frozen=True)
class MvpProofSummaryValidation:
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"{status}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


@dataclass(frozen=True)
class MvpClosureItem:
    area: str
    status: str
    blocking: bool
    action: str
    required_evidence: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "area": self.area,
            "status": self.status,
            "blocking": self.blocking,
            "action": self.action,
            "required_evidence": self.required_evidence,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class MvpClosureReport:
    package_path: Path
    generated_at: str
    ready_for_external_handoff: bool
    overall_status: str
    closure_summary: dict[str, Any]
    open_items: tuple[MvpClosureItem, ...]
    closeout_commands: tuple[str, ...]
    verified_roles: tuple[str, ...]
    handoff_roles: tuple[str, ...]
    handoff_role_counts: dict[str, int]
    residual_risks: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "nmrcp_mvp_closure_report_v1",
            "package": str(self.package_path),
            "generated_at": self.generated_at,
            "ready_for_external_handoff": self.ready_for_external_handoff,
            "overall_status": self.overall_status,
            "closure_summary": dict(self.closure_summary),
            "open_items": [item.to_dict() for item in self.open_items],
            "closeout_commands": list(self.closeout_commands),
            "verified_roles": list(self.verified_roles),
            "handoff_roles": list(self.handoff_roles),
            "handoff_role_counts": dict(self.handoff_role_counts),
            "residual_risks": list(self.residual_risks),
        }

    def to_markdown(self) -> str:
        lines = [
            "# MVP Closure Report",
            "",
            f"- Overall status: `{self.overall_status}`",
            f"- Ready for external handoff: `{'yes' if self.ready_for_external_handoff else 'no'}`",
            f"- Blocking open items: `{self.closure_summary.get('blocking_open_items', 0)}`",
            f"- Required evidence IDs: `{self.closure_summary.get('required_evidence_id_count', 0)}`",
            f"- Closeout command lines: `{self.closure_summary.get('closeout_command_lines', 0)}`",
            f"- Verified proof roles: `{len(self.verified_roles)}`",
            f"- Nested handoff roles: `{len(self.handoff_roles)}`",
            "",
            "## Required Evidence IDs",
            "",
        ]
        required_evidence_ids = tuple(str(item) for item in self.closure_summary.get("required_evidence_ids", ()))
        if required_evidence_ids:
            for evidence_id in required_evidence_ids:
                lines.append(f"- `{evidence_id}`")
        else:
            lines.append("- No required evidence schema IDs remain open.")
        lines.extend(
            [
                "",
                "## Open Items",
                "",
            ]
        )
        if self.open_items:
            lines.extend(
                [
                    "| Area | Status | Blocking | Required Evidence | Action | Reason |",
                    "| --- | --- | --- | --- | --- | --- |",
                ]
            )
            for item in self.open_items:
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            f"`{item.area}`",
                            f"`{item.status}`",
                            "`yes`" if item.blocking else "`no`",
                            escape_markdown_cell(item.required_evidence),
                            escape_markdown_cell(item.action),
                            escape_markdown_cell(item.reason),
                        ]
                    )
                    + " |"
                )
        else:
            lines.append("- No open MVP closure items were detected.")
        lines.extend(["", "## Closeout Commands", ""])
        if self.closeout_commands:
            lines.extend(["```powershell", *self.closeout_commands, "```"])
        else:
            lines.append("- No closeout commands are required by the closure report.")
        lines.extend(["", "## Verified Roles", ""])
        for role in self.verified_roles:
            lines.append(f"- `{role}`")
        if not self.verified_roles:
            lines.append("- No proof roles verified.")
        lines.extend(["", "## Handoff Package Roles", ""])
        if self.handoff_role_counts:
            lines.extend(["| Role | Count |", "| --- | ---: |"])
            for role, count in sorted(self.handoff_role_counts.items()):
                lines.append(f"| `{role}` | `{count}` |")
        elif self.handoff_roles:
            for role in self.handoff_roles:
                lines.append(f"- `{role}`")
        else:
            lines.append("- No nested handoff roles were available.")
        lines.extend(["", "## Residual Risks", ""])
        for risk in self.residual_risks:
            lines.append(f"- {risk}")
        if not self.residual_risks:
            lines.append("- No residual risks detected by the closure report.")
        lines.append("")
        return "\n".join(lines)


@dataclass(frozen=True)
class MvpClosureReportValidation:
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"{status}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def package_mvp_proof(
    package_path: Path,
    *,
    mvp_audit_path: Path,
    live_proof_path: Path | None = None,
    move_submit_readiness_path: Path | None = None,
    move_lab_transcript_path: Path | None = None,
    move_lab_proof_path: Path | None = None,
    move_lab_runbook_path: Path | None = None,
    move_lab_closure_checklist_path: Path | None = None,
    move_lab_capture_kit_dir: Path | None = None,
    move_lab_capture_validation_path: Path | None = None,
    move_lab_readiness_packet_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
    source_collection_plan_path: Path | None = None,
    source_endpoint_evidence_request_path: Path | None = None,
    move_lab_evidence_request_path: Path | None = None,
    external_proof_plan_path: Path | None = None,
    operator_gate_summary_path: Path | None = None,
    handoff_package_path: Path | None = None,
) -> Path:
    validate_mvp_audit(mvp_audit_path)
    entries = [
        file_entry(mvp_audit_path, "proof/mvp-audit.json", "mvp_audit"),
    ]
    optional_entries = (
        (live_proof_path, "proof/live-proof-validation.json", "live_endpoint_proof"),
        (move_submit_readiness_path, "proof/move-submit-readiness.json", "move_submit_readiness"),
        (move_lab_transcript_path, "proof/move-lab-transcript-validation.json", "move_lab_transcript"),
        (move_lab_proof_path, "proof/move-lab-proof-validation.json", "move_lab_proof"),
        (move_lab_runbook_path, "proof/move-lab-execution-runbook.md", "move_lab_runbook"),
        (move_lab_closure_checklist_path, "proof/move-lab-closure-checklist.md", "move_lab_closure_checklist"),
        (move_lab_capture_validation_path, "proof/move-lab-capture-kit-validation.json", "move_lab_capture_validation"),
        (move_lab_readiness_packet_path, "proof/move-lab-readiness-packet.json", "move_lab_readiness_packet"),
        (move_lab_evidence_intake_path, "proof/move-lab-evidence-intake.json", "move_lab_evidence_intake"),
        (source_collection_plan_path, "proof/source-collection-plan.md", "source_collection_plan"),
        (source_endpoint_evidence_request_path, "proof/source-endpoint-evidence-request.md", "source_endpoint_evidence_request"),
        (move_lab_evidence_request_path, "proof/move-lab-evidence-request.md", "move_lab_evidence_request"),
        (external_proof_plan_path, "proof/external-proof-plan.json", "external_proof_plan"),
        (operator_gate_summary_path, "proof/operator-gate-summary.md", "operator_gate_summary"),
        (handoff_package_path, "handoff/handoff-package.zip", "handoff_package"),
    )
    for path, archive_path, role in optional_entries:
        if path:
            entries.append(file_entry(path, archive_path, role))
    if move_lab_capture_kit_dir:
        entries.extend(capture_kit_entries(move_lab_capture_kit_dir))

    manifest = {
        "schema_version": MVP_PROOF_MANIFEST_SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "files": [archive_manifest_entry(entry) for entry in entries],
    }
    package_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(package_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("mvp-proof-manifest.json", json.dumps(manifest, indent=2).encode("utf-8"))
        for entry in entries:
            archive.write(str(entry["source_path"]), arcname=str(entry["path"]))
    return package_path


def verify_mvp_proof_package(package_path: Path) -> MvpProofVerification:
    errors: list[str] = []
    checked = 0
    with zipfile.ZipFile(package_path, "r") as archive:
        names = set(archive.namelist())
        if "mvp-proof-manifest.json" not in names:
            return MvpProofVerification(0, (), ("package missing mvp-proof-manifest.json",))
        manifest = json.loads(archive.read("mvp-proof-manifest.json").decode("utf-8"))
        if manifest.get("schema_version") != MVP_PROOF_MANIFEST_SCHEMA:
            return MvpProofVerification(0, (), ("unsupported MVP proof manifest schema",))
        files = manifest.get("files")
        if not isinstance(files, list):
            return MvpProofVerification(0, (), ("MVP proof manifest must contain a files list",))
        roles_seen: list[str] = []
        paths_seen: set[str] = set()
        for entry in files:
            checked += 1
            if not isinstance(entry, dict):
                errors.append("MVP proof manifest file entry must be an object")
                continue
            role = str(entry.get("role") or "")
            path = str(entry.get("path") or "")
            if not role:
                errors.append(f"{path or 'unknown'}: missing manifest role")
            elif role not in ROLE_ARCHIVE_PATHS:
                errors.append(f"{path or role}: unsupported manifest role {role}")
            elif ROLE_ARCHIVE_PATHS[role] != path:
                errors.append(f"{path}: role {role} must use archive path {ROLE_ARCHIVE_PATHS[role]}")
            elif role in roles_seen:
                errors.append(f"{path}: duplicate manifest role {role}")
            else:
                roles_seen.append(role)
            if path in paths_seen:
                errors.append(f"{path}: duplicate manifest archive path")
            paths_seen.add(path)
            if path not in names:
                errors.append(f"{path}: missing from MVP proof package")
                continue
            data = archive.read(path)
            try:
                expected_size = int(entry.get("size_bytes", -1))
            except (TypeError, ValueError):
                expected_size = -1
            if len(data) != expected_size:
                errors.append(f"{path}: size mismatch expected={entry.get('size_bytes', 'missing')} actual={len(data)}")
            if hashlib.sha256(data).hexdigest() != entry.get("sha256"):
                errors.append(f"{path}: sha256 mismatch")
            validate_packaged_role(role, path, data, errors)
        missing_roles = sorted(REQUIRED_ROLES.difference(roles_seen))
        for role in missing_roles:
            errors.append(f"missing required MVP proof role: {role}")
        capture_roles = {"move_lab_capture_template", "move_lab_capture_checklist"}.intersection(roles_seen)
        if capture_roles and capture_roles != {"move_lab_capture_template", "move_lab_capture_checklist"}:
            missing_capture_roles = sorted({"move_lab_capture_template", "move_lab_capture_checklist"}.difference(roles_seen))
            errors.append(f"Move lab capture kit roles must be packaged together; missing {', '.join(missing_capture_roles)}")
        capture_package_roles = {
            "move_lab_capture_template",
            "move_lab_capture_checklist",
            "move_lab_capture_validation",
        }.intersection(roles_seen)
        expected_capture_package_roles = {
            "move_lab_capture_template",
            "move_lab_capture_checklist",
            "move_lab_capture_validation",
        }
        if capture_package_roles and capture_package_roles != expected_capture_package_roles:
            missing_capture_package_roles = sorted(expected_capture_package_roles.difference(roles_seen))
            errors.append(f"Move lab capture kit and validation proof must be packaged together; missing {', '.join(missing_capture_package_roles)}")
    return MvpProofVerification(checked, tuple(roles_seen), tuple(errors))


def summarize_mvp_proof_package(package_path: Path) -> MvpProofSummary:
    verification = verify_mvp_proof_package(package_path)
    with zipfile.ZipFile(package_path, "r") as archive:
        manifest = json.loads(archive.read("mvp-proof-manifest.json").decode("utf-8"))
        roles = tuple(str(entry.get("role") or "") for entry in manifest.get("files", []) if isinstance(entry, dict))
        mvp_audit = read_optional_json(archive, "proof/mvp-audit.json")
        live_proof = read_optional_json(archive, "proof/live-proof-validation.json")
        move_submit = read_optional_json(archive, "proof/move-submit-readiness.json")
        move_lab_transcript = read_optional_json(archive, "proof/move-lab-transcript-validation.json")
        move_lab = read_optional_json(archive, "proof/move-lab-proof-validation.json")
        move_lab_capture = read_optional_json(archive, "proof/move-lab-capture-kit-validation.json")
        move_lab_readiness = read_optional_json(archive, "proof/move-lab-readiness-packet.json")
        move_lab_intake = read_optional_json(archive, "proof/move-lab-evidence-intake.json")
        external_proof_plan = read_optional_json(archive, "proof/external-proof-plan.json")
        handoff_roles = read_nested_handoff_roles(archive)

    requirements = tuple(
        {
            "id": str(requirement.get("id") or "unknown"),
            "status": str(requirement.get("status") or "unknown"),
            "warnings": tuple(str(item) for item in requirement.get("warnings", []) if str(item)),
            "errors": tuple(str(item) for item in requirement.get("errors", []) if str(item)),
        }
        for requirement in mvp_audit.get("requirements", [])
        if isinstance(requirement, dict)
    )
    move_scope = move_lab_scope(move_lab)
    return MvpProofSummary(
        package_path=package_path,
        verification=verification,
        generated_at=datetime.now(UTC).isoformat(),
        roles=tuple(role for role in roles if role),
        mvp_status=str(mvp_audit.get("status") or "missing"),
        mvp_counts={str(key): int(value) for key, value in (mvp_audit.get("summary") or {}).items()},
        requirements=requirements,
        live_proof_status=str(live_proof.get("status") or "missing"),
        move_submit_status=str(move_submit.get("status") or "missing"),
        move_lab_transcript_status=str(move_lab_transcript.get("status") or "missing"),
        move_lab_status=str(move_lab.get("status") or "missing"),
        move_lab_scope=move_scope,
        has_runbook="move_lab_runbook" in roles,
        has_closure_checklist="move_lab_closure_checklist" in roles,
        has_capture_kit={"move_lab_capture_template", "move_lab_capture_checklist"}.issubset(set(roles)),
        move_lab_capture_validation_status=str(move_lab_capture.get("status") or "missing"),
        move_lab_readiness_packet_status=str(move_lab_readiness.get("status") or "missing"),
        move_lab_evidence_intake_status=str(move_lab_intake.get("status") or "missing"),
        has_source_collection_plan="source_collection_plan" in roles,
        has_source_endpoint_evidence_request="source_endpoint_evidence_request" in roles,
        has_move_lab_evidence_request="move_lab_evidence_request" in roles,
        external_proof_plan_status=str(external_proof_plan.get("status") or "missing"),
        has_operator_summary="operator_gate_summary" in roles,
        has_handoff="handoff_package" in roles,
        handoff_verification_status=handoff_verification_status(verification, roles),
        handoff_roles=handoff_roles,
        handoff_role_counts=count_roles(handoff_roles),
    )


def write_mvp_proof_summary(package_path: Path, out_path: Path) -> MvpProofSummary:
    summary = summarize_mvp_proof_package(package_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(summary.to_markdown(), encoding="utf-8")
    return summary


def validate_mvp_proof_summary(package_path: Path, summary_path: Path) -> MvpProofSummaryValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0

    try:
        text = summary_path.read_text(encoding="utf-8")
    except OSError as exc:
        return MvpProofSummaryValidation(1, (f"MVP proof summary is unreadable: {exc}",), ())

    expected = summarize_mvp_proof_package(package_path)
    expected_lines = expected.to_markdown().splitlines()
    required_fragments = (
        "# MVP Proof Package Summary",
        "## Roles",
        "## Handoff Package Roles",
        "## MVP Requirements",
        "## Residual Risk",
        f"- Package verification: `{'pass' if expected.verification.ok else 'fail'}`",
        f"- Files checked: `{expected.verification.checked}`",
        f"- Roles present: `{len(expected.roles)}`",
        f"- MVP status: `{expected.mvp_status}`",
        f"- Requirement counts: `pass={expected.mvp_counts.get('pass', 0)}, partial={expected.mvp_counts.get('partial', 0)}, fail={expected.mvp_counts.get('fail', 0)}`",
        f"- Move lab scope: `{expected.move_lab_scope}`",
        f"- Move lab readiness packet: `{expected.move_lab_readiness_packet_status}`",
        f"- Move lab evidence intake: `{expected.move_lab_evidence_intake_status}`",
        f"- Handoff package: `{expected.handoff_verification_status}`",
        f"- Handoff roles: `{len(expected.handoff_roles)}`",
    )
    for fragment in required_fragments:
        checks += 1
        if fragment not in text:
            errors.append(f"MVP proof summary missing required text: {fragment}")

    for role in expected.roles:
        checks += 1
        role_line = f"| `{role}` | `{ROLE_ARCHIVE_PATHS.get(role, 'unknown')}` |"
        if role_line not in text:
            errors.append(f"MVP proof summary missing role row: {role}")

    for role in expected.handoff_roles:
        checks += 1
        role_line = f"| `{role}` | `{expected.handoff_role_counts.get(role, 0)}` |"
        if role_line not in text:
            errors.append(f"MVP proof summary missing handoff role row: {role}")

    for line in expected_lines:
        if line.startswith("| `") and " | `" in line:
            checks += 1
            if line not in text:
                errors.append(f"MVP proof summary missing expected table row: {line}")

    if expected.mvp_status == "partial" and "MVP status is partial" not in text:
        warnings.append("Partial MVP proof summary should call out partial MVP residual risk")

    return MvpProofSummaryValidation(checks, tuple(errors), tuple(warnings))


def build_mvp_closure_report(package_path: Path) -> MvpClosureReport:
    summary = summarize_mvp_proof_package(package_path)
    open_items: list[MvpClosureItem] = []
    residual_risks: list[str] = []

    if not summary.verification.ok:
        for error in summary.verification.errors:
            open_items.append(
                MvpClosureItem(
                    area="proof_package_integrity",
                    status="fail",
                    blocking=True,
                    action="Rebuild the MVP proof package after correcting the manifest, hashes, roles, or packaged files.",
                    required_evidence="A verified MVP proof package with no integrity errors.",
                    reason=error,
                )
            )

    if summary.live_proof_status != "pass":
        open_items.append(
            MvpClosureItem(
                area="read_only_collection",
                status=summary.live_proof_status,
                blocking=True,
                action="Run approved read-only vCenter and Prism Central collection, then validate the redacted live proof.",
                required_evidence="nmrcp_live_endpoint_proof_v1 with status=pass.",
                reason="Live endpoint proof is required to close the read-only collection MVP requirement.",
            )
        )

    for requirement in summary.requirements:
        status = str(requirement.get("status") or "unknown")
        if status == "pass":
            continue
        notes = tuple(str(item) for item in requirement.get("errors", ()) or requirement.get("warnings", ()))
        open_items.append(
            MvpClosureItem(
                area=str(requirement.get("id") or "unknown"),
                status=status,
                blocking=status != "pass",
                action=closure_action_for_requirement(str(requirement.get("id") or "")),
                required_evidence=closure_evidence_for_requirement(str(requirement.get("id") or "")),
                reason="; ".join(notes) if notes else "Requirement is not fully passing in the MVP audit.",
            )
        )

    if summary.move_submit_status != "pass":
        open_items.append(
            MvpClosureItem(
                area="move_submit_readiness",
                status=summary.move_submit_status,
                blocking=True,
                action="Validate the reviewed lab-only Move dry-run payload with the lab acknowledgement set.",
                required_evidence="nmrcp_move_submit_readiness_v1 with status=pass.",
                reason="Move API payloads need an explicit fail-closed lab readiness proof before proof packaging.",
            )
        )

    if summary.move_lab_transcript_status not in {"pass", "warn"}:
        open_items.append(
            MvpClosureItem(
                area="move_lab_transcript",
                status=summary.move_lab_transcript_status,
                blocking=True,
                action="Capture and validate a redacted approved lab Move API transcript.",
                required_evidence="nmrcp_move_lab_transcript_validation_v1 with status=pass or warn.",
                reason="Approved Move proof must be traceable to a validated lab transcript.",
            )
        )

    if summary.move_lab_status != "pass" or summary.move_lab_scope != "approved_lab_move_appliance":
        open_items.append(
            MvpClosureItem(
                area="move_lab_proof",
                status=summary.move_lab_status,
                blocking=True,
                action="Replace simulated proof with approved lab Move appliance proof, validate it with --transcript-validation, and package passing evidence intake.",
                required_evidence="nmrcp_move_lab_proof_validation_v1 with status=pass and proof_scope=approved_lab_move_appliance, plus nmrcp_move_lab_evidence_intake_v1 with status=pass.",
                reason=f"Move proof status={summary.move_lab_status}; scope={summary.move_lab_scope}.",
            )
        )
        residual_risks.append("Real approved Nutanix Move appliance behavior remains unproven.")
    elif summary.move_lab_evidence_intake_status != "pass":
        open_items.append(
            MvpClosureItem(
                area="move_lab_evidence_intake",
                status=summary.move_lab_evidence_intake_status,
                blocking=True,
                action="Package passing Move lab evidence intake proof with the approved lab proof set.",
                required_evidence="nmrcp_move_lab_evidence_intake_v1 with status=pass.",
                reason="Approved Move proof needs a final intake record tying raw transcript, validation files, proof, and capture-kit validation together.",
            )
        )

    if not summary.has_runbook:
        open_items.append(
            MvpClosureItem(
                area="move_lab_runbook",
                status="missing",
                blocking=False,
                action="Generate the Move lab execution runbook from the reviewed payload and proof template.",
                required_evidence="Move lab execution runbook Markdown packaged as move_lab_runbook.",
                reason="The proof package does not include operator steps for repeating the lab proof window.",
            )
        )

    if not summary.has_capture_kit or summary.move_lab_capture_validation_status != "pass":
        open_items.append(
            MvpClosureItem(
                area="move_lab_capture_kit",
                status=summary.move_lab_capture_validation_status if summary.has_capture_kit else "missing",
                blocking=True,
                action="Package the Move lab capture kit and passing capture-kit validation.",
                required_evidence="Move lab transcript template, capture checklist, and nmrcp_move_lab_capture_kit_validation_v1 status=pass.",
                reason="Approved lab capture needs repeatable template and checklist proof.",
            )
        )

    if summary.move_lab_readiness_packet_status not in {"pass", "warn"}:
        open_items.append(
            MvpClosureItem(
                area="move_lab_readiness_packet",
                status=summary.move_lab_readiness_packet_status,
                blocking=False,
                action="Generate and package the Move lab readiness packet before the approved lab window.",
                required_evidence="nmrcp_move_lab_readiness_packet_v1 with status=pass or warn and no errors.",
                reason="Reviewers need the hash-addressed pre-lab operator handoff packet alongside capture-kit and lab proof artifacts.",
            )
        )

    if not summary.has_operator_summary:
        open_items.append(
            MvpClosureItem(
                area="operator_gate_summary",
                status="missing",
                blocking=False,
                action="Generate and package the operator gate summary.",
                required_evidence="Operator gate summary Markdown packaged as operator_gate_summary.",
                reason="Reviewers need the compact gate matrix inside the proof package.",
            )
        )

    if not summary.has_source_endpoint_evidence_request:
        open_items.append(
            MvpClosureItem(
                area="source_endpoint_evidence_request",
                status="missing",
                blocking=False,
                action="Package the generated source endpoint evidence request with the MVP proof bundle.",
                required_evidence="Validated source-endpoint-evidence-request.md packaged as source_endpoint_evidence_request.",
                reason="Reviewers need the approved read-only source collection request alongside live endpoint proof.",
            )
        )
    if not summary.has_source_collection_plan:
        open_items.append(
            MvpClosureItem(
                area="source_collection_plan",
                status="missing",
                blocking=False,
                action="Generate and package source-collection-plan.md from the completed assessment intake.",
                required_evidence="Validated source-collection-plan.md packaged as source_collection_plan.",
                reason="Operators need the no-contact collection sequence, privacy posture, proof outputs, and stop conditions before approved endpoint access.",
            )
        )

    if not summary.has_move_lab_evidence_request:
        open_items.append(
            MvpClosureItem(
                area="move_lab_evidence_request",
                status="missing",
                blocking=False,
                action="Package the generated Move lab evidence request with the MVP proof bundle.",
                required_evidence="Validated move-lab-evidence-request.md packaged as move_lab_evidence_request.",
                reason="Reviewers need the approved lab proof-window request alongside Move lab proof artifacts.",
            )
        )

    if summary.external_proof_plan_status == "missing":
        open_items.append(
            MvpClosureItem(
                area="external_proof_plan",
                status="missing",
                blocking=False,
                action="Generate and package the external proof gap plan.",
                required_evidence="nmrcp_external_proof_plan_v1 packaged as external_proof_plan.",
                reason="Reviewers need one combined closeout plan for approved endpoint and Move proof gaps.",
            )
        )

    if not summary.has_handoff:
        open_items.append(
            MvpClosureItem(
                area="handoff_package",
                status="missing",
                blocking=True,
                action="Package and verify the assessment handoff bundle.",
                required_evidence="Verified handoff package zip packaged as handoff_package.",
                reason="External handoff requires the validated assessment, approvals, remediation, and Move staging artifacts.",
            )
        )

    if summary.mvp_status == "partial":
        residual_risks.append("MVP audit is partial; at least one requirement still depends on external proof.")
    if summary.mvp_status == "fail":
        residual_risks.append("MVP audit failed; do not use the package for review.")

    ready = not any(item.blocking for item in open_items) and summary.mvp_status == "pass"
    overall = "pass" if ready else "fail" if any(item.status == "fail" for item in open_items) else "partial"
    closeout_commands = closure_commands_for_open_items(open_items)
    closure_summary = summarize_closure_state(open_items, closeout_commands, residual_risks)
    return MvpClosureReport(
        package_path=package_path,
        generated_at=datetime.now(UTC).isoformat(),
        ready_for_external_handoff=ready,
        overall_status=overall,
        closure_summary=closure_summary,
        open_items=tuple(open_items),
        closeout_commands=closeout_commands,
        verified_roles=summary.verification.roles if summary.verification.ok else (),
        handoff_roles=summary.handoff_roles if summary.verification.ok else (),
        handoff_role_counts=summary.handoff_role_counts if summary.verification.ok else {},
        residual_risks=tuple(dict.fromkeys(residual_risks)),
    )


def write_mvp_closure_report(package_path: Path, out_path: Path, json_out_path: Path | None = None) -> MvpClosureReport:
    report = build_mvp_closure_report(package_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.to_markdown(), encoding="utf-8")
    if json_out_path:
        json_out_path.parent.mkdir(parents=True, exist_ok=True)
        json_out_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return report


def validate_mvp_closure_report(
    package_path: Path,
    json_report_path: Path,
    *,
    markdown_report_path: Path | None = None,
) -> MvpClosureReportValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0

    try:
        payload = json.loads(json_report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return MvpClosureReportValidation(1, (f"MVP closure report JSON is unreadable: {exc}",), ())
    if not isinstance(payload, dict):
        return MvpClosureReportValidation(1, ("MVP closure report JSON must be an object",), ())

    checks += 1
    if payload.get("schema_version") != "nmrcp_mvp_closure_report_v1":
        errors.append("MVP closure report schema_version must be nmrcp_mvp_closure_report_v1")

    expected = build_mvp_closure_report(package_path).to_dict()
    comparable_keys = (
        "package",
        "ready_for_external_handoff",
        "overall_status",
        "closure_summary",
        "open_items",
        "closeout_commands",
        "verified_roles",
        "handoff_roles",
        "handoff_role_counts",
        "residual_risks",
    )
    for key in comparable_keys:
        checks += 1
        if key == "package":
            if not same_package_reference(payload.get(key), expected.get(key)):
                errors.append(f"MVP closure report JSON field {key} does not match current MVP proof package")
            continue
        if json_compatible(payload.get(key)) != json_compatible(expected.get(key)):
            errors.append(f"MVP closure report JSON field {key} does not match current MVP proof package")

    generated_at = str(payload.get("generated_at") or "")
    checks += 1
    if not generated_at:
        errors.append("MVP closure report JSON missing generated_at")

    if payload.get("ready_for_external_handoff") is True and payload.get("overall_status") != "pass":
        errors.append("ready_for_external_handoff=true requires overall_status pass")
    if payload.get("overall_status") == "pass" and payload.get("ready_for_external_handoff") is not True:
        errors.append("overall_status pass requires ready_for_external_handoff=true")
    if payload.get("overall_status") == "partial":
        open_items = payload.get("open_items") if isinstance(payload.get("open_items"), list) else []
        if not open_items:
            warnings.append("Partial MVP closure report should include open_items")

    if markdown_report_path:
        try:
            text = markdown_report_path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"MVP closure report Markdown is unreadable: {exc}")
            text = ""
        required_fragments = (
            "# MVP Closure Report",
            "## Required Evidence IDs",
            "## Open Items",
            "## Closeout Commands",
            "## Verified Roles",
            "## Handoff Package Roles",
            "## Residual Risks",
            f"- Overall status: `{payload.get('overall_status')}`",
            f"- Ready for external handoff: `{'yes' if payload.get('ready_for_external_handoff') else 'no'}`",
            f"- Blocking open items: `{(payload.get('closure_summary') or {}).get('blocking_open_items', 0)}`",
            f"- Required evidence IDs: `{(payload.get('closure_summary') or {}).get('required_evidence_id_count', 0)}`",
            f"- Closeout command lines: `{(payload.get('closure_summary') or {}).get('closeout_command_lines', 0)}`",
            f"- Verified proof roles: `{len(payload.get('verified_roles') if isinstance(payload.get('verified_roles'), list) else [])}`",
            f"- Nested handoff roles: `{len(payload.get('handoff_roles') if isinstance(payload.get('handoff_roles'), list) else [])}`",
        )
        for fragment in required_fragments:
            checks += 1
            if fragment not in text:
                errors.append(f"MVP closure report Markdown missing required text: {fragment}")
        for evidence_id in required_evidence_ids_from_payload(payload):
            checks += 1
            fragment = f"- `{evidence_id}`"
            if fragment not in text:
                errors.append(f"MVP closure report Markdown missing required evidence ID: {evidence_id}")
        for command in closeout_commands_from_payload(payload):
            checks += 1
            if command not in text:
                errors.append(f"MVP closure report Markdown missing closeout command line: {command}")

    return MvpClosureReportValidation(checks, tuple(errors), tuple(warnings))


def closure_action_for_requirement(requirement_id: str) -> str:
    actions = {
        "read_only_collection": "Supply validated live vCenter and Prism Central read-only proof.",
        "move_ready_plan": "Supply approved lab Move appliance proof with passing evidence intake, then rerun MVP audit with --move-proof and --move-lab-evidence-intake.",
        "handoff_and_review": "Supply missing final closure evidence or resolve/accept remaining handoff change-gate warnings.",
        "waves_and_change_evidence": "Regenerate and validate migration waves, change-board evidence, runbook, report, dashboard, and risk artifacts.",
    }
    return actions.get(requirement_id, "Resolve the MVP audit warnings/errors and regenerate the proof package.")


def closure_evidence_for_requirement(requirement_id: str) -> str:
    evidence = {
        "read_only_collection": "Passing nmrcp_live_endpoint_proof_v1.",
        "move_ready_plan": "Passing approved-lab nmrcp_move_lab_proof_validation_v1 and nmrcp_move_lab_evidence_intake_v1.",
        "handoff_and_review": "Passing final change gate with verified closure evidence, documented warning acceptance if needed, and verified handoff package.",
        "waves_and_change_evidence": "Passing generated artifact contract validations.",
    }
    return evidence.get(requirement_id, "Passing MVP audit requirement evidence.")


def summarize_closure_state(
    open_items: list[MvpClosureItem],
    closeout_commands: tuple[str, ...],
    residual_risks: list[str],
) -> dict[str, Any]:
    required_evidence_ids = sorted(
        {
            evidence_id
            for item in open_items
            for evidence_id in extract_required_evidence_ids(item.required_evidence)
        }
    )
    blocking_items = [item for item in open_items if item.blocking]
    return {
        "open_items": len(open_items),
        "blocking_open_items": len(blocking_items),
        "nonblocking_open_items": len(open_items) - len(blocking_items),
        "required_evidence_id_count": len(required_evidence_ids),
        "required_evidence_ids": required_evidence_ids,
        "closeout_command_lines": len(closeout_commands),
        "residual_risks": len(dict.fromkeys(residual_risks)),
    }


def extract_required_evidence_ids(text: str) -> tuple[str, ...]:
    return tuple(sorted(set(re.findall(r"nmrcp_[a-z0-9_]+_v\d+", text or ""))))


def required_evidence_ids_from_payload(payload: dict[str, Any]) -> tuple[str, ...]:
    closure_summary = payload.get("closure_summary") if isinstance(payload.get("closure_summary"), dict) else {}
    ids = closure_summary.get("required_evidence_ids")
    if not isinstance(ids, list):
        return ()
    return tuple(str(item) for item in ids)


def closeout_commands_from_payload(payload: dict[str, Any]) -> tuple[str, ...]:
    commands = payload.get("closeout_commands")
    if not isinstance(commands, list):
        return ()
    return tuple(str(item) for item in commands if str(item).strip())


def handoff_verification_status(verification: MvpProofVerification, roles: tuple[str, ...]) -> str:
    if "handoff_package" not in roles:
        return "missing"
    if verification.ok:
        return "verified"
    if any("handoff/handoff-package.zip" in error for error in verification.errors):
        return "invalid"
    return "present_unverified"


def closure_commands_for_open_items(open_items: list[MvpClosureItem]) -> tuple[str, ...]:
    areas = {item.area for item in open_items}
    commands: list[str] = []
    if {"move_ready_plan", "move_lab_proof", "move_lab_evidence_intake"}.intersection(areas):
        commands.extend(
            [
                '$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"',
                "python -m nmrcp.cli validate-move-submit-readiness `",
                "  --payload outputs\\sample-assessment\\move-api-payload.lab.dry-run.json `",
                "  --review examples\\sample_move_submit_review.json `",
                "  --out outputs\\move-submit-readiness.json",
                "python -m nmrcp.cli validate-move-lab-transcript `",
                "  --transcript outputs\\move-lab-capture-kit\\move-lab-transcript.approved.json `",
                "  --payload outputs\\sample-assessment\\move-api-payload.lab.dry-run.json `",
                "  --review examples\\sample_move_submit_review.json `",
                "  --out outputs\\move-lab-transcript-validation.json",
                "python -m nmrcp.cli generate-approved-move-lab-proof `",
                "  --transcript outputs\\move-lab-capture-kit\\move-lab-transcript.approved.json `",
                "  --transcript-validation outputs\\move-lab-transcript-validation.json `",
                "  --payload outputs\\sample-assessment\\move-api-payload.lab.dry-run.json `",
                "  --review examples\\sample_move_submit_review.json `",
                "  --approved-by \"Lab Migration Lead\" `",
                "  --out outputs\\move-lab-proof.approved.json",
                "python -m nmrcp.cli validate-move-lab-proof `",
                "  --proof outputs\\move-lab-proof.approved.json `",
                "  --payload outputs\\sample-assessment\\move-api-payload.lab.dry-run.json `",
                "  --review examples\\sample_move_submit_review.json `",
                "  --transcript-validation outputs\\move-lab-transcript-validation.json `",
                "  --out outputs\\move-lab-proof-validation.json",
                "python -m nmrcp.cli validate-move-lab-evidence-intake `",
                "  --payload outputs\\sample-assessment\\move-api-payload.lab.dry-run.json `",
                "  --review examples\\sample_move_submit_review.json `",
                "  --transcript outputs\\move-lab-capture-kit\\move-lab-transcript.approved.json `",
                "  --transcript-validation outputs\\move-lab-transcript-validation.json `",
                "  --proof outputs\\move-lab-proof.approved.json `",
                "  --proof-validation outputs\\move-lab-proof-validation.json `",
                "  --capture-kit-validation outputs\\move-lab-capture-kit-validation.json `",
                "  --out outputs\\move-lab-evidence-intake.json",
                "python -m nmrcp.cli summarize-gates `",
                "  --dir outputs\\sample-assessment `",
                "  --move-lab-proof outputs\\move-lab-proof-validation.json `",
                "  --move-lab-evidence-intake outputs\\move-lab-evidence-intake.json",
                "python -m nmrcp.cli change-gate `",
                "  --dir outputs\\sample-assessment `",
                "  --move-lab-proof outputs\\move-lab-proof-validation.json `",
                "  --move-lab-evidence-intake outputs\\move-lab-evidence-intake.json",
                "python -m nmrcp.cli package-handoff `",
                "  --dir outputs\\sample-assessment `",
                "  --move-lab-proof outputs\\move-lab-proof-validation.json `",
                "  --move-lab-evidence-intake outputs\\move-lab-evidence-intake.json `",
                "  --move-lab-readiness-packet outputs\\move-lab-readiness-packet.json `",
                "  --out outputs\\handoff-package.zip",
                "python -m nmrcp.cli verify-handoff --package outputs\\handoff-package.zip",
                "python -m nmrcp.cli mvp-audit `",
                "  --repo-root . `",
                "  --assessment-dir outputs\\sample-assessment `",
                "  --assessment-intake outputs\\assessment-intake.csv `",
                "  --live-proof outputs\\source-collection\\live-proof-validation.json `",
                "  --move-proof outputs\\move-lab-proof-validation.json `",
                "  --move-lab-evidence-intake outputs\\move-lab-evidence-intake.json `",
                "  --out outputs\\mvp-audit.json",
                "python -m nmrcp.cli external-proof-plan `",
                "  --repo-root . `",
                "  --assessment-intake outputs\\assessment-intake.csv `",
                "  --live-proof outputs\\source-collection\\live-proof-validation.json `",
                "  --move-proof outputs\\move-lab-proof-validation.json `",
                "  --move-lab-evidence-intake outputs\\move-lab-evidence-intake.json `",
                "  --out outputs\\external-proof-plan.md `",
                "  --json-out outputs\\external-proof-plan.json",
                "python -m nmrcp.cli package-mvp-proof `",
                "  --mvp-audit outputs\\mvp-audit.json `",
                "  --live-proof outputs\\source-collection\\live-proof-validation.json `",
                "  --move-submit-readiness outputs\\move-submit-readiness.json `",
                "  --move-lab-transcript outputs\\move-lab-transcript-validation.json `",
                "  --move-lab-proof outputs\\move-lab-proof-validation.json `",
                "  --move-lab-runbook outputs\\sample-assessment\\move-lab-execution-runbook.md `",
                "  --move-lab-closure-checklist outputs\\sample-assessment\\move-lab-closure-checklist.md `",
                "  --move-lab-capture-kit outputs\\move-lab-capture-kit `",
                "  --move-lab-capture-validation outputs\\move-lab-capture-kit-validation.json `",
                "  --move-lab-readiness-packet outputs\\move-lab-readiness-packet.json `",
                "  --move-lab-evidence-intake outputs\\move-lab-evidence-intake.json `",
                "  --source-collection-plan outputs\\source-collection-plan.md `",
                "  --source-endpoint-evidence-request outputs\\sample-assessment\\source-endpoint-evidence-request.md `",
                "  --move-lab-evidence-request outputs\\sample-assessment\\move-lab-evidence-request.md `",
                "  --external-proof-plan outputs\\external-proof-plan.json `",
                "  --operator-gate-summary outputs\\sample-assessment\\operator-gate-summary.md `",
                "  --handoff-package outputs\\handoff-package.zip `",
                "  --out outputs\\mvp-proof-package.zip",
                "python -m nmrcp.cli verify-mvp-proof --package outputs\\mvp-proof-package.zip",
                "python -m nmrcp.cli summarize-mvp-proof `",
                "  --package outputs\\mvp-proof-package.zip `",
                "  --out outputs\\mvp-proof-summary.md",
                "python -m nmrcp.cli validate-mvp-proof-summary `",
                "  --package outputs\\mvp-proof-package.zip `",
                "  --summary outputs\\mvp-proof-summary.md",
                "python -m nmrcp.cli mvp-closure-report `",
                "  --package outputs\\mvp-proof-package.zip `",
                "  --out outputs\\mvp-closure-report.md `",
                "  --json-out outputs\\mvp-closure-report.json",
                "python -m nmrcp.cli validate-mvp-closure-report `",
                "  --package outputs\\mvp-proof-package.zip `",
                "  --report outputs\\mvp-closure-report.md `",
                "  --json-report outputs\\mvp-closure-report.json",
                "python -m nmrcp.cli launch-readiness-report `",
                "  --package outputs\\mvp-proof-package.zip `",
                "  --out outputs\\launch-readiness-report.md `",
                "  --json-out outputs\\launch-readiness-report.json",
                "python -m nmrcp.cli validate-launch-readiness-report `",
                "  --package outputs\\mvp-proof-package.zip `",
                "  --report outputs\\launch-readiness-report.md `",
                "  --json-report outputs\\launch-readiness-report.json",
                "Remove-Item Env:\\NMRCP_MOVE_LAB_ACK",
            ]
        )
    return tuple(commands)


def read_optional_json(archive: zipfile.ZipFile, archive_path: str) -> dict[str, Any]:
    if archive_path not in archive.namelist():
        return {}
    payload = json.loads(archive.read(archive_path).decode("utf-8"))
    return payload if isinstance(payload, dict) else {}


def read_nested_handoff_roles(archive: zipfile.ZipFile) -> tuple[str, ...]:
    archive_path = "handoff/handoff-package.zip"
    if archive_path not in archive.namelist():
        return ()
    try:
        with zipfile.ZipFile(io.BytesIO(archive.read(archive_path)), "r") as handoff:
            manifest = json.loads(handoff.read("handoff-manifest.json").decode("utf-8"))
    except (KeyError, OSError, zipfile.BadZipFile, UnicodeDecodeError, json.JSONDecodeError):
        return ()
    files = manifest.get("files")
    if not isinstance(files, list):
        return ()
    return tuple(
        str(entry.get("role") or "")
        for entry in files
        if isinstance(entry, dict) and str(entry.get("role") or "")
    )


def handoff_role_status(handoff_roles: tuple[str, ...], role: str) -> str:
    if role in handoff_roles:
        return "present"
    if handoff_roles:
        return "missing"
    return "unknown"


def count_roles(roles: tuple[str, ...]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for role in roles:
        counts[role] = counts.get(role, 0) + 1
    return counts


def move_lab_scope(payload: dict[str, Any]) -> str:
    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    for check in checks:
        if isinstance(check, dict) and check.get("name") == "move-lab-proof-scope":
            return str(check.get("detail") or "missing")
    return "missing"


def validate_packaged_role(role: str, path: str, data: bytes, errors: list[str]) -> None:
    if role == "mvp_audit":
        payload = read_role_json(path, data, errors)
        if not payload:
            return
        if payload.get("schema_version") != "nmrcp_mvp_readiness_audit_v1":
            errors.append(f"{path}: mvp_audit schema_version must be nmrcp_mvp_readiness_audit_v1")
        if payload.get("status") == "fail":
            errors.append(f"{path}: mvp_audit status must not be fail")
        if payload.get("status") not in {"pass", "partial"}:
            errors.append(f"{path}: mvp_audit status must be pass or partial")
    elif role == "live_endpoint_proof":
        validate_live_endpoint_proof_role(path, data, errors)
    elif role == "move_submit_readiness":
        validate_json_schema_status(path, data, "nmrcp_move_submit_readiness_v1", {"pass"}, errors)
    elif role == "move_lab_transcript":
        validate_json_schema_status(path, data, "nmrcp_move_lab_transcript_validation_v1", {"pass", "warn"}, errors)
    elif role == "move_lab_proof":
        validate_move_lab_proof_role(path, data, errors)
    elif role == "move_lab_runbook":
        text = read_role_text(path, data, errors)
        if text:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                runbook_path = Path(tmp) / "move-lab-execution-runbook.md"
                runbook_path.write_text(text, encoding="utf-8")
                result = validate_move_lab_runbook(runbook_path)
            errors.extend(f"{path}: {error}" for error in result.errors)
    elif role == "move_lab_closure_checklist":
        text = read_role_text(path, data, errors)
        if text:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                checklist_path = Path(tmp) / "move-lab-closure-checklist.md"
                checklist_path.write_text(text, encoding="utf-8")
                result = validate_move_lab_closure_checklist(checklist_path)
            errors.extend(f"{path}: {error}" for error in result.errors)
    elif role == "move_lab_capture_template":
        payload = read_role_json(path, data, errors)
        if not payload:
            return
        if payload.get("schema_version") != "nmrcp_move_lab_transcript_v1":
            errors.append(f"{path}: move_lab_capture_template schema_version must be nmrcp_move_lab_transcript_v1")
        if payload.get("evidence_state") != "template_only_replace_after_lab_capture":
            errors.append(f"{path}: move_lab_capture_template must remain template_only_replace_after_lab_capture")
        if payload.get("production_targets") is not False:
            errors.append(f"{path}: move_lab_capture_template must set production_targets=false")
        if payload.get("mutation_performed") is not False:
            errors.append(f"{path}: move_lab_capture_template must set mutation_performed=false")
    elif role == "move_lab_capture_checklist":
        text = read_role_text(path, data, errors)
        if text and "# Move Lab Capture Checklist" not in text:
            errors.append(f"{path}: move_lab_capture_checklist must contain Move Lab Capture Checklist heading")
    elif role == "move_lab_capture_validation":
        validate_json_schema_status(path, data, "nmrcp_move_lab_capture_kit_validation_v1", {"pass"}, errors)
    elif role == "move_lab_readiness_packet":
        import tempfile

        payload = read_role_json(path, data, errors)
        if not payload:
            return
        with tempfile.TemporaryDirectory() as tmp:
            packet_path = Path(tmp) / "move-lab-readiness-packet.json"
            packet_path.write_bytes(data)
            result = validate_move_lab_readiness_packet(packet_path)
        errors.extend(f"{path}: {error}" for error in result.errors)
    elif role == "move_lab_evidence_intake":
        validate_json_schema_status(path, data, "nmrcp_move_lab_evidence_intake_v1", {"pass"}, errors)
    elif role == "source_collection_plan":
        text = read_role_text(path, data, errors)
        result = validate_source_collection_plan_text(text)
        errors.extend(f"{path}: {error}" for error in result.errors)
    elif role == "source_endpoint_evidence_request":
        text = read_role_text(path, data, errors)
        if text:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                request_path = Path(tmp) / "source-endpoint-evidence-request.md"
                request_path.write_text(text, encoding="utf-8")
                result = validate_source_endpoint_evidence_request(request_path)
            errors.extend(f"{path}: {error}" for error in result.errors)
    elif role == "move_lab_evidence_request":
        text = read_role_text(path, data, errors)
        if text:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                request_path = Path(tmp) / "move-lab-evidence-request.md"
                request_path.write_text(text, encoding="utf-8")
                result = validate_move_lab_evidence_request(request_path)
            errors.extend(f"{path}: {error}" for error in result.errors)
    elif role == "external_proof_plan":
        validate_external_proof_plan_role(path, data, errors)
    elif role == "operator_gate_summary":
        text = read_role_text(path, data, errors)
        if text:
            import tempfile

            with tempfile.TemporaryDirectory() as tmp:
                summary_path = Path(tmp) / "operator-gate-summary.md"
                summary_path.write_text(text, encoding="utf-8")
                result = validate_operator_gate_summary(summary_path)
            errors.extend(f"{path}: {error}" for error in result.errors)
    elif role == "handoff_package":
        import io
        import tempfile

        try:
            with zipfile.ZipFile(io.BytesIO(data), "r") as nested:
                if not nested.namelist():
                    errors.append(f"{path}: handoff_package zip is empty")
        except zipfile.BadZipFile:
            errors.append(f"{path}: handoff_package must be a valid zip")
            return
        with tempfile.TemporaryDirectory() as tmp:
            handoff_path = Path(tmp) / "handoff-package.zip"
            handoff_path.write_bytes(data)
            from .handoff_package import verify_handoff_package

            result = verify_handoff_package(handoff_path)
        errors.extend(f"{path}: {error}" for error in result.errors)


def validate_json_schema_status(
    path: str,
    data: bytes,
    schema_version: str,
    allowed_statuses: set[str],
    errors: list[str],
) -> None:
    payload = read_role_json(path, data, errors)
    if not payload:
        return
    if payload.get("schema_version") != schema_version:
        errors.append(f"{path}: schema_version must be {schema_version}")
    status = str(payload.get("status") or "")
    if status not in allowed_statuses:
        errors.append(f"{path}: status must be one of {', '.join(sorted(allowed_statuses))}")
    payload_errors = payload.get("errors")
    if isinstance(payload_errors, list) and payload_errors:
        errors.append(f"{path}: proof errors must be empty")


def validate_live_endpoint_proof_role(path: str, data: bytes, errors: list[str]) -> None:
    payload = read_role_json(path, data, errors)
    if not payload:
        return
    if payload.get("schema_version") != "nmrcp_live_endpoint_proof_v1":
        errors.append(f"{path}: schema_version must be nmrcp_live_endpoint_proof_v1")
    if payload.get("status") != "pass":
        errors.append(f"{path}: status must be pass")
    payload_errors = payload.get("errors")
    if isinstance(payload_errors, list) and payload_errors:
        errors.append(f"{path}: proof errors must be empty")

    checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    checks_by_name = {
        str(check.get("name") or ""): check
        for check in checks
        if isinstance(check, dict) and check.get("name")
    }
    required_checks = (
        "live-readiness-status",
        "live-readiness-security",
        "collection-summary-schema",
        "collection-summary-privacy",
        "collection-summary-assessment-intake",
        "collection-proof-manifest-security",
        "collection-proof-manifest-api-allowlist",
        "collection-proof-manifest-assessment-intake",
        "collection-proof-manifest-assessment-intake-match",
    )
    for check_name in required_checks:
        check = checks_by_name.get(check_name)
        if not check:
            errors.append(f"{path}: live endpoint proof missing required check {check_name}")
        elif check.get("status") != "pass":
            errors.append(f"{path}: live endpoint proof check {check_name} must pass")


def validate_move_lab_proof_role(path: str, data: bytes, errors: list[str]) -> None:
    import tempfile

    payload = read_role_json(path, data, errors)
    if not payload:
        return
    with tempfile.TemporaryDirectory() as tmp:
        proof_path = Path(tmp) / "move-lab-proof-validation.json"
        proof_path.write_bytes(data)
        from .move_lab_proof import validate_move_lab_proof_validation_file

        result = validate_move_lab_proof_validation_file(
            proof_path,
            require_approved_lab=str(payload.get("status") or "") == "pass",
        )
    errors.extend(f"{path}: {error}" for error in result.errors)


def validate_external_proof_plan_role(path: str, data: bytes, errors: list[str]) -> None:
    payload = read_role_json(path, data, errors)
    if not payload:
        return
    if payload.get("schema_version") != EXTERNAL_PROOF_PLAN_SCHEMA_VERSION:
        errors.append(f"{path}: external_proof_plan schema_version must be {EXTERNAL_PROOF_PLAN_SCHEMA_VERSION}")
    if payload.get("status") not in {"blocked_until_external_evidence", "ready_for_external_handoff"}:
        errors.append(f"{path}: external_proof_plan status must be blocked_until_external_evidence or ready_for_external_handoff")
    steps = payload.get("steps") if isinstance(payload.get("steps"), list) else []
    step_names = {str(step.get("name") or "") for step in steps if isinstance(step, dict)}
    for required in ("Approved read-only source endpoint proof", "Approved Nutanix Move appliance proof"):
        if required not in step_names:
            errors.append(f"{path}: external_proof_plan missing step {required}")
    text = data.decode("utf-8", errors="ignore")
    for fragment in (
        "nmrcp_live_endpoint_proof_v1",
        "nmrcp_move_lab_proof_validation_v1",
        "nmrcp_move_lab_evidence_intake_v1",
        "Do not claim external handoff readiness",
    ):
        if fragment not in text:
            errors.append(f"{path}: external_proof_plan missing required boundary or evidence reference: {fragment}")


def read_role_json(path: str, data: bytes, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: packaged JSON proof is unreadable: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{path}: packaged JSON proof must be an object")
        return {}
    return payload


def read_role_text(path: str, data: bytes, errors: list[str]) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        errors.append(f"{path}: packaged text proof is not UTF-8: {exc}")
        return ""
    if not text.strip():
        errors.append(f"{path}: packaged text proof must not be empty")
    return text


def validate_mvp_audit(path: Path) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != "nmrcp_mvp_readiness_audit_v1":
        raise ValueError("MVP audit proof must use schema nmrcp_mvp_readiness_audit_v1")
    if payload.get("status") == "fail":
        raise ValueError("MVP audit proof status must not be fail")


def file_entry(path: Path, archive_path: str, role: str) -> dict[str, Any]:
    if not path.exists():
        raise ValueError(f"Missing MVP proof file: {path}")
    return {
        "path": archive_path,
        "role": role,
        "source_path": str(path),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def capture_kit_entries(capture_kit_dir: Path) -> list[dict[str, Any]]:
    return [
        file_entry(
            capture_kit_dir / "move-lab-transcript.template.json",
            "proof/move-lab-transcript.template.json",
            "move_lab_capture_template",
        ),
        file_entry(
            capture_kit_dir / "move-lab-capture-checklist.md",
            "proof/move-lab-capture-checklist.md",
            "move_lab_capture_checklist",
        ),
    ]


def archive_manifest_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if key != "source_path"}


def escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def json_compatible(value: Any) -> Any:
    return json.loads(json.dumps(value))


def same_package_reference(actual: object, expected: object) -> bool:
    actual_text = str(actual or "")
    expected_text = str(expected or "")
    if actual_text == expected_text:
        return True
    try:
        return Path(actual_text).resolve() == Path(expected_text).resolve()
    except OSError:
        return False
