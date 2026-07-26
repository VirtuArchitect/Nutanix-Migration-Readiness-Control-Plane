from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
from typing import Any


MOVE_SUBMIT_REVIEW_SCHEMA_VERSION = "nmrcp_move_submit_review_v1"
LAB_ACK_VALUE = "I_UNDERSTAND_LAB_ONLY"
REQUIRED_REVIEW_APPROVALS = {
    "payload_reviewed",
    "network_mapping_reviewed",
    "rollback_reviewed",
    "no_production_submit",
}


@dataclass(frozen=True)
class MoveSubmitReadiness:
    payload_path: Path
    ok: bool
    checks: tuple[dict[str, str], ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"{status}: checks={len(self.checks)}, errors={len(self.errors)}, warnings={len(self.warnings)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": "nmrcp_move_submit_readiness_v1",
            "payload": str(self.payload_path),
            "status": "pass" if self.ok else "fail",
            "checks": list(self.checks),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def validate_move_submit_readiness(
    payload_path: Path,
    review_path: Path,
    *,
    lab_ack_env: str = "NMRCP_MOVE_LAB_ACK",
) -> MoveSubmitReadiness:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    payload = _load_json_object(payload_path, "Move payload", errors)
    review = _load_json_object(review_path, "Move submit review", errors)
    if payload is not None:
        _check_payload_contract(payload, checks, errors, warnings)
        _check_payload_values(payload, checks, errors)
    if review is not None:
        _check_review_record(review, checks, errors)
    _check_lab_ack(lab_ack_env, checks, errors)

    return MoveSubmitReadiness(
        payload_path=payload_path,
        ok=not errors,
        checks=tuple(checks),
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def _load_json_object(path: Path, label: str, errors: list[str]) -> dict[str, Any] | None:
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


def _check_payload_contract(
    payload: dict[str, Any],
    checks: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> None:
    contract_ok = payload.get("contract") == "nmrcp_move_api_payload_dry_run_v1"
    _add_check(checks, "payload-contract", contract_ok, str(payload.get("contract") or "missing"))
    if not contract_ok:
        errors.append("Move payload must use contract nmrcp_move_api_payload_dry_run_v1")

    dry_run_ok = payload.get("dry_run_only") is True and payload.get("mutation_allowed") is False
    _add_check(checks, "payload-mutation-guard", dry_run_ok, "dry_run_only=true; mutation_allowed=false")
    if not dry_run_ok:
        errors.append("Move payload must remain dry-run-only with mutation_allowed=false")

    workloads = payload.get("workloads")
    workload_ok = isinstance(workloads, list) and bool(workloads)
    _add_check(checks, "payload-workloads", workload_ok, f"count={len(workloads) if isinstance(workloads, list) else 0}")
    if not workload_ok:
        errors.append("Move payload must contain at least one included workload")

    network_summary = str(((payload.get("validation") or {}).get("network_mapping") or ""))
    network_ok = network_summary.startswith("PASS:")
    _add_check(checks, "network-mapping", network_ok, network_summary or "missing")
    if not network_ok:
        errors.append("Move payload network mapping validation must pass")

    if payload.get("operator_notes"):
        warnings.append("Operator notes are advisory; readiness still requires review record and lab acknowledgement")


def _check_payload_values(payload: dict[str, Any], checks: list[dict[str, str]], errors: list[str]) -> None:
    value_paths = {
        "source_provider": payload.get("source_provider"),
        "target_provider": payload.get("target_provider"),
        "target_cluster": payload.get("target_cluster"),
        "target_container": payload.get("target_container"),
    }
    for name, value in value_paths.items():
        ok = isinstance(value, dict) and not _contains_placeholder(value)
        _add_check(checks, name, ok, "no placeholders" if ok else "placeholder or missing value")
        if not ok:
            errors.append(f"{name} must be populated with lab-reviewed Move identifiers")

    schedule = payload.get("schedule") if isinstance(payload.get("schedule"), dict) else {}
    safe_schedule = schedule.get("start_immediately") is False
    _add_check(checks, "schedule", safe_schedule, "start_immediately=false")
    if not safe_schedule:
        errors.append("Move payload schedule must not start immediately")


def _check_review_record(review: dict[str, Any], checks: list[dict[str, str]], errors: list[str]) -> None:
    schema_ok = review.get("schema_version") == MOVE_SUBMIT_REVIEW_SCHEMA_VERSION
    _add_check(checks, "review-schema", schema_ok, str(review.get("schema_version") or "missing"))
    if not schema_ok:
        errors.append(f"Move submit review must use schema {MOVE_SUBMIT_REVIEW_SCHEMA_VERSION}")

    environment_ok = str(review.get("environment") or "").strip().lower() == "lab"
    _add_check(checks, "review-environment", environment_ok, str(review.get("environment") or "missing"))
    if not environment_ok:
        errors.append("Move submit review environment must be lab")

    reviewer_ok = bool(str(review.get("reviewed_by") or "").strip()) and bool(str(review.get("reviewed_at") or "").strip())
    _add_check(checks, "reviewer", reviewer_ok, "reviewed_by and reviewed_at supplied")
    if not reviewer_ok:
        errors.append("Move submit review must include reviewed_by and reviewed_at")

    appliance_ok = bool(str(review.get("lab_move_appliance") or "").strip())
    _add_check(checks, "lab-move-appliance", appliance_ok, str(review.get("lab_move_appliance") or "missing"))
    if not appliance_ok:
        errors.append("Move submit review must identify the lab Move appliance")

    approvals = review.get("approvals") if isinstance(review.get("approvals"), dict) else {}
    missing = sorted(key for key in REQUIRED_REVIEW_APPROVALS if approvals.get(key) is not True)
    approvals_ok = not missing
    _add_check(checks, "review-approvals", approvals_ok, "all required approvals true" if approvals_ok else f"missing={','.join(missing)}")
    if missing:
        errors.append(f"Move submit review missing required approvals: {', '.join(missing)}")


def _check_lab_ack(lab_ack_env: str, checks: list[dict[str, str]], errors: list[str]) -> None:
    value = os.getenv(lab_ack_env)
    ok = value == LAB_ACK_VALUE
    _add_check(checks, "lab-acknowledgement", ok, f"{lab_ack_env}=set" if value else f"{lab_ack_env}=missing")
    if not ok:
        errors.append(f"Set {lab_ack_env}={LAB_ACK_VALUE} to acknowledge lab-only Move API experimentation")


def _contains_placeholder(value: Any) -> bool:
    if isinstance(value, dict):
        return any(_contains_placeholder(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_placeholder(item) for item in value)
    text = str(value or "").strip().lower()
    return not text or "placeholder" in text or text in {"todo", "tbd", "changeme"}


def _add_check(checks: list[dict[str, str]], name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})
