from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .mvp_audit import audit_mvp


EXTERNAL_PROOF_PLAN_SCHEMA_VERSION = "nmrcp_external_proof_plan_v1"


@dataclass(frozen=True)
class ExternalProofStep:
    name: str
    status: str
    requirement: str
    current_gap: str
    evidence_ids: tuple[str, ...]
    closeout_commands: tuple[str, ...]
    stop_conditions: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "requirement": self.requirement,
            "current_gap": self.current_gap,
            "evidence_ids": list(self.evidence_ids),
            "closeout_commands": list(self.closeout_commands),
            "stop_conditions": list(self.stop_conditions),
        }


@dataclass(frozen=True)
class ExternalProofPlan:
    status: str
    repo_root: str
    steps: tuple[ExternalProofStep, ...]
    operator_boundaries: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.status == "ready_for_external_handoff"

    def summary(self) -> str:
        blocked = sum(1 for step in self.steps if step.status != "pass")
        return f"{self.status}: steps={len(self.steps)}, blocked={blocked}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": EXTERNAL_PROOF_PLAN_SCHEMA_VERSION,
            "status": self.status,
            "repo_root": self.repo_root,
            "steps": [step.to_dict() for step in self.steps],
            "operator_boundaries": list(self.operator_boundaries),
        }

    def to_markdown(self) -> str:
        lines = [
            "# External Proof Gap Plan",
            "",
            f"- Status: `{self.status}`",
            f"- Repository root: `{self.repo_root}`",
            f"- Step count: `{len(self.steps)}`",
            "",
            "## Proof Steps",
            "",
        ]
        for step in self.steps:
            lines.extend(
                [
                    f"### {step.name}",
                    "",
                    f"- Status: `{step.status}`",
                    f"- Requirement: {step.requirement}",
                    f"- Current gap: {step.current_gap}",
                    f"- Evidence IDs: `{', '.join(step.evidence_ids)}`",
                    "",
                    "Closeout commands:",
                    "",
                    "```powershell",
                    *step.closeout_commands,
                    "```",
                    "",
                    "Stop conditions:",
                    "",
                    *(f"- {condition}" for condition in step.stop_conditions),
                    "",
                ]
            )
        lines.extend(["## Operator Boundaries", ""])
        lines.extend(f"- {boundary}" for boundary in self.operator_boundaries)
        lines.append("")
        return "\n".join(lines)


@dataclass(frozen=True)
class ExternalProofPlanValidation:
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{'PASS' if self.ok else 'FAIL'}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def build_external_proof_plan(
    repo_root: Path,
    *,
    assessment_intake_path: Path | None = None,
    live_proof_path: Path | None = None,
    move_proof_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
) -> ExternalProofPlan:
    root = repo_root.resolve()
    audit = audit_mvp(
        root,
        assessment_intake_path=assessment_intake_path,
        live_proof_path=live_proof_path,
        move_proof_path=move_proof_path,
        move_lab_evidence_intake_path=move_lab_evidence_intake_path,
    )
    by_id = {requirement.id: requirement for requirement in audit.requirements}
    live = by_id["read_only_collection"]
    move = by_id["move_ready_plan"]
    steps = (
        ExternalProofStep(
            "Approved read-only source endpoint proof",
            live.status,
            live.requirement,
            "; ".join((*live.errors, *live.warnings)) or "closed by supplied proof",
            ("nmrcp_live_endpoint_proof_v1",),
            (
                "python -m nmrcp.cli live-readiness --require-vcenter --require-prism --out outputs\\source-collection\\live-readiness.json",
                "python -m nmrcp.cli validate-assessment-intake --intake outputs\\assessment-intake.csv",
                "python -m nmrcp.cli collect-sources --assessment-intake outputs\\assessment-intake.csv --out-dir outputs\\source-collection",
                "python -m nmrcp.cli validate-live-proof --live-readiness outputs\\source-collection\\live-readiness.json --collection-summary outputs\\source-collection\\collection-summary.json --source-dir outputs\\source-collection --out outputs\\source-collection\\live-proof-validation.json",
            ),
            (
                "Stop if vCenter or Prism Central scope is not approved for read-only validation.",
                "Stop if credentials, endpoint values, tokens, FQDNs, IP addresses, or usernames are serialized into evidence.",
                "Stop if collection summary reports any mutating call.",
                "Stop if validate-live-proof does not produce nmrcp_live_endpoint_proof_v1 with status=pass.",
            ),
        ),
        ExternalProofStep(
            "Approved Nutanix Move appliance proof",
            move.status,
            move.requirement,
            "; ".join((*move.errors, *move.warnings)) or "closed by supplied proof",
            ("nmrcp_move_lab_proof_validation_v1", "nmrcp_move_lab_evidence_intake_v1"),
            (
                "powershell -ExecutionPolicy Bypass -File scripts\\move_lab_proof_workflow.ps1 -MoveLabProof outputs\\move-lab-proof.approved.json -MoveLabProofValidation outputs\\move-lab-proof-validation.json -MoveLabEvidenceIntake outputs\\move-lab-evidence-intake.json",
                "python -m nmrcp.cli validate-move-lab-proof --proof outputs\\move-lab-proof.approved.json --payload outputs\\sample-assessment\\move-api-payload.dry-run.json --review outputs\\sample-assessment\\move-submit-readiness.json --transcript-validation outputs\\move-lab-transcript-validation.json --out outputs\\move-lab-proof-validation.json",
                "python -m nmrcp.cli validate-move-lab-evidence-intake --intake outputs\\move-lab-evidence-intake.json --proof outputs\\move-lab-proof.approved.json --proof-validation outputs\\move-lab-proof-validation.json --out outputs\\move-lab-evidence-intake-validation.json",
            ),
            (
                "Stop if the Move appliance is production, unapproved, or outside the reviewed non-production scope.",
                "Stop if any migration is started; approved proof requires started_migrations=0.",
                "Stop if credentials or endpoint values are persisted in transcripts, proof, logs, or packages.",
                "Stop if approved proof and evidence intake do not both validate as passing.",
            ),
        ),
    )
    status = "ready_for_external_handoff" if all(step.status == "pass" for step in steps) else "blocked_until_external_evidence"
    return ExternalProofPlan(status, str(root), steps, operator_boundaries())


def validate_external_proof_plan(
    repo_root: Path,
    json_report_path: Path,
    *,
    markdown_report_path: Path | None = None,
    assessment_intake_path: Path | None = None,
    live_proof_path: Path | None = None,
    move_proof_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
) -> ExternalProofPlanValidation:
    checks = 0
    errors: list[str] = []
    warnings: list[str] = []
    expected = build_external_proof_plan(
        repo_root,
        assessment_intake_path=assessment_intake_path,
        live_proof_path=live_proof_path,
        move_proof_path=move_proof_path,
        move_lab_evidence_intake_path=move_lab_evidence_intake_path,
    )
    checks += 1
    try:
        payload = json.loads(json_report_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validation returns data.
        return ExternalProofPlanValidation(checks, (f"External proof plan JSON is unreadable: {exc}",), ())
    if not isinstance(payload, dict):
        return ExternalProofPlanValidation(checks, ("External proof plan JSON must be an object",), ())
    checks += 1
    if payload.get("schema_version") != EXTERNAL_PROOF_PLAN_SCHEMA_VERSION:
        errors.append(f"External proof plan schema_version must be {EXTERNAL_PROOF_PLAN_SCHEMA_VERSION}")
    expected_payload = expected.to_dict()
    for key in ("status", "repo_root", "steps", "operator_boundaries"):
        checks += 1
        if payload.get(key) != expected_payload[key]:
            errors.append(f"External proof plan JSON field {key} does not match current proof gaps")
    if markdown_report_path:
        checks += 1
        try:
            markdown = markdown_report_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - validation returns data.
            errors.append(f"External proof plan Markdown is unreadable: {exc}")
        else:
            for fragment in required_markdown_fragments(expected):
                checks += 1
                if fragment not in markdown:
                    errors.append(f"External proof plan Markdown missing required text: {fragment}")
    return ExternalProofPlanValidation(checks, tuple(errors), tuple(warnings))


def required_markdown_fragments(expected: ExternalProofPlan) -> tuple[str, ...]:
    fragments = [
        "# External Proof Gap Plan",
        f"- Status: `{expected.status}`",
        "## Proof Steps",
        "## Operator Boundaries",
        "Do not claim external handoff readiness until both proof steps pass with approved evidence.",
        "This plan did not contact vCenter, Prism Central, Nutanix Move, AHV, or NC2.",
    ]
    for step in expected.steps:
        fragments.extend(
            [
                f"### {step.name}",
                f"- Status: `{step.status}`",
                f"- Evidence IDs: `{', '.join(step.evidence_ids)}`",
                step.current_gap,
            ]
        )
        fragments.extend(step.closeout_commands)
        fragments.extend(f"- {condition}" for condition in step.stop_conditions)
    return tuple(fragments)


def operator_boundaries() -> tuple[str, ...]:
    return (
        "This plan did not contact vCenter, Prism Central, Nutanix Move, AHV, or NC2.",
        "This plan did not stage, commit, push, publish, open a pull request, or mutate infrastructure.",
        "Do not claim external handoff readiness until both proof steps pass with approved evidence.",
        "Keep credentials, endpoint values, tokens, FQDNs, IP addresses, usernames, and raw customer identifiers out of committed artifacts.",
    )
