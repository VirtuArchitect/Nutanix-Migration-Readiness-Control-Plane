from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .move_submit_readiness import validate_move_submit_readiness
from .move_lab_transcript import validate_move_lab_transcript, validate_move_lab_transcript_validation_file
from .redaction_review import scan_text


MOVE_LAB_PROOF_SCHEMA_VERSION = "nmrcp_move_lab_proof_v1"
MOVE_LAB_VALIDATION_SCHEMA_VERSION = "nmrcp_move_lab_proof_validation_v1"
APPROVED_LAB_SCOPE = "approved_lab_move_appliance"
SIMULATED_SCOPE = "simulated_contract"
ALLOWED_SCOPES = {APPROVED_LAB_SCOPE, SIMULATED_SCOPE}
REQUIRED_APPROVALS = (
    "change_window_reviewed",
    "rollback_reviewed",
    "operator_present",
    "no_production_targets",
    "credentials_not_persisted",
)
PROOF_TEMPLATE_SCOPES = {APPROVED_LAB_SCOPE, SIMULATED_SCOPE}


def write_move_lab_proof_template(
    payload_path: Path,
    review_path: Path,
    out_path: Path,
    *,
    proof_scope: str = SIMULATED_SCOPE,
) -> Path:
    if proof_scope not in PROOF_TEMPLATE_SCOPES:
        raise ValueError(f"proof_scope must be one of {', '.join(sorted(PROOF_TEMPLATE_SCOPES))}")
    payload = load_json_object(payload_path, "Move payload")
    review = load_json_object(review_path, "Move submit review")
    workloads = payload.get("workloads") if isinstance(payload.get("workloads"), list) else []
    proof = {
        "schema_version": MOVE_LAB_PROOF_SCHEMA_VERSION,
        "proof_scope": proof_scope,
        "environment": "lab",
        "reviewed_by": str(review.get("reviewed_by") or ""),
        "reviewed_at": datetime.now(UTC).isoformat(),
        "lab_move_appliance": str(review.get("lab_move_appliance") or ""),
        "api_round_trip": False if proof_scope == APPROVED_LAB_SCOPE else True,
        "dry_run_only": True,
        "mutation_performed": False,
        "production_targets": False,
        "transcript_validation_sha256": "" if proof_scope == APPROVED_LAB_SCOPE else "not-required-for-simulated-proof",
        "results": {
            "payload_workloads": len(workloads),
            "accepted_payloads": len(workloads) if proof_scope == SIMULATED_SCOPE else 0,
            "created_plans": 0,
            "started_migrations": 0,
        },
        "approvals": {name: False for name in REQUIRED_APPROVALS},
        "notes": (
            "Simulated local contract proof. Replace with approved_lab_move_appliance proof after real lab Move testing."
            if proof_scope == SIMULATED_SCOPE
            else "Approved lab Move proof template. Fill only after real non-production Move API round-trip evidence is reviewed."
        ),
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(proof, indent=2), encoding="utf-8")
    return out_path


def write_approved_move_lab_proof(
    payload_path: Path,
    review_path: Path,
    transcript_path: Path,
    transcript_validation_path: Path,
    out_path: Path,
    *,
    approved_by: str,
    notes: str = "",
    lab_ack_env: str = "NMRCP_MOVE_LAB_ACK",
) -> Path:
    readiness = validate_move_submit_readiness(payload_path, review_path, lab_ack_env=lab_ack_env)
    if not readiness.ok:
        raise ValueError("Move submit readiness must pass before approved proof generation: " + "; ".join(readiness.errors))
    if readiness.warnings:
        raise ValueError("Move submit readiness warnings must be resolved before approved proof generation: " + "; ".join(readiness.warnings))

    transcript_validation = validate_move_lab_transcript_validation_file(transcript_validation_path)
    if not transcript_validation.ok:
        raise ValueError("Move lab transcript validation must pass before approved proof generation: " + "; ".join(transcript_validation.errors))
    if transcript_validation.warnings:
        raise ValueError("Move lab transcript validation warnings must be resolved before approved proof generation: " + "; ".join(transcript_validation.warnings))

    current_transcript = validate_move_lab_transcript(transcript_path, payload_path, review_path, lab_ack_env=lab_ack_env)
    if not current_transcript.ok:
        raise ValueError("Move lab transcript must validate before approved proof generation: " + "; ".join(current_transcript.errors))
    if current_transcript.warnings:
        raise ValueError("Move lab transcript warnings must be resolved before approved proof generation: " + "; ".join(current_transcript.warnings))

    payload = load_json_object(payload_path, "Move payload")
    review = load_json_object(review_path, "Move submit review")
    transcript = load_json_object(transcript_path, "Move lab transcript")
    validate_transcript_for_approved_proof(transcript, payload_path, payload)

    workloads = payload.get("workloads") if isinstance(payload.get("workloads"), list) else []
    results = transcript.get("results") if isinstance(transcript.get("results"), dict) else {}
    proof = {
        "schema_version": MOVE_LAB_PROOF_SCHEMA_VERSION,
        "proof_scope": APPROVED_LAB_SCOPE,
        "environment": "lab",
        "reviewed_by": approved_by.strip(),
        "reviewed_at": datetime.now(UTC).isoformat(),
        "lab_move_appliance": str(transcript.get("lab_move_appliance") or review.get("lab_move_appliance") or ""),
        "api_round_trip": True,
        "dry_run_only": True,
        "mutation_performed": False,
        "production_targets": False,
        "transcript_validation_sha256": sha256_file(transcript_validation_path),
        "results": {
            "payload_workloads": len(workloads),
            "accepted_payloads": int_value(results.get("accepted_payloads")),
            "created_plans": max(int_value(results.get("created_plans")), 0),
            "started_migrations": int_value(results.get("started_migrations")),
        },
        "approvals": {name: True for name in REQUIRED_APPROVALS},
        "notes": notes.strip()
        or "Generated from clean approved lab transcript validation; no production targets or started migrations.",
    }
    if not proof["reviewed_by"]:
        raise ValueError("--approved-by is required for approved proof generation")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(proof, indent=2), encoding="utf-8")
    return out_path


@dataclass(frozen=True)
class MoveLabProofValidation:
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
            "schema_version": MOVE_LAB_VALIDATION_SCHEMA_VERSION,
            "status": self.status,
            "checks": list(self.checks),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def validate_move_lab_proof(
    proof_path: Path,
    payload_path: Path,
    review_path: Path,
    *,
    transcript_validation_path: Path | None = None,
    lab_ack_env: str = "NMRCP_MOVE_LAB_ACK",
) -> MoveLabProofValidation:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    readiness = validate_move_submit_readiness(payload_path, review_path, lab_ack_env=lab_ack_env)
    add_check(checks, "move-submit-readiness", readiness.ok, readiness.summary())
    errors.extend(f"Move submit readiness: {error}" for error in readiness.errors)
    warnings.extend(f"Move submit readiness: {warning}" for warning in readiness.warnings)

    proof = read_json_object(proof_path, "Move lab proof", errors)
    if proof is not None:
        findings = scan_text(proof_path.name, proof_path.read_text(encoding="utf-8"))
        add_check(checks, "move-lab-proof-redaction", not findings, f"findings={len(findings)}")
        errors.extend(f"Move lab proof leak: {finding}" for finding in findings)
        check_proof(proof, checks, errors, warnings, transcript_validation_path=transcript_validation_path)

    status = "fail" if errors else "warn" if warnings else "pass"
    return MoveLabProofValidation(status, tuple(checks), tuple(errors), tuple(warnings))


def validate_move_lab_proof_validation_file(
    validation_path: Path,
    *,
    require_approved_lab: bool = True,
) -> MoveLabProofValidation:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []
    payload = read_json_object(validation_path, "Move lab proof validation", errors)
    if payload is not None:
        findings = scan_text(validation_path.name, validation_path.read_text(encoding="utf-8"))
        add_check(checks, "move-lab-validation-redaction", not findings, f"findings={len(findings)}")
        errors.extend(f"Move lab validation leak: {finding}" for finding in findings)

        schema_ok = payload.get("schema_version") == MOVE_LAB_VALIDATION_SCHEMA_VERSION
        add_check(checks, "move-lab-validation-schema", schema_ok, str(payload.get("schema_version") or "missing"))
        if not schema_ok:
            errors.append(f"Move lab validation schema_version must be {MOVE_LAB_VALIDATION_SCHEMA_VERSION}")

        payload_errors = payload.get("errors")
        no_payload_errors = isinstance(payload_errors, list) and not payload_errors
        add_check(checks, "move-lab-validation-errors", no_payload_errors, f"errors={len(payload_errors) if isinstance(payload_errors, list) else 'invalid'}")
        if not no_payload_errors:
            errors.append("Move lab validation proof must not contain errors")

        status = str(payload.get("status") or "")
        if require_approved_lab:
            status_ok = status == "pass"
            add_check(checks, "move-lab-validation-status", status_ok, status or "missing")
            if not status_ok:
                errors.append("Approved Move lab validation proof must have status pass")
            _check_approved_scope(payload, checks, errors)
        else:
            status_ok = status in {"pass", "warn"}
            add_check(checks, "move-lab-validation-status", status_ok, status or "missing")
            if not status_ok:
                errors.append("Move lab validation proof status must be pass or warn")
            warnings.extend(str(warning) for warning in payload.get("warnings") or [])
    status = "fail" if errors else "warn" if warnings else "pass"
    return MoveLabProofValidation(status, tuple(checks), tuple(errors), tuple(warnings))


def _check_approved_scope(payload: dict[str, Any], checks: list[dict[str, str]], errors: list[str]) -> None:
    validation_checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    scope_check = next(
        (check for check in validation_checks if isinstance(check, dict) and check.get("name") == "move-lab-proof-scope"),
        None,
    )
    approved = (
        isinstance(scope_check, dict)
        and scope_check.get("status") == "pass"
        and scope_check.get("detail") == APPROVED_LAB_SCOPE
    )
    add_check(checks, "move-lab-approved-scope", approved, str(scope_check.get("detail") if isinstance(scope_check, dict) else "missing"))
    if not approved:
        errors.append("Move lab validation proof must have approved_lab_move_appliance scope")
    transcript_check = next(
        (check for check in validation_checks if isinstance(check, dict) and check.get("name") == "move-lab-transcript-validation-link"),
        None,
    )
    transcript_linked = isinstance(transcript_check, dict) and transcript_check.get("status") == "pass"
    add_check(checks, "move-lab-approved-transcript-link", transcript_linked, str(transcript_check.get("detail") if isinstance(transcript_check, dict) else "missing"))
    if not transcript_linked:
        errors.append("Approved Move lab validation proof must include a passing transcript validation link")


def check_proof(
    proof: dict[str, Any],
    checks: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
    *,
    transcript_validation_path: Path | None = None,
) -> None:
    schema_ok = proof.get("schema_version") == MOVE_LAB_PROOF_SCHEMA_VERSION
    add_check(checks, "move-lab-proof-schema", schema_ok, str(proof.get("schema_version") or "missing"))
    if not schema_ok:
        errors.append(f"Move lab proof schema_version must be {MOVE_LAB_PROOF_SCHEMA_VERSION}")

    scope = str(proof.get("proof_scope") or "").strip()
    scope_ok = scope in ALLOWED_SCOPES
    add_check(checks, "move-lab-proof-scope", scope_ok, scope or "missing")
    if not scope_ok:
        errors.append(f"Move lab proof proof_scope must be one of {', '.join(sorted(ALLOWED_SCOPES))}")
    if scope == SIMULATED_SCOPE:
        warnings.append("Move lab proof is simulated_contract; real lab Move appliance behavior remains unproven")
    if scope == APPROVED_LAB_SCOPE:
        check_transcript_validation_link(proof, transcript_validation_path, checks, errors, warnings)

    environment_ok = str(proof.get("environment") or "").strip().lower() == "lab"
    add_check(checks, "move-lab-environment", environment_ok, str(proof.get("environment") or "missing"))
    if not environment_ok:
        errors.append("Move lab proof environment must be lab")

    appliance_ok = bool(str(proof.get("lab_move_appliance") or "").strip())
    add_check(checks, "move-lab-appliance", appliance_ok, str(proof.get("lab_move_appliance") or "missing"))
    if not appliance_ok:
        errors.append("Move lab proof must identify the lab Move appliance without credentials")

    mutation_ok = proof.get("mutation_performed") is False and proof.get("production_targets") is False
    add_check(checks, "move-lab-mutation-guard", mutation_ok, "mutation_performed=false; production_targets=false")
    if not mutation_ok:
        errors.append("Move lab proof must show mutation_performed=false and production_targets=false")

    api_round_trip_ok = proof.get("api_round_trip") is True
    add_check(checks, "move-lab-api-round-trip", api_round_trip_ok, str(proof.get("api_round_trip")))
    if not api_round_trip_ok:
        errors.append("Move lab proof must show api_round_trip=true")

    dry_run_ok = proof.get("dry_run_only") is True
    add_check(checks, "move-lab-dry-run-only", dry_run_ok, str(proof.get("dry_run_only")))
    if not dry_run_ok:
        errors.append("Move lab proof must show dry_run_only=true")

    results = proof.get("results") if isinstance(proof.get("results"), dict) else {}
    if int_value(results.get("payload_workloads")) <= 0:
        errors.append("Move lab proof results.payload_workloads must be positive")
    if int_value(results.get("accepted_payloads")) <= 0:
        errors.append("Move lab proof results.accepted_payloads must be positive")

    approvals = proof.get("approvals") if isinstance(proof.get("approvals"), dict) else {}
    missing = sorted(name for name in REQUIRED_APPROVALS if approvals.get(name) is not True)
    approvals_ok = not missing
    add_check(checks, "move-lab-approvals", approvals_ok, "all required approvals true" if approvals_ok else f"missing={','.join(missing)}")
    if missing:
        errors.append(f"Move lab proof missing required approvals: {', '.join(missing)}")


def check_transcript_validation_link(
    proof: dict[str, Any],
    transcript_validation_path: Path | None,
    checks: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> None:
    if transcript_validation_path is None:
        add_check(checks, "move-lab-transcript-validation-link", False, "not provided")
        errors.append("Approved Move lab proof requires --transcript-validation evidence")
        return

    transcript = validate_move_lab_transcript_validation_file(transcript_validation_path)
    add_check(checks, "move-lab-transcript-validation", transcript.ok, transcript.summary())
    errors.extend(f"Move lab transcript validation: {error}" for error in transcript.errors)
    warnings.extend(f"Move lab transcript validation: {warning}" for warning in transcript.warnings)

    expected_hash = sha256_file(transcript_validation_path)
    actual_hash = str(proof.get("transcript_validation_sha256") or "").strip().lower()
    hash_ok = actual_hash == expected_hash
    add_check(checks, "move-lab-transcript-validation-link", hash_ok, "sha256 matched" if hash_ok else "sha256 missing or mismatched")
    if not hash_ok:
        errors.append("Approved Move lab proof transcript_validation_sha256 must match --transcript-validation")


def read_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
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


def load_json_object(path: Path, label: str) -> dict[str, Any]:
    errors: list[str] = []
    payload = read_json_object(path, label, errors)
    if errors:
        raise ValueError("; ".join(errors))
    if payload is None:
        raise ValueError(f"{label} could not be loaded")
    return payload


def validate_transcript_for_approved_proof(transcript: dict[str, Any], payload_path: Path, payload: dict[str, Any]) -> None:
    errors: list[str] = []
    if transcript.get("schema_version") != "nmrcp_move_lab_transcript_v1":
        errors.append("Move lab transcript schema_version must be nmrcp_move_lab_transcript_v1")
    if transcript.get("proof_scope") != APPROVED_LAB_SCOPE:
        errors.append("Move lab transcript proof_scope must be approved_lab_move_appliance")
    if str(transcript.get("evidence_state") or "").strip().lower() != "captured_approved_lab":
        errors.append("Move lab transcript evidence_state must be captured_approved_lab")
    if transcript.get("dry_run_only") is not True:
        errors.append("Move lab transcript dry_run_only must be true")
    if transcript.get("mutation_performed") is not False or transcript.get("production_targets") is not False:
        errors.append("Move lab transcript must show mutation_performed=false and production_targets=false")

    expected_payload_hash = sha256_file(payload_path)
    actual_payload_hash = str(transcript.get("payload_sha256") or "").strip().lower()
    if actual_payload_hash != expected_payload_hash:
        errors.append("Move lab transcript payload_sha256 must match the reviewed dry-run payload")

    payload_workloads = len(payload.get("workloads")) if isinstance(payload.get("workloads"), list) else 0
    results = transcript.get("results") if isinstance(transcript.get("results"), dict) else {}
    if int_value(results.get("accepted_payloads")) < max(payload_workloads, 1):
        errors.append("Move lab transcript results.accepted_payloads must cover reviewed payload workloads")
    if int_value(results.get("started_migrations")) != 0:
        errors.append("Move lab transcript results.started_migrations must be 0")
    if not str(transcript.get("lab_move_appliance") or "").strip():
        errors.append("Move lab transcript must identify the lab Move appliance")

    if errors:
        raise ValueError("; ".join(errors))


def add_check(checks: list[dict[str, str]], name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
