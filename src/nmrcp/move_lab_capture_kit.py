from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .move_lab_transcript import APPROVED_LAB_SCOPE, MOVE_LAB_TRANSCRIPT_SCHEMA_VERSION
from .move_submit_readiness import validate_move_submit_readiness
from .redaction import redact_value
from .redaction_review import scan_text


MOVE_LAB_CAPTURE_KIT_VALIDATION_SCHEMA_VERSION = "nmrcp_move_lab_capture_kit_validation_v1"
TEMPLATE_EVIDENCE_STATE = "template_only_replace_after_lab_capture"


@dataclass(frozen=True)
class MoveLabCaptureKit:
    out_dir: Path
    transcript_template_path: Path
    checklist_path: Path

    def to_dict(self) -> dict[str, str]:
        return {
            "out_dir": str(self.out_dir),
            "transcript_template": str(self.transcript_template_path),
            "checklist": str(self.checklist_path),
        }


@dataclass(frozen=True)
class MoveLabCaptureKitValidation:
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
            "schema_version": MOVE_LAB_CAPTURE_KIT_VALIDATION_SCHEMA_VERSION,
            "status": self.status,
            "checks": list(self.checks),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def write_move_lab_capture_kit(
    payload_path: Path,
    review_path: Path,
    out_dir: Path,
    *,
    lab_ack_env: str = "NMRCP_MOVE_LAB_ACK",
) -> MoveLabCaptureKit:
    readiness = validate_move_submit_readiness(payload_path, review_path, lab_ack_env=lab_ack_env)
    if not readiness.ok:
        raise ValueError("Move submit readiness must pass before generating a lab capture kit: " + "; ".join(readiness.errors))

    payload = read_json_object(payload_path, "Move payload")
    review = read_json_object(review_path, "Move submit review")
    workloads = payload.get("workloads") if isinstance(payload.get("workloads"), list) else []
    network_mappings = payload.get("network_mappings") if isinstance(payload.get("network_mappings"), list) else []

    out_dir.mkdir(parents=True, exist_ok=True)
    transcript_template_path = out_dir / "move-lab-transcript.template.json"
    checklist_path = out_dir / "move-lab-capture-checklist.md"
    payload_sha256 = file_sha256(payload_path)

    template = {
        "schema_version": MOVE_LAB_TRANSCRIPT_SCHEMA_VERSION,
        "proof_scope": APPROVED_LAB_SCOPE,
        "evidence_state": TEMPLATE_EVIDENCE_STATE,
        "environment": "lab",
        "lab_move_appliance": "[REDACTED_LAB_MOVE_APPLIANCE]",
        "payload_sha256": payload_sha256,
        "dry_run_only": True,
        "mutation_performed": False,
        "production_targets": False,
        "interactions": [
            {
                "name": "create-reviewed-dry-run-plan",
                "method": "POST",
                "path": "/api/move/[REDACTED_RELATIVE_DRY_RUN_PLAN_PATH]",
                "status_code": 0,
                "dry_run": True,
                "mutating": False,
                "redacted": True,
                "request_sha256": "[OPTIONAL_SHA256_OF_REDACTED_REQUEST]",
                "response_sha256": "[OPTIONAL_SHA256_OF_REDACTED_RESPONSE]",
                "operator_note": "Replace status_code, path, and hashes with redacted values captured from the approved lab appliance.",
            }
        ],
        "results": {
            "accepted_payloads": 0,
            "created_plans": 0,
            "started_migrations": 0,
        },
        "operator_attestation": {
            "approved_lab_window": False,
            "reviewed_payload_sha256": payload_sha256,
            "no_production_targets": True,
            "no_started_migrations": True,
        },
    }

    transcript_template_path.write_text(json.dumps(template, indent=2), encoding="utf-8")
    checklist_path.write_text(
        "\n".join(checklist_lines(payload_path, review_path, payload, review, len(workloads), len(network_mappings))),
        encoding="utf-8",
    )
    return MoveLabCaptureKit(out_dir, transcript_template_path, checklist_path)


def validate_move_lab_capture_kit(capture_kit_dir: Path, payload_path: Path) -> MoveLabCaptureKitValidation:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    template_path = capture_kit_dir / "move-lab-transcript.template.json"
    checklist_path = capture_kit_dir / "move-lab-capture-checklist.md"

    template_exists = template_path.exists()
    checklist_exists = checklist_path.exists()
    add_check(checks, "move-lab-capture-template-present", template_exists, template_path.name)
    add_check(checks, "move-lab-capture-checklist-present", checklist_exists, checklist_path.name)
    if not template_exists:
        errors.append(f"Move lab capture kit missing transcript template: {template_path}")
    if not checklist_exists:
        errors.append(f"Move lab capture kit missing checklist: {checklist_path}")

    payload_exists = payload_path.exists()
    add_check(checks, "move-lab-capture-payload-present", payload_exists, payload_path.name)
    if not payload_exists:
        errors.append(f"Move lab capture kit payload is missing: {payload_path}")

    template = read_json_object_for_validation(template_path, "Move lab capture transcript template", errors) if template_exists else None
    checklist = read_text_for_validation(checklist_path, "Move lab capture checklist", errors) if checklist_exists else ""

    if template_path.exists():
        template_text = template_path.read_text(encoding="utf-8-sig")
        findings = scan_text(template_path.name, template_text)
        add_check(checks, "move-lab-capture-template-redaction", not findings, f"findings={len(findings)}")
        errors.extend(f"Move lab capture template leak: {finding}" for finding in findings)
    if checklist:
        findings = scan_text(checklist_path.name, checklist)
        add_check(checks, "move-lab-capture-checklist-redaction", not findings, f"findings={len(findings)}")
        errors.extend(f"Move lab capture checklist leak: {finding}" for finding in findings)

    if template is not None:
        validate_template(template, payload_path, payload_exists, checks, errors)
    if checklist:
        validate_checklist(checklist, checks, errors)

    status = "fail" if errors else "warn" if warnings else "pass"
    return MoveLabCaptureKitValidation(status, tuple(checks), tuple(errors), tuple(warnings))


def validate_move_lab_capture_kit_validation_file(validation_path: Path) -> MoveLabCaptureKitValidation:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []
    payload = read_json_object_for_validation(validation_path, "Move lab capture kit validation", errors)
    if payload is not None:
        findings = scan_text(validation_path.name, validation_path.read_text(encoding="utf-8-sig"))
        add_check(checks, "move-lab-capture-validation-redaction", not findings, f"findings={len(findings)}")
        errors.extend(f"Move lab capture kit validation leak: {finding}" for finding in findings)

        schema_ok = payload.get("schema_version") == MOVE_LAB_CAPTURE_KIT_VALIDATION_SCHEMA_VERSION
        add_check(checks, "move-lab-capture-validation-schema", schema_ok, str(payload.get("schema_version") or "missing"))
        if not schema_ok:
            errors.append(f"Move lab capture kit validation schema_version must be {MOVE_LAB_CAPTURE_KIT_VALIDATION_SCHEMA_VERSION}")

        status = str(payload.get("status") or "")
        status_ok = status == "pass"
        add_check(checks, "move-lab-capture-validation-status", status_ok, status or "missing")
        if not status_ok:
            errors.append("Move lab capture kit validation status must be pass")

        payload_errors = payload.get("errors")
        no_payload_errors = isinstance(payload_errors, list) and not payload_errors
        add_check(checks, "move-lab-capture-validation-errors", no_payload_errors, f"errors={len(payload_errors) if isinstance(payload_errors, list) else 'invalid'}")
        if not no_payload_errors:
            errors.append("Move lab capture kit validation must not contain errors")

        warnings.extend(str(warning) for warning in payload.get("warnings") or [])
    status = "fail" if errors else "warn" if warnings else "pass"
    return MoveLabCaptureKitValidation(status, tuple(checks), tuple(errors), tuple(warnings))


def validate_template(
    template: dict[str, Any],
    payload_path: Path,
    payload_exists: bool,
    checks: list[dict[str, str]],
    errors: list[str],
) -> None:
    schema_ok = template.get("schema_version") == MOVE_LAB_TRANSCRIPT_SCHEMA_VERSION
    add_check(checks, "move-lab-capture-template-schema", schema_ok, str(template.get("schema_version") or "missing"))
    if not schema_ok:
        errors.append(f"Move lab capture template schema_version must be {MOVE_LAB_TRANSCRIPT_SCHEMA_VERSION}")

    scope_ok = template.get("proof_scope") == APPROVED_LAB_SCOPE
    add_check(checks, "move-lab-capture-template-scope", scope_ok, str(template.get("proof_scope") or "missing"))
    if not scope_ok:
        errors.append("Move lab capture template must use approved_lab_move_appliance proof_scope")

    state_ok = template.get("evidence_state") == TEMPLATE_EVIDENCE_STATE
    add_check(checks, "move-lab-capture-template-state", state_ok, str(template.get("evidence_state") or "missing"))
    if not state_ok:
        errors.append(f"Move lab capture template evidence_state must remain {TEMPLATE_EVIDENCE_STATE}")

    lab_ok = str(template.get("environment") or "").strip().lower() == "lab"
    add_check(checks, "move-lab-capture-template-environment", lab_ok, str(template.get("environment") or "missing"))
    if not lab_ok:
        errors.append("Move lab capture template environment must be lab")

    dry_run_ok = template.get("dry_run_only") is True
    add_check(checks, "move-lab-capture-template-dry-run-only", dry_run_ok, str(template.get("dry_run_only")))
    if not dry_run_ok:
        errors.append("Move lab capture template must set dry_run_only=true")

    mutation_ok = template.get("mutation_performed") is False and template.get("production_targets") is False
    add_check(checks, "move-lab-capture-template-mutation-guard", mutation_ok, "mutation_performed=false; production_targets=false")
    if not mutation_ok:
        errors.append("Move lab capture template must set mutation_performed=false and production_targets=false")

    expected_hash = file_sha256(payload_path) if payload_exists else ""
    payload_hash = str(template.get("payload_sha256") or "").strip().lower()
    payload_hash_ok = bool(expected_hash) and payload_hash == expected_hash
    add_check(checks, "move-lab-capture-template-payload-hash", payload_hash_ok, "sha256 matched" if payload_hash_ok else "sha256 missing or mismatched")
    if not payload_hash_ok:
        errors.append("Move lab capture template payload_sha256 must match the reviewed dry-run payload")

    attestation = template.get("operator_attestation") if isinstance(template.get("operator_attestation"), dict) else {}
    attestation_hash = str(attestation.get("reviewed_payload_sha256") or "").strip().lower()
    attestation_hash_ok = bool(expected_hash) and attestation_hash == expected_hash
    add_check(checks, "move-lab-capture-attestation-payload-hash", attestation_hash_ok, "sha256 matched" if attestation_hash_ok else "sha256 missing or mismatched")
    if not attestation_hash_ok:
        errors.append("Move lab capture template operator_attestation.reviewed_payload_sha256 must match the reviewed dry-run payload")

    attestation_ok = (
        attestation.get("approved_lab_window") is False
        and attestation.get("no_production_targets") is True
        and attestation.get("no_started_migrations") is True
    )
    add_check(checks, "move-lab-capture-attestation-template-state", attestation_ok, "approved_lab_window=false; no_production_targets=true; no_started_migrations=true")
    if not attestation_ok:
        errors.append("Move lab capture template attestation must remain unapproved and lab-safe before capture")

    interactions = template.get("interactions")
    interactions_ok = isinstance(interactions, list) and bool(interactions)
    add_check(checks, "move-lab-capture-template-interactions", interactions_ok, f"count={len(interactions) if isinstance(interactions, list) else 0}")
    if not interactions_ok:
        errors.append("Move lab capture template must include at least one template interaction")

    results = template.get("results") if isinstance(template.get("results"), dict) else {}
    results_ok = int_value(results.get("accepted_payloads")) == 0 and int_value(results.get("created_plans")) == 0 and int_value(results.get("started_migrations")) == 0
    add_check(checks, "move-lab-capture-template-results", results_ok, f"accepted={int_value(results.get('accepted_payloads'))}; created={int_value(results.get('created_plans'))}; started={int_value(results.get('started_migrations'))}")
    if not results_ok:
        errors.append("Move lab capture template results must remain zero before approved lab capture")


def validate_checklist(checklist: str, checks: list[dict[str, str]], errors: list[str]) -> None:
    required_text = (
        "# Move Lab Capture Checklist",
        "validate-move-lab-transcript",
        "generate-approved-move-lab-proof",
        "validate-move-lab-evidence-intake",
        TEMPLATE_EVIDENCE_STATE,
        "captured_approved_lab",
        "NMRCP_MOVE_LAB_ACK",
        "started_migrations=0",
    )
    for item in required_text:
        present = item in checklist
        add_check(checks, f"move-lab-capture-checklist-text-{slug(item)}", present, item)
        if not present:
            errors.append(f"Move lab capture checklist must contain {item}")


def checklist_lines(
    payload_path: Path,
    review_path: Path,
    payload: dict[str, Any],
    review: dict[str, Any],
    workload_count: int,
    network_mapping_count: int,
) -> list[str]:
    approvals = review.get("approvals") if isinstance(review.get("approvals"), dict) else {}
    schedule = payload.get("schedule") if isinstance(payload.get("schedule"), dict) else {}
    return [
        "# Move Lab Capture Checklist",
        "",
        "Use this checklist during an approved non-production Nutanix Move appliance API proof window.",
        "Do not store raw URLs, headers, request bodies, response bodies, cookies, tokens, passwords, or authorization values.",
        "",
        "## Reviewed Inputs",
        "",
        f"- Dry-run payload: `{payload_path.name}`",
        f"- Dry-run payload SHA-256: `{file_sha256(payload_path)}`",
        f"- Move submit review: `{review_path.name}`",
        f"- Workloads in payload: `{workload_count}`",
        f"- Network mappings in payload: `{network_mapping_count}`",
        f"- Schedule start_immediately: `{redacted(schedule.get('start_immediately', 'missing'))}`",
        "",
        "## Required Shell Guard",
        "",
        "```powershell",
        '$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"',
        "```",
        "",
        "Remove this variable when the lab window closes.",
        "",
        "## Capture Steps",
        "",
        "1. Copy `move-lab-transcript.template.json` to `move-lab-transcript.approved.json`.",
        "2. Confirm the Move appliance, vCenter, Prism Central, networks, and workloads are lab-only.",
        "3. Submit only the reviewed dry-run payload to the lab Move appliance.",
        "4. Capture only relative API paths, HTTP method, 2xx status code, dry-run flag, mutation flag, redaction flag, and optional body hashes.",
        f"5. Set `evidence_state` from `{TEMPLATE_EVIDENCE_STATE}` to `captured_approved_lab` only after the API evidence has been redacted.",
        "6. Set `results.accepted_payloads` to the accepted workload or payload count reported by Move.",
        "7. Keep `results.started_migrations=0`; stop if any migration is started.",
        "8. Run `validate-move-lab-transcript` before completing the approved Move lab proof JSON.",
        "9. Run `generate-approved-move-lab-proof` to derive the transcript validation hash, accepted payload counts, and approval record.",
        "10. Run `validate-move-lab-evidence-intake` after transcript validation, proof validation, and capture-kit validation all pass.",
        "",
        "## Transcript Validation Command",
        "",
        "```powershell",
        "python -m nmrcp.cli validate-move-lab-transcript `",
        "  --transcript outputs\\move-lab-capture-kit\\move-lab-transcript.approved.json `",
        f"  --payload {payload_path.name} `",
        f"  --review {review_path.name} `",
        "  --out outputs\\move-lab-transcript-validation.json",
        "```",
        "",
        "## Approved Proof Generation Command",
        "",
        "```powershell",
        "python -m nmrcp.cli generate-approved-move-lab-proof `",
        f"  --payload {payload_path.name} `",
        f"  --review {review_path.name} `",
        "  --transcript outputs\\move-lab-capture-kit\\move-lab-transcript.approved.json `",
        "  --transcript-validation outputs\\move-lab-transcript-validation.json `",
        "  --approved-by \"[LAB_APPROVER]\" `",
        "  --out outputs\\move-lab-proof.approved.json",
        "```",
        "",
        "## Final Evidence Intake Command",
        "",
        "```powershell",
        "python -m nmrcp.cli validate-move-lab-evidence-intake `",
        f"  --payload {payload_path.name} `",
        f"  --review {review_path.name} `",
        "  --transcript outputs\\move-lab-capture-kit\\move-lab-transcript.approved.json `",
        "  --transcript-validation outputs\\move-lab-transcript-validation.json `",
        "  --proof outputs\\move-lab-proof.approved.json `",
        "  --proof-validation outputs\\move-lab-proof-validation.json `",
        "  --capture-kit-validation outputs\\move-lab-capture-kit-validation.json `",
        "  --out outputs\\move-lab-evidence-intake.json",
        "```",
        "",
        "## Required Approvals",
        "",
    ] + approval_lines(approvals)


def approval_lines(approvals: dict[str, Any]) -> list[str]:
    if not approvals:
        return ["- No approvals found in review file."]
    return [f"- `{name}`: `{str(approvals.get(name)).lower()}`" for name in sorted(approvals)]


def read_json_object(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ValueError(f"{label} file is missing: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def read_json_object_for_validation(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except FileNotFoundError:
        errors.append(f"{label} file is missing: {path}")
        return None
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is not valid JSON: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return None
    return payload


def read_text_for_validation(path: Path, label: str, errors: list[str]) -> str:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        errors.append(f"{label} file is missing: {path}")
        return ""
    except UnicodeDecodeError as exc:
        errors.append(f"{label} is not UTF-8: {exc}")
        return ""
    if not text.strip():
        errors.append(f"{label} must not be empty")
    return text


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def add_check(checks: list[dict[str, str]], name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})


def slug(value: str) -> str:
    return "".join(character.lower() if character.isalnum() else "-" for character in value).strip("-")[:48] or "required"


def redacted(value: Any) -> str:
    return str(redact_value(value)).replace("|", "\\|").replace("\n", " ").strip() or "missing"
