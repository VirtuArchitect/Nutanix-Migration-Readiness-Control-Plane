from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .move_submit_readiness import validate_move_submit_readiness
from .redaction_review import scan_text


APPROVED_LAB_SCOPE = "approved_lab_move_appliance"
MOVE_LAB_TRANSCRIPT_SCHEMA_VERSION = "nmrcp_move_lab_transcript_v1"
MOVE_LAB_TRANSCRIPT_VALIDATION_SCHEMA_VERSION = "nmrcp_move_lab_transcript_validation_v1"
FORBIDDEN_TRANSCRIPT_KEYS = {
    "authorization",
    "cookie",
    "headers",
    "password",
    "request_body",
    "response_body",
    "secret",
    "token",
    "url",
}


@dataclass(frozen=True)
class MoveLabTranscriptValidation:
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
            "schema_version": MOVE_LAB_TRANSCRIPT_VALIDATION_SCHEMA_VERSION,
            "status": self.status,
            "checks": list(self.checks),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def validate_move_lab_transcript(
    transcript_path: Path,
    payload_path: Path,
    review_path: Path,
    *,
    lab_ack_env: str = "NMRCP_MOVE_LAB_ACK",
) -> MoveLabTranscriptValidation:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    readiness = validate_move_submit_readiness(payload_path, review_path, lab_ack_env=lab_ack_env)
    add_check(checks, "move-submit-readiness", readiness.ok, readiness.summary())
    errors.extend(f"Move submit readiness: {error}" for error in readiness.errors)
    warnings.extend(f"Move submit readiness: {warning}" for warning in readiness.warnings)

    payload = read_json_object(payload_path, "Move payload", errors)
    transcript = read_json_object(transcript_path, "Move lab transcript", errors)
    if transcript is not None:
        findings = scan_text(transcript_path.name, transcript_path.read_text(encoding="utf-8-sig"))
        add_check(checks, "move-lab-transcript-redaction", not findings, f"findings={len(findings)}")
        errors.extend(f"Move lab transcript leak: {finding}" for finding in findings)
        check_transcript(transcript, payload, payload_path, checks, errors, warnings)

    status = "fail" if errors else "warn" if warnings else "pass"
    return MoveLabTranscriptValidation(status, tuple(checks), tuple(errors), tuple(warnings))


def validate_move_lab_transcript_validation_file(validation_path: Path) -> MoveLabTranscriptValidation:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []
    payload = read_json_object(validation_path, "Move lab transcript validation", errors)
    if payload is not None:
        findings = scan_text(validation_path.name, validation_path.read_text(encoding="utf-8-sig"))
        add_check(checks, "move-lab-transcript-validation-redaction", not findings, f"findings={len(findings)}")
        errors.extend(f"Move lab transcript validation leak: {finding}" for finding in findings)

        schema_ok = payload.get("schema_version") == MOVE_LAB_TRANSCRIPT_VALIDATION_SCHEMA_VERSION
        add_check(checks, "move-lab-transcript-validation-schema", schema_ok, str(payload.get("schema_version") or "missing"))
        if not schema_ok:
            errors.append(f"Move lab transcript validation schema_version must be {MOVE_LAB_TRANSCRIPT_VALIDATION_SCHEMA_VERSION}")

        status = str(payload.get("status") or "")
        status_ok = status in {"pass", "warn"}
        add_check(checks, "move-lab-transcript-validation-status", status_ok, status or "missing")
        if not status_ok:
            errors.append("Move lab transcript validation status must be pass or warn")

        payload_errors = payload.get("errors")
        no_payload_errors = isinstance(payload_errors, list) and not payload_errors
        add_check(checks, "move-lab-transcript-validation-errors", no_payload_errors, f"errors={len(payload_errors) if isinstance(payload_errors, list) else 'invalid'}")
        if not no_payload_errors:
            errors.append("Move lab transcript validation must not contain errors")

        warnings.extend(str(warning) for warning in payload.get("warnings") or [])
    status = "fail" if errors else "warn" if warnings else "pass"
    return MoveLabTranscriptValidation(status, tuple(checks), tuple(errors), tuple(warnings))


def check_transcript(
    transcript: dict[str, Any],
    payload: dict[str, Any] | None,
    payload_path: Path,
    checks: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> None:
    schema_ok = transcript.get("schema_version") == MOVE_LAB_TRANSCRIPT_SCHEMA_VERSION
    add_check(checks, "move-lab-transcript-schema", schema_ok, str(transcript.get("schema_version") or "missing"))
    if not schema_ok:
        errors.append(f"Move lab transcript schema_version must be {MOVE_LAB_TRANSCRIPT_SCHEMA_VERSION}")

    scope_ok = transcript.get("proof_scope") == APPROVED_LAB_SCOPE
    add_check(checks, "move-lab-transcript-scope", scope_ok, str(transcript.get("proof_scope") or "missing"))
    if not scope_ok:
        errors.append("Move lab transcript must use approved_lab_move_appliance proof_scope")

    environment_ok = str(transcript.get("environment") or "").strip().lower() == "lab"
    add_check(checks, "move-lab-transcript-environment", environment_ok, str(transcript.get("environment") or "missing"))
    if not environment_ok:
        errors.append("Move lab transcript environment must be lab")

    mutation_ok = transcript.get("mutation_performed") is False and transcript.get("production_targets") is False
    add_check(checks, "move-lab-transcript-mutation-guard", mutation_ok, "mutation_performed=false; production_targets=false")
    if not mutation_ok:
        errors.append("Move lab transcript must show mutation_performed=false and production_targets=false")

    dry_run_ok = transcript.get("dry_run_only") is True
    add_check(checks, "move-lab-transcript-dry-run-only", dry_run_ok, str(transcript.get("dry_run_only")))
    if not dry_run_ok:
        errors.append("Move lab transcript must show dry_run_only=true")

    evidence_state = str(transcript.get("evidence_state") or "").strip().lower()
    template_state = evidence_state == "template_only_replace_after_lab_capture"
    add_check(checks, "move-lab-transcript-evidence-state", not template_state, evidence_state or "not supplied")
    if template_state:
        errors.append("Move lab transcript template must be copied and replaced with captured approved lab evidence before validation")
    elif not evidence_state:
        warnings.append("Move lab transcript evidence_state not supplied; captured_approved_lab is recommended")

    payload_hash = str(transcript.get("payload_sha256") or "").strip().lower()
    expected_hash = file_sha256(payload_path) if payload is not None else ""
    payload_hash_ok = bool(payload_hash) and payload_hash == expected_hash
    add_check(checks, "move-lab-transcript-payload-hash", payload_hash_ok, "sha256 matched" if payload_hash_ok else "sha256 missing or mismatched")
    if not payload_hash_ok:
        errors.append("Move lab transcript payload_sha256 must match the reviewed dry-run payload")

    interactions = transcript.get("interactions")
    interactions_ok = isinstance(interactions, list) and bool(interactions)
    add_check(checks, "move-lab-transcript-interactions", interactions_ok, f"count={len(interactions) if isinstance(interactions, list) else 0}")
    if not interactions_ok:
        errors.append("Move lab transcript must contain at least one interaction")
        interactions = []

    dry_run_posts = 0
    for index, interaction in enumerate(interactions, start=1):
        if not isinstance(interaction, dict):
            errors.append(f"Interaction {index}: must be an object")
            continue
        check_interaction(index, interaction, errors, warnings)
        method = str(interaction.get("method") or "").strip().upper()
        if method == "POST" and interaction.get("dry_run") is True:
            dry_run_posts += 1
    dry_run_post_ok = dry_run_posts > 0
    add_check(checks, "move-lab-transcript-dry-run-post", dry_run_post_ok, f"count={dry_run_posts}")
    if not dry_run_post_ok:
        errors.append("Move lab transcript must include at least one dry_run=true POST interaction")

    results = transcript.get("results") if isinstance(transcript.get("results"), dict) else {}
    payload_workloads = len(payload.get("workloads")) if isinstance(payload, dict) and isinstance(payload.get("workloads"), list) else 0
    accepted = int_value(results.get("accepted_payloads"))
    accepted_ok = accepted >= max(payload_workloads, 1)
    add_check(checks, "move-lab-transcript-accepted-payloads", accepted_ok, f"accepted={accepted}; payload_workloads={payload_workloads}")
    if not accepted_ok:
        errors.append("Move lab transcript results.accepted_payloads must cover reviewed payload workloads")

    started = int_value(results.get("started_migrations"))
    started_ok = started == 0
    add_check(checks, "move-lab-transcript-started-migrations", started_ok, f"started={started}")
    if not started_ok:
        errors.append("Move lab transcript results.started_migrations must be 0")


def check_interaction(index: int, interaction: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    forbidden = sorted(key for key in interaction if key.lower() in FORBIDDEN_TRANSCRIPT_KEYS)
    if forbidden:
        errors.append(f"Interaction {index}: forbidden raw or secret-bearing fields present: {', '.join(forbidden)}")

    method = str(interaction.get("method") or "").strip().upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        errors.append(f"Interaction {index}: method must be an HTTP verb")
    if method in {"PUT", "PATCH", "DELETE"}:
        errors.append(f"Interaction {index}: mutating HTTP method {method} is not allowed in proof transcript")

    path = str(interaction.get("path") or "").strip()
    if not path.startswith("/") or "://" in path:
        errors.append(f"Interaction {index}: path must be a relative API path")

    status_code = int_value(interaction.get("status_code"))
    if status_code < 200 or status_code >= 300:
        errors.append(f"Interaction {index}: status_code must be 2xx")

    if interaction.get("mutating") is not False:
        errors.append(f"Interaction {index}: mutating must be false")

    if interaction.get("redacted") is not True:
        errors.append(f"Interaction {index}: redacted must be true")

    if not str(interaction.get("request_sha256") or "").strip():
        warnings.append(f"Interaction {index}: request_sha256 not supplied")
    if not str(interaction.get("response_sha256") or "").strip():
        warnings.append(f"Interaction {index}: response_sha256 not supplied")


def read_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
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


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def add_check(checks: list[dict[str, str]], name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})
