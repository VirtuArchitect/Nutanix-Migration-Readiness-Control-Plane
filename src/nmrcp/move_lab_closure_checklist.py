from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


REQUIRED_SECTIONS = (
    "# Move Lab Closure Checklist",
    "## Purpose",
    "## Required Proof Chain",
    "## Required Commands",
    "## Change Gate Closeout",
    "## Stop Conditions",
)

REQUIRED_FRAGMENTS = (
    "`nmrcp_move_submit_readiness_v1`",
    "`nmrcp_move_lab_transcript_validation_v1`",
    "`nmrcp_move_lab_proof_validation_v1`",
    "`proof_scope=approved_lab_move_appliance`",
    "`nmrcp_move_lab_evidence_intake_v1`",
    "validate-move-lab-evidence-intake",
    "summarize-gates",
    "change-gate",
    "mvp-audit",
    "package-handoff",
    "--move-proof",
    "--move-lab-evidence-intake",
    "--dir outputs\\sample-assessment",
    "--out outputs\\mvp-audit.json",
)

DISALLOWED_FRAGMENTS = (
    "summarize-gates `\n  --assessment-dir",
    "change-gate `\n  --assessment-dir",
    "package-handoff `\n  --assessment-dir",
    "--json-out outputs\\mvp-audit.json",
)


@dataclass(frozen=True)
class MoveLabClosureChecklistValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def write_move_lab_closure_checklist(path: Path) -> Path:
    lines = [
        "# Move Lab Closure Checklist",
        "",
        "## Purpose",
        "",
        "Use this checklist before external handoff to close the remaining approved Nutanix Move lab proof gap.",
        "It is generated with every assessment so the final proof chain is visible before operators enter a lab window.",
        "",
        "## Required Proof Chain",
        "",
        "| Step | Evidence | Required State |",
        "| --- | --- | --- |",
        "| 1 | `nmrcp_move_submit_readiness_v1` | `status=pass`; reviewed dry-run payload accepted for lab proof. |",
        "| 2 | Move lab capture kit validation | `nmrcp_move_lab_capture_kit_validation_v1` with `status=pass`. |",
        "| 3 | Move lab transcript validation | `nmrcp_move_lab_transcript_validation_v1` with `status=pass`. |",
        "| 4 | Move lab proof validation | `nmrcp_move_lab_proof_validation_v1` with `status=pass` and `proof_scope=approved_lab_move_appliance`. |",
        "| 5 | Move lab evidence intake | `nmrcp_move_lab_evidence_intake_v1` with `status=pass`. |",
        "| 6 | MVP audit | `ready_for_external_handoff=false` only until approved proof and intake are supplied. |",
        "",
        "## Required Commands",
        "",
        "Run these from the repository root with `PYTHONPATH=src` and an approved non-production lab window:",
        "",
        "```powershell",
        '$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"',
        "python -m nmrcp.cli validate-move-submit-readiness `",
        "  --payload outputs\\sample-assessment\\move-api-payload.lab.dry-run.json `",
        "  --review examples\\sample_move_submit_review.json `",
        "  --out outputs\\move-submit-readiness.json",
        "",
        "python -m nmrcp.cli validate-move-lab-transcript `",
        "  --transcript outputs\\move-lab-capture-kit\\move-lab-transcript.approved.json `",
        "  --payload outputs\\sample-assessment\\move-api-payload.lab.dry-run.json `",
        "  --review examples\\sample_move_submit_review.json `",
        "  --out outputs\\move-lab-transcript-validation.json",
        "",
        "python -m nmrcp.cli validate-move-lab-proof `",
        "  --proof outputs\\move-lab-proof.approved.json `",
        "  --payload outputs\\sample-assessment\\move-api-payload.lab.dry-run.json `",
        "  --review examples\\sample_move_submit_review.json `",
        "  --transcript-validation outputs\\move-lab-transcript-validation.json `",
        "  --out outputs\\move-lab-proof-validation.json",
        "",
        "python -m nmrcp.cli validate-move-lab-evidence-intake `",
        "  --payload outputs\\sample-assessment\\move-api-payload.lab.dry-run.json `",
        "  --review examples\\sample_move_submit_review.json `",
        "  --transcript outputs\\move-lab-capture-kit\\move-lab-transcript.approved.json `",
        "  --transcript-validation outputs\\move-lab-transcript-validation.json `",
        "  --proof outputs\\move-lab-proof.approved.json `",
        "  --proof-validation outputs\\move-lab-proof-validation.json `",
        "  --capture-kit-validation outputs\\move-lab-capture-kit-validation.json `",
        "  --out outputs\\move-lab-evidence-intake.json",
        "Remove-Item Env:\\NMRCP_MOVE_LAB_ACK",
        "```",
        "",
        "## Change Gate Closeout",
        "",
        "After the proof chain passes, rerun the final gates with both approved-proof files:",
        "",
        "```powershell",
        "python -m nmrcp.cli summarize-gates `",
        "  --dir outputs\\sample-assessment `",
        "  --move-lab-proof outputs\\move-lab-proof-validation.json `",
        "  --move-lab-evidence-intake outputs\\move-lab-evidence-intake.json",
        "",
        "python -m nmrcp.cli change-gate `",
        "  --dir outputs\\sample-assessment `",
        "  --move-lab-proof outputs\\move-lab-proof-validation.json `",
        "  --move-lab-evidence-intake outputs\\move-lab-evidence-intake.json",
        "",
        "python -m nmrcp.cli mvp-audit `",
        "  --repo-root . `",
        "  --assessment-dir outputs\\sample-assessment `",
        "  --move-proof outputs\\move-lab-proof-validation.json `",
        "  --move-lab-evidence-intake outputs\\move-lab-evidence-intake.json `",
        "  --out outputs\\mvp-audit.json",
        "",
        "python -m nmrcp.cli package-handoff `",
        "  --dir outputs\\sample-assessment `",
        "  --move-lab-proof outputs\\move-lab-proof-validation.json `",
        "  --move-lab-evidence-intake outputs\\move-lab-evidence-intake.json `",
        "  --out outputs\\sample-assessment-handoff-package.zip",
        "```",
        "",
        "## Stop Conditions",
        "",
        "- Stop if any endpoint, workload, or target is production.",
        "- Stop if any evidence file includes credentials, tokens, IP addresses, FQDNs, or unredacted customer identifiers.",
        "- Stop if approved proof validation is not `status=pass` with `proof_scope=approved_lab_move_appliance`.",
        "- Stop if `validate-move-lab-evidence-intake` does not return `status=pass`.",
        "- Stop if `summarize-gates`, `change-gate`, or `mvp-audit` is run with `--move-proof` but without `--move-lab-evidence-intake`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def validate_move_lab_closure_checklist(path: Path) -> MoveLabClosureChecklistValidation:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return MoveLabClosureChecklistValidation("fail", 1, (f"{path}: could not read Move lab closure checklist: {exc}",), ())

    errors: list[str] = []
    checks = 0
    for section in REQUIRED_SECTIONS:
        checks += 1
        if section not in text:
            errors.append(f"Move lab closure checklist missing required section: {section}")

    for fragment in REQUIRED_FRAGMENTS:
        checks += 1
        if fragment not in text:
            errors.append(f"Move lab closure checklist missing required proof-chain reference: {fragment}")

    for fragment in DISALLOWED_FRAGMENTS:
        checks += 1
        if fragment in text:
            errors.append(f"Move lab closure checklist contains stale CLI flag: {fragment}")

    checks += 1
    if "production" not in text.lower():
        errors.append("Move lab closure checklist must include production stop conditions")

    checks += 1
    if "redact" not in text.lower() and "redacted" not in text.lower():
        errors.append("Move lab closure checklist must include redaction stop conditions")

    return MoveLabClosureChecklistValidation("pass" if not errors else "fail", checks, tuple(errors), ())
