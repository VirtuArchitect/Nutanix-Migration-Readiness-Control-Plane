from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .move_lab_proof import load_json_object
from .redaction import redact_value


REQUIRED_SECTIONS = (
    "# Move Lab Execution Runbook",
    "## Inputs",
    "## Required Environment",
    "## Pre-Run Gates",
    "## Stop Conditions",
    "## Validation Commands",
    "## Evidence To Capture",
    "## Workload Scope",
    "## Closeout",
)

REQUIRED_FRAGMENTS = (
    "non-production Nutanix Move appliance",
    "NMRCP_MOVE_LAB_ACK",
    "I_UNDERSTAND_LAB_ONLY",
    "dry_run_only=true",
    "mutation_allowed=false",
    "start_immediately=false",
    "validate-move-submit-readiness",
    "validate-move-lab-transcript",
    "generate-approved-move-lab-proof",
    "validate-move-lab-proof",
    "validate-move-lab-evidence-intake",
    "--transcript-validation",
    "--capture-kit-validation",
    "Move lab evidence intake JSON with `status=pass`",
    "mvp-audit --move-proof --move-lab-evidence-intake",
    "created_plans=0",
    "started_migrations=0",
    "redacted",
)


@dataclass(frozen=True)
class MoveLabRunbookValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def write_move_lab_runbook(
    payload_path: Path,
    review_path: Path,
    out_path: Path,
    *,
    proof_template_path: Path | None = None,
) -> Path:
    payload = load_json_object(payload_path, "Move payload")
    review = load_json_object(review_path, "Move submit review")
    proof_template = load_json_object(proof_template_path, "Move lab proof template") if proof_template_path else None

    workloads = payload.get("workloads") if isinstance(payload.get("workloads"), list) else []
    network_mappings = payload.get("network_mappings") if isinstance(payload.get("network_mappings"), list) else []
    schedule = payload.get("schedule") if isinstance(payload.get("schedule"), dict) else {}
    approvals = review.get("approvals") if isinstance(review.get("approvals"), dict) else {}

    lines = [
        "# Move Lab Execution Runbook",
        "",
        "This runbook is generated from the dry-run Move payload and lab review record.",
        "It is for non-production Nutanix Move appliance proof only.",
        "",
        "## Inputs",
        "",
        f"- Dry-run payload: `{payload_path.name}`",
        f"- Submit review: `{review_path.name}`",
        f"- Proof template: `{proof_template_path.name if proof_template_path else 'not provided'}`",
        f"- Payload contract: `{payload.get('contract', 'missing')}`",
        f"- Workloads in scope: `{len(workloads)}`",
        f"- Network mappings: `{len(network_mappings)}`",
        f"- Schedule mode: `{redacted(schedule.get('mode', 'missing'))}`",
        f"- Start immediately: `{str(schedule.get('start_immediately', 'missing')).lower()}`",
        "- Lab Move appliance: `[REDACTED_LAB_MOVE_APPLIANCE]`",
        "",
        "## Required Environment",
        "",
        "```powershell",
        '$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"',
        "```",
        "",
        "Do not set this variable outside an approved lab window.",
        "",
        "## Pre-Run Gates",
        "",
        "- Confirm the target is a non-production Nutanix Move appliance.",
        "- Confirm no production vCenter, Prism Central, subnet, or workload target is in scope.",
        "- Confirm `dry_run_only=true` and `mutation_allowed=false` in the payload.",
        "- Confirm `start_immediately=false` in the payload schedule.",
        "- Confirm all submit-review approvals are true.",
        "- Confirm the proof template is blank for real appliance results before the lab run.",
        "- Confirm screenshots, logs, and API responses are redacted before saving evidence.",
        "",
        "## Stop Conditions",
        "",
        "- Stop if any endpoint, target, or workload is production.",
        "- Stop if Nutanix Move proposes to start a migration immediately.",
        "- Stop if the payload cannot be submitted as dry-run-only lab evidence.",
        "- Stop if provider, cluster, container, or network mapping values differ from the reviewed payload.",
        "- Stop if the operator cannot capture redacted evidence without credentials, endpoints, IPs, or hostnames.",
        "- Stop if any required review or proof approval is missing.",
        "",
        "## Validation Commands",
        "",
        "```powershell",
        "python -m nmrcp.cli validate-move-submit-readiness `",
        f"  --payload {payload_path.name} `",
        f"  --review {review_path.name} `",
        "  --out outputs\\move-submit-readiness.json",
        "",
        "python -m nmrcp.cli validate-move-lab-transcript `",
        "  --transcript outputs\\move-lab-transcript.approved.json `",
        f"  --payload {payload_path.name} `",
        f"  --review {review_path.name} `",
        "  --out outputs\\move-lab-transcript-validation.json",
        "",
        "python -m nmrcp.cli generate-approved-move-lab-proof `",
        "  --transcript outputs\\move-lab-transcript.approved.json `",
        "  --transcript-validation outputs\\move-lab-transcript-validation.json `",
        f"  --payload {payload_path.name} `",
        f"  --review {review_path.name} `",
        "  --approved-by \"[LAB_APPROVER]\" `",
        "  --out outputs\\move-lab-proof.approved.json",
        "",
        "python -m nmrcp.cli validate-move-lab-proof `",
        "  --proof outputs\\move-lab-proof.approved.json `",
        f"  --payload {payload_path.name} `",
        f"  --review {review_path.name} `",
        "  --transcript-validation outputs\\move-lab-transcript-validation.json `",
        "  --out outputs\\move-lab-proof-validation.json",
        "",
        "python -m nmrcp.cli validate-move-lab-evidence-intake `",
        f"  --payload {payload_path.name} `",
        f"  --review {review_path.name} `",
        "  --transcript outputs\\move-lab-transcript.approved.json `",
        "  --transcript-validation outputs\\move-lab-transcript-validation.json `",
        "  --proof outputs\\move-lab-proof.approved.json `",
        "  --proof-validation outputs\\move-lab-proof-validation.json `",
        "  --capture-kit-validation outputs\\move-lab-capture-kit-validation.json `",
        "  --out outputs\\move-lab-evidence-intake.json",
        "```",
        "",
        "## Evidence To Capture",
        "",
        "- Move submit-readiness JSON.",
        "- Move lab transcript validation JSON with `status=pass`.",
        "- Completed Move lab proof JSON with `proof_scope=approved_lab_move_appliance`.",
        "- `transcript_validation_sha256` in the proof JSON matching the transcript validation file.",
        "- Move lab proof validation JSON with `status=pass`.",
        "- Move lab evidence intake JSON with `status=pass`.",
        "- Redacted operator notes for accepted payload count and created plan count.",
        "- Confirmation that `created_plans=0` and `started_migrations=0` for MVP proof.",
        "",
        "## Workload Scope",
        "",
        "| VM ID | Wave | Target | Readiness | Risk | Dependency Count |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for workload in workloads:
        lines.append(
            "| "
            + " | ".join(
                [
                    redacted(workload.get("source_vm_id", "")),
                    redacted(workload.get("wave", "")),
                    redacted(workload.get("target", "")),
                    redacted(workload.get("readiness", "")),
                    redacted(workload.get("risk_score", "")),
                    redacted(workload.get("dependency_count", "")),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Review Approvals",
            "",
            "| Approval | Status |",
            "| --- | --- |",
        ]
    )
    for name in sorted(approvals):
        lines.append(f"| `{name}` | `{str(approvals.get(name)).lower()}` |")

    if proof_template:
        proof_scope = redacted(proof_template.get("proof_scope", "missing"))
        accepted_payloads = ((proof_template.get("results") or {}) if isinstance(proof_template.get("results"), dict) else {}).get("accepted_payloads", "missing")
        lines.extend(
            [
                "",
                "## Proof Template State",
                "",
                f"- Proof scope: `{proof_scope}`",
                f"- Accepted payloads before lab evidence: `{accepted_payloads}`",
                "- Keep approved-lab templates unproven until the real lab API round trip is complete.",
            ]
        )

    lines.extend(
        [
            "",
            "## Closeout",
            "",
            "1. Run `validate-move-lab-transcript` against redacted transcript evidence.",
            "2. Run `generate-approved-move-lab-proof` so transcript hashes, accepted payload counts, and approval metadata are machine-derived.",
            "3. Run `validate-move-lab-proof` against the generated proof JSON and transcript validation file.",
            "4. Run `validate-move-lab-evidence-intake` so the transcript, proof validation, and capture-kit validation are tied together.",
            "5. Run `mvp-audit --move-proof --move-lab-evidence-intake` only after proof validation has approved lab scope and evidence intake has `status=pass`.",
            "6. Run `scripts\\move_lab_proof_workflow.ps1 -GenerateApprovedProof` to package the verified MVP proof bundle.",
            "7. Remove `NMRCP_MOVE_LAB_ACK` from the shell after the lab window.",
            "",
        ]
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def validate_move_lab_runbook(path: Path) -> MoveLabRunbookValidation:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return MoveLabRunbookValidation("fail", 1, (f"{path}: could not read Move lab execution runbook: {exc}",), ())

    errors: list[str] = []
    checks = 0
    for section in REQUIRED_SECTIONS:
        checks += 1
        if section not in text:
            errors.append(f"Move lab execution runbook missing required section: {section}")

    for fragment in REQUIRED_FRAGMENTS:
        checks += 1
        if fragment not in text:
            errors.append(f"Move lab execution runbook missing required proof-chain reference: {fragment}")

    checks += 1
    if "production" not in text.lower():
        errors.append("Move lab execution runbook must include production stop conditions")

    checks += 1
    if "redact" not in text.lower() and "redacted" not in text.lower():
        errors.append("Move lab execution runbook must include redaction controls")

    checks += 1
    if "credential" not in text.lower() and "secret" not in text.lower():
        errors.append("Move lab execution runbook must include credential or secret handling controls")

    return MoveLabRunbookValidation("pass" if not errors else "fail", checks, tuple(errors), ())


def redacted(value: Any) -> str:
    text = str(redact_value(value))
    return text.replace("|", "\\|").replace("\n", " ").strip() or "missing"
