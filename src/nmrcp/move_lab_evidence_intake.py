from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any

from .move_lab_capture_kit import validate_move_lab_capture_kit_validation_file
from .move_lab_proof import validate_move_lab_proof, validate_move_lab_proof_validation_file
from .move_lab_transcript import validate_move_lab_transcript, validate_move_lab_transcript_validation_file
from .move_submit_readiness import validate_move_submit_readiness


MOVE_LAB_EVIDENCE_INTAKE_SCHEMA_VERSION = "nmrcp_move_lab_evidence_intake_v1"
MOVE_LAB_EVIDENCE_PREFLIGHT_SCHEMA_VERSION = "nmrcp_move_lab_evidence_preflight_v1"


@dataclass(frozen=True)
class MoveLabEvidenceIntakeValidation:
    status: str
    checks: tuple[dict[str, str], ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={len(self.checks)}, errors={len(self.errors)}, warnings={len(self.warnings)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MOVE_LAB_EVIDENCE_INTAKE_SCHEMA_VERSION,
            "status": self.status,
            "checks": list(self.checks),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True)
class MoveLabEvidencePreflight:
    status: str
    checks: tuple[dict[str, str], ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    required_artifacts: tuple[dict[str, str], ...]
    commands: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return (
            f"{self.status.upper()}: checks={len(self.checks)}, "
            f"artifacts={len(self.required_artifacts)}, errors={len(self.errors)}, warnings={len(self.warnings)}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MOVE_LAB_EVIDENCE_PREFLIGHT_SCHEMA_VERSION,
            "status": self.status,
            "checks": list(self.checks),
            "required_artifacts": list(self.required_artifacts),
            "commands": list(self.commands),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Move Lab Evidence Preflight",
            "",
            f"- Status: `{self.status}`",
            f"- Checks: `{len(self.checks)}`",
            f"- Required artifacts: `{len(self.required_artifacts)}`",
            f"- Errors: `{len(self.errors)}`",
            f"- Warnings: `{len(self.warnings)}`",
            "",
            "## Required Artifacts",
            "",
            "| Role | Path | State |",
            "| --- | --- | --- |",
        ]
        for artifact in self.required_artifacts:
            lines.append(f"| `{artifact['role']}` | `{artifact['path']}` | `{artifact['state']}` |")
        lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
        for check in self.checks:
            lines.append(f"| `{check['name']}` | `{check['status']}` | {escape_markdown_cell(check['detail'])} |")
        if self.commands:
            lines.extend(["", "## Commands", ""])
            for command in self.commands:
                lines.extend(["```powershell", command, "```", ""])
        if self.warnings:
            lines.extend(["## Warnings", ""])
            lines.extend(f"- {warning}" for warning in self.warnings)
            lines.append("")
        if self.errors:
            lines.extend(["## Errors", ""])
            lines.extend(f"- {error}" for error in self.errors)
            lines.append("")
        return "\n".join(lines).rstrip() + "\n"


def validate_move_lab_evidence_preflight(
    payload_path: Path,
    review_path: Path,
    capture_kit_validation_path: Path,
    transcript_path: Path,
    transcript_validation_path: Path,
    proof_path: Path,
    proof_validation_path: Path,
    evidence_intake_path: Path,
    *,
    lab_ack_env: str = "NMRCP_MOVE_LAB_ACK",
) -> MoveLabEvidencePreflight:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    readiness = validate_move_submit_readiness(payload_path, review_path, lab_ack_env=lab_ack_env)
    add_result(checks, errors, warnings, "move-submit-readiness", readiness)

    capture_kit = validate_move_lab_capture_kit_validation_file(capture_kit_validation_path)
    add_result(checks, errors, warnings, "move-lab-capture-kit-validation", capture_kit, fail_on_warning=True)

    required_artifacts = (
        artifact_state("payload", payload_path, must_exist=True),
        artifact_state("review", review_path, must_exist=True),
        artifact_state("capture_kit_validation", capture_kit_validation_path, must_exist=True),
        artifact_state("approved_transcript", transcript_path, must_exist=False),
        artifact_state("transcript_validation", transcript_validation_path, must_exist=False),
        artifact_state("approved_proof", proof_path, must_exist=False),
        artifact_state("proof_validation", proof_validation_path, must_exist=False),
        artifact_state("evidence_intake", evidence_intake_path, must_exist=False),
    )
    for artifact in required_artifacts:
        add_check(
            checks,
            f"artifact-{artifact['role']}",
            artifact["state"] in {"present", "planned"},
            f"{artifact['state']}: {artifact['path']}",
        )
        if artifact["state"] == "missing":
            errors.append(f"Required preflight artifact is missing: {artifact['role']} at {artifact['path']}")

    validate_planned_artifact_paths(
        transcript_path,
        transcript_validation_path,
        proof_path,
        proof_validation_path,
        evidence_intake_path,
        checks,
        errors,
        warnings,
    )
    validate_capture_validation_checks(capture_kit_validation_path, checks, errors)

    commands = (
        command_line(
            "python -m nmrcp.cli validate-move-lab-transcript",
            {
                "--transcript": transcript_path,
                "--payload": payload_path,
                "--review": review_path,
                "--out": transcript_validation_path,
            },
        ),
        command_line(
            "python -m nmrcp.cli generate-approved-move-lab-proof",
            {
                "--transcript": transcript_path,
                "--transcript-validation": transcript_validation_path,
                "--payload": payload_path,
                "--review": review_path,
                "--approved-by": "[LAB_APPROVER]",
                "--out": proof_path,
            },
        ),
        command_line(
            "python -m nmrcp.cli validate-move-lab-proof",
            {
                "--proof": proof_path,
                "--payload": payload_path,
                "--review": review_path,
                "--transcript-validation": transcript_validation_path,
                "--out": proof_validation_path,
            },
        ),
        command_line(
            "python -m nmrcp.cli validate-move-lab-evidence-intake",
            {
                "--payload": payload_path,
                "--review": review_path,
                "--transcript": transcript_path,
                "--transcript-validation": transcript_validation_path,
                "--proof": proof_path,
                "--proof-validation": proof_validation_path,
                "--capture-kit-validation": capture_kit_validation_path,
                "--out": evidence_intake_path,
            },
        ),
    )
    status = "fail" if errors else "warn" if warnings else "pass"
    return MoveLabEvidencePreflight(status, tuple(checks), tuple(errors), tuple(warnings), required_artifacts, commands)


def validate_move_lab_evidence_intake(
    payload_path: Path,
    review_path: Path,
    transcript_path: Path,
    transcript_validation_path: Path,
    proof_path: Path,
    proof_validation_path: Path,
    *,
    capture_kit_validation_path: Path | None = None,
    lab_ack_env: str = "NMRCP_MOVE_LAB_ACK",
) -> MoveLabEvidenceIntakeValidation:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    readiness = validate_move_submit_readiness(payload_path, review_path, lab_ack_env=lab_ack_env)
    add_result(checks, errors, warnings, "move-submit-readiness", readiness)

    transcript = validate_move_lab_transcript(transcript_path, payload_path, review_path, lab_ack_env=lab_ack_env)
    add_result(checks, errors, warnings, "move-lab-transcript", transcript, fail_on_warning=True)

    transcript_validation = validate_move_lab_transcript_validation_file(transcript_validation_path)
    add_result(checks, errors, warnings, "move-lab-transcript-validation", transcript_validation, fail_on_warning=True)

    proof = validate_move_lab_proof(
        proof_path,
        payload_path,
        review_path,
        transcript_validation_path=transcript_validation_path,
        lab_ack_env=lab_ack_env,
    )
    add_result(checks, errors, warnings, "move-lab-proof", proof, fail_on_warning=True)

    proof_validation = validate_move_lab_proof_validation_file(proof_validation_path, require_approved_lab=True)
    add_result(checks, errors, warnings, "move-lab-proof-validation", proof_validation, fail_on_warning=True)

    if capture_kit_validation_path:
        capture_kit = validate_move_lab_capture_kit_validation_file(capture_kit_validation_path)
        add_result(checks, errors, warnings, "move-lab-capture-kit-validation", capture_kit, fail_on_warning=True)
    else:
        add_check(checks, "move-lab-capture-kit-validation", False, "not provided")
        errors.append("Move lab capture kit validation is required for final evidence intake")

    status = "fail" if errors else "warn" if warnings else "pass"
    return MoveLabEvidenceIntakeValidation(status, tuple(checks), tuple(errors), tuple(warnings))


def validate_move_lab_evidence_intake_validation_file(path: Path) -> MoveLabEvidenceIntakeValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks: list[dict[str, str]] = []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        return MoveLabEvidenceIntakeValidation("fail", (), (f"unable to read evidence intake validation: {exc}",), ())
    except json.JSONDecodeError as exc:
        return MoveLabEvidenceIntakeValidation("fail", (), (f"invalid evidence intake validation JSON: {exc}",), ())

    if payload.get("schema_version") != MOVE_LAB_EVIDENCE_INTAKE_SCHEMA_VERSION:
        errors.append(f"schema_version must be {MOVE_LAB_EVIDENCE_INTAKE_SCHEMA_VERSION}")
    if payload.get("status") != "pass":
        errors.append("status must be pass")

    payload_errors = payload.get("errors")
    if isinstance(payload_errors, list):
        errors.extend(str(error) for error in payload_errors)
    else:
        errors.append("errors must be a list")

    payload_warnings = payload.get("warnings")
    if isinstance(payload_warnings, list):
        warnings.extend(str(warning) for warning in payload_warnings)
    else:
        errors.append("warnings must be a list")

    payload_checks = payload.get("checks")
    if isinstance(payload_checks, list):
        checks = [check for check in payload_checks if isinstance(check, dict)]
    else:
        errors.append("checks must be a list")

    status = "fail" if errors else "warn" if warnings else "pass"
    return MoveLabEvidenceIntakeValidation(status, tuple(checks), tuple(errors), tuple(warnings))


def add_result(
    checks: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
    name: str,
    result: Any,
    *,
    fail_on_warning: bool = False,
) -> None:
    add_check(checks, name, result.ok and not (fail_on_warning and result.warnings), result.summary())
    errors.extend(f"{name}: {error}" for error in result.errors)
    if fail_on_warning and result.warnings:
        errors.extend(f"{name}: warning must be resolved for final evidence intake: {warning}" for warning in result.warnings)
    else:
        warnings.extend(f"{name}: {warning}" for warning in result.warnings)


def add_check(checks: list[dict[str, str]], name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})


def artifact_state(role: str, path: Path, *, must_exist: bool) -> dict[str, str]:
    if path.exists():
        state = "present"
    elif must_exist:
        state = "missing"
    else:
        state = "planned"
    return {"role": role, "path": str(path), "state": state}


def validate_planned_artifact_paths(
    transcript_path: Path,
    transcript_validation_path: Path,
    proof_path: Path,
    proof_validation_path: Path,
    evidence_intake_path: Path,
    checks: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> None:
    planned = {
        "approved_transcript": transcript_path,
        "transcript_validation": transcript_validation_path,
        "approved_proof": proof_path,
        "proof_validation": proof_validation_path,
        "evidence_intake": evidence_intake_path,
    }
    unique_paths = {str(path.resolve()).lower() for path in planned.values()}
    add_check(checks, "planned-artifact-paths-unique", len(unique_paths) == len(planned), f"unique={len(unique_paths)}")
    if len(unique_paths) != len(planned):
        errors.append("Planned Move lab evidence artifact paths must be unique")

    for role, path in planned.items():
        suffix_ok = path.suffix.lower() == ".json"
        add_check(checks, f"{role}-json-suffix", suffix_ok, path.name)
        if not suffix_ok:
            errors.append(f"{role} path must end in .json: {path}")

    transcript_name = transcript_path.name.lower()
    transcript_name_ok = "approved" in transcript_name and "template" not in transcript_name
    add_check(checks, "approved-transcript-path-name", transcript_name_ok, transcript_path.name)
    if not transcript_name_ok:
        errors.append("Approved transcript path must be a copied approved evidence file, not the template")

    if "approved" not in proof_path.name.lower():
        warnings.append("Approved proof path name should include 'approved' for operator clarity")

    if evidence_intake_path.exists():
        warnings.append("Evidence intake output already exists; review before overwriting or packaging")


def validate_capture_validation_checks(
    capture_kit_validation_path: Path,
    checks: list[dict[str, str]],
    errors: list[str],
) -> None:
    required = {
        "move-lab-capture-template-payload-hash": "sha256 matched",
        "move-lab-capture-attestation-payload-hash": "sha256 matched",
        "move-lab-capture-template-state": "template_only_replace_after_lab_capture",
        "move-lab-capture-checklist-text-validate-move-lab-evidence-intake": "validate-move-lab-evidence-intake",
    }
    try:
        payload = json.loads(capture_kit_validation_path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        errors.append(f"Unable to inspect capture kit validation checks: {exc}")
        payload = {}
    except json.JSONDecodeError as exc:
        errors.append(f"Capture kit validation JSON is unreadable for preflight linkage checks: {exc}")
        payload = {}
    raw_checks = payload.get("checks") if isinstance(payload, dict) else []
    capture_checks = [check for check in raw_checks if isinstance(check, dict)] if isinstance(raw_checks, list) else []
    by_name = {str(check.get("name")): check for check in capture_checks}
    for name, expected_detail in required.items():
        check = by_name.get(name)
        ok = isinstance(check, dict) and check.get("status") == "pass" and expected_detail in str(check.get("detail") or "")
        add_check(checks, f"capture-validation-{name}", ok, str(check.get("detail") if isinstance(check, dict) else "missing"))
        if not ok:
            errors.append(f"Move lab capture kit validation missing passing {name}")


def command_line(command: str, args: dict[str, Path]) -> str:
    lines = [f"{command} `"]
    items = list(args.items())
    for index, (name, path) in enumerate(items):
        suffix = " `" if index < len(items) - 1 else ""
        lines.append(f"  {name} {path}{suffix}")
    return "\n".join(lines)


def escape_markdown_cell(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()
