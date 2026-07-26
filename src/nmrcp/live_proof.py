from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .collection_audit import validate_collection_audit_file
from .collection_workflow import COLLECTION_PROOF_MANIFEST_SCHEMA_VERSION, COLLECTION_SUMMARY_SCHEMA_VERSION
from .redaction_review import scan_text


LIVE_PROOF_SCHEMA_VERSION = "nmrcp_live_endpoint_proof_v1"
LIVE_READINESS_SCHEMA_VERSION = "nmrcp_live_readiness_v1"
ALLOWED_VCENTER_READ_ONLY_CALLS = {"/api/session", "/api/vcenter/vm"}
ALLOWED_VCENTER_COLLECTION_CALLS = ALLOWED_VCENTER_READ_ONLY_CALLS | {"/api/vcenter/vm/{vm}", "/api/vcenter/network"}
ALLOWED_PRISM_READ_ONLY_CALLS = {"/api/nutanix/v3/clusters/list", "/api/nutanix/v3/vms/list"}
ALLOWED_COLLECTION_CALLS = ALLOWED_VCENTER_COLLECTION_CALLS | ALLOWED_PRISM_READ_ONLY_CALLS
ALLOWED_TLS_VERIFICATION_STATES = {"enabled", "disabled", "loopback_http", "not_configured"}
ASSESSMENT_INTAKE_VALIDATION_SCHEMA_VERSION = "nmrcp_assessment_intake_validation_v1"


@dataclass(frozen=True)
class LiveProofValidation:
    status: str
    checks: tuple[dict[str, Any], ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={len(self.checks)}, errors={len(self.errors)}, warnings={len(self.warnings)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LIVE_PROOF_SCHEMA_VERSION,
            "status": self.status,
            "checks": list(self.checks),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def validate_live_proof(
    live_readiness_path: Path,
    collection_summary_path: Path | None = None,
    source_dir: Path | None = None,
) -> LiveProofValidation:
    checks: list[dict[str, Any]] = []
    errors: list[str] = []
    warnings: list[str] = []

    live_readiness = read_json(live_readiness_path, errors)
    if live_readiness:
        validate_live_readiness_payload(live_readiness_path, live_readiness, checks, errors, warnings)

    if collection_summary_path:
        collection_summary = read_json(collection_summary_path, errors)
        if collection_summary:
            validate_collection_summary_payload(collection_summary_path, collection_summary, checks, errors, warnings)
            if source_dir:
                validate_source_inventory_audits(source_dir, collection_summary, checks, errors, warnings)
                validate_collection_proof_manifest(source_dir, collection_summary, checks, errors, warnings)
    else:
        add_check(checks, "collection-summary", True, "not provided; endpoint readiness proof only")
        warnings.append("Collection summary not provided; source collection artifact proof not evaluated")

    status = "fail" if errors else "warn" if warnings else "pass"
    return LiveProofValidation(status, tuple(checks), tuple(errors), tuple(warnings))


def validate_live_readiness_payload(
    path: Path,
    payload: dict[str, Any],
    checks: list[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> None:
    findings = scan_text(path.name, path.read_text(encoding="utf-8"))
    add_check(checks, "live-readiness-redaction", not findings, f"findings={len(findings)}")
    errors.extend(f"Live readiness proof leak: {finding}" for finding in findings)

    schema_ok = payload.get("schema_version") == LIVE_READINESS_SCHEMA_VERSION
    add_check(checks, "live-readiness-schema", schema_ok, str(payload.get("schema_version") or "missing"))
    if not schema_ok:
        errors.append(f"live readiness schema_version must be {LIVE_READINESS_SCHEMA_VERSION}")

    status_ok = payload.get("status") == "pass"
    add_check(checks, "live-readiness-status", status_ok, str(payload.get("status") or "missing"))
    if not status_ok:
        errors.append("live readiness status must be pass for external proof")

    security = payload.get("security") if isinstance(payload.get("security"), dict) else {}
    security_ok = (
        security.get("mode") == "read-only"
        and security.get("credentials_serialized") is False
        and security.get("endpoint_values_serialized") is False
        and security.get("mutation_allowed") is False
    )
    add_check(checks, "live-readiness-security", security_ok, "read-only redacted mutation_allowed=false")
    if not security_ok:
        errors.append("live readiness security block must prove read-only mode with no serialized credentials or endpoints")
    tls_states = security.get("tls_verification") if isinstance(security.get("tls_verification"), dict) else {}
    tls_ok = validate_tls_state_map(
        "live-readiness-security",
        tls_states,
        ("vcenter", "prism-central"),
        checks,
        errors,
        warnings,
    )
    add_check(checks, "live-readiness-tls-verification", tls_ok, tls_state_detail(tls_states))

    live_checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    for name in ("vcenter", "prism-central"):
        check = next((item for item in live_checks if isinstance(item, dict) and item.get("name") == name), None)
        if not isinstance(check, dict):
            add_check(checks, f"{name}-live-readiness", False, "missing")
            errors.append(f"live readiness missing {name} check")
            continue
        validate_endpoint_check(name, check, checks, errors, warnings)


def validate_endpoint_check(
    name: str,
    check: dict[str, Any],
    checks: list[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> None:
    ok = check.get("status") == "pass" and check.get("configured") is True and check.get("authenticated") is True
    add_check(checks, f"{name}-live-readiness", ok, f"status={check.get('status')}; configured={check.get('configured')}")
    if not ok:
        errors.append(f"{name} live readiness must be configured, authenticated, and pass")
    tls_ok = validate_tls_state(
        f"{name}-live-readiness",
        check.get("tls_verification"),
        checks,
        errors,
        warnings,
    )
    add_check(checks, f"{name}-tls-verification", tls_ok, str(check.get("tls_verification") or "missing"))

    read_only_calls = set(str(call) for call in check.get("read_only_calls") or [])
    allowed = ALLOWED_VCENTER_READ_ONLY_CALLS if name == "vcenter" else ALLOWED_PRISM_READ_ONLY_CALLS
    calls_ok = bool(read_only_calls) and read_only_calls <= allowed
    add_check(checks, f"{name}-read-only-calls", calls_ok, ", ".join(sorted(read_only_calls)) or "none")
    if not calls_ok:
        errors.append(f"{name} read-only calls must be limited to approved inventory paths")

    counts = check.get("counts") if isinstance(check.get("counts"), dict) else {}
    if name == "vcenter":
        if int_value(counts.get("vms")) <= 0:
            errors.append("vCenter live proof must observe at least one VM")
    if name == "prism-central":
        if int_value(counts.get("clusters")) <= 0:
            errors.append("Prism Central live proof must observe at least one cluster")
        if int_value(counts.get("vms")) == 0:
            warnings.append("Prism Central live proof observed zero existing VMs; target inventory may be empty")


def validate_collection_summary_payload(
    path: Path,
    payload: dict[str, Any],
    checks: list[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> None:
    findings = scan_text(path.name, path.read_text(encoding="utf-8"))
    add_check(checks, "collection-summary-redaction", not findings, f"findings={len(findings)}")
    errors.extend(f"Collection summary proof leak: {finding}" for finding in findings)

    schema_ok = payload.get("schema_version") == COLLECTION_SUMMARY_SCHEMA_VERSION
    add_check(checks, "collection-summary-schema", schema_ok, str(payload.get("schema_version") or "missing"))
    if not schema_ok:
        errors.append(f"collection summary schema_version must be {COLLECTION_SUMMARY_SCHEMA_VERSION}")
    if payload.get("status") != "pass":
        errors.append("collection summary status must be pass")

    privacy = payload.get("privacy") if isinstance(payload.get("privacy"), dict) else {}
    privacy_ok = (
        privacy.get("credentials_serialized") is False
        and privacy.get("endpoint_values_serialized") is False
        and privacy.get("summary_redacted") is True
    )
    add_check(checks, "collection-summary-privacy", privacy_ok, "redacted no credentials/endpoints")
    if not privacy_ok:
        errors.append("collection summary privacy block must prove no serialized credentials or endpoints")
    tls_states = privacy.get("tls_verification") if isinstance(privacy.get("tls_verification"), dict) else {}
    tls_ok = validate_tls_state_map(
        "collection-summary-privacy",
        tls_states,
        ("vcenter", "prism-central"),
        checks,
        errors,
        warnings,
    )
    add_check(checks, "collection-summary-tls-verification", tls_ok, tls_state_detail(tls_states))
    validate_assessment_intake_binding(
        payload.get("governance", {}).get("assessment_intake") if isinstance(payload.get("governance"), dict) else None,
        "collection-summary-assessment-intake",
        checks,
        errors,
    )

    summary_checks = payload.get("checks") if isinstance(payload.get("checks"), list) else []
    for check in summary_checks:
        if not isinstance(check, dict):
            continue
        name = str(check.get("name") or "unknown")
        mutating_ok = int_value(check.get("mutating_calls")) == 0
        add_check(checks, f"{name}-mutating-calls", mutating_ok, f"mutating_calls={check.get('mutating_calls')}")
        if not mutating_ok:
            errors.append(f"{name} must report mutating_calls=0")
        tls_ok = validate_tls_state(name, check.get("tls_verification"), checks, errors, warnings)
        add_check(checks, f"{name}-tls-verification", tls_ok, str(check.get("tls_verification") or "missing"))
        if name == "vcenter-read-only-collection" and int_value(check.get("workloads")) <= 0:
            errors.append("vCenter collection summary must report at least one workload")
        if name == "vcenter-network-read-only-collection" and int_value(check.get("networks")) <= 0:
            warnings.append("vCenter network collection summary reported zero networks")
        if name == "prism-capacity-read-only-collection" and int_value(check.get("targets")) <= 0:
            errors.append("Prism capacity collection summary must report at least one target")
        if name == "prism-read-only-collection" and int_value(check.get("workloads")) == 0:
            warnings.append("Prism collection summary reported zero existing VMs; target inventory may be empty")


def validate_source_inventory_audits(
    source_dir: Path,
    collection_summary: dict[str, Any],
    checks: list[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> None:
    artifacts = collection_summary.get("artifacts") if isinstance(collection_summary.get("artifacts"), dict) else {}
    for key in ("vcenter_inventory", "prism_inventory"):
        relative = artifacts.get(key)
        if not isinstance(relative, str):
            errors.append(f"collection summary missing artifact path for {key}")
            continue
        path = source_dir / relative
        if not path.exists():
            add_check(checks, f"{key}-audit", False, f"missing {relative}")
            errors.append(f"{key} not found at {path}")
            continue
        result = validate_collection_audit_file(path)
        add_check(checks, f"{key}-audit", result.ok, result.summary())
        errors.extend(f"{key}: {error}" for error in result.errors)
        warnings.extend(f"{key}: {warning}" for warning in result.warnings)


def validate_collection_proof_manifest(
    source_dir: Path,
    collection_summary: dict[str, Any],
    checks: list[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> None:
    artifacts = collection_summary.get("artifacts") if isinstance(collection_summary.get("artifacts"), dict) else {}
    relative = artifacts.get("collection_proof_manifest")
    if not isinstance(relative, str):
        add_check(checks, "collection-proof-manifest", False, "missing from collection summary")
        errors.append("collection summary missing artifact path for collection_proof_manifest")
        return
    path = source_dir / relative
    if not path.exists():
        add_check(checks, "collection-proof-manifest", False, f"missing {relative}")
        errors.append(f"collection proof manifest not found at {path}")
        return
    payload = read_json(path, errors)
    if not payload:
        add_check(checks, "collection-proof-manifest", False, "unreadable")
        return

    findings = scan_text(path.name, path.read_text(encoding="utf-8"))
    add_check(checks, "collection-proof-manifest-redaction", not findings, f"findings={len(findings)}")
    errors.extend(f"Collection proof manifest leak: {finding}" for finding in findings)

    schema_ok = payload.get("schema_version") == COLLECTION_PROOF_MANIFEST_SCHEMA_VERSION
    add_check(checks, "collection-proof-manifest-schema", schema_ok, str(payload.get("schema_version") or "missing"))
    if not schema_ok:
        errors.append(f"collection proof manifest schema_version must be {COLLECTION_PROOF_MANIFEST_SCHEMA_VERSION}")

    security = payload.get("security") if isinstance(payload.get("security"), dict) else {}
    security_ok = (
        security.get("mode") == "read-only"
        and security.get("credentials_serialized") is False
        and security.get("endpoint_values_serialized") is False
        and security.get("mutation_allowed") is False
    )
    add_check(checks, "collection-proof-manifest-security", security_ok, "read-only redacted mutation_allowed=false")
    if not security_ok:
        errors.append("collection proof manifest security block must prove read-only mode with no credentials, endpoints, or mutations")

    api_paths = set(str(item) for item in security.get("read_only_api_allowlist") or [])
    api_ok = bool(api_paths) and api_paths <= ALLOWED_COLLECTION_CALLS
    add_check(checks, "collection-proof-manifest-api-allowlist", api_ok, ", ".join(sorted(api_paths)) or "none")
    if not api_ok:
        errors.append("collection proof manifest read-only API allowlist contains missing or unapproved paths")

    summary_intake = (
        collection_summary.get("governance", {}).get("assessment_intake")
        if isinstance(collection_summary.get("governance"), dict)
        else None
    )
    manifest_intake = security.get("assessment_intake")
    manifest_intake_ok = validate_assessment_intake_binding(
        manifest_intake,
        "collection-proof-manifest-assessment-intake",
        checks,
        errors,
    )
    intake_match_ok = bool(manifest_intake_ok and manifest_intake == summary_intake)
    add_check(
        checks,
        "collection-proof-manifest-assessment-intake-match",
        intake_match_ok,
        "manifest matches collection summary" if intake_match_ok else "manifest and summary differ",
    )
    if not intake_match_ok:
        errors.append("collection proof manifest assessment intake proof must match collection summary governance")

    manifest_artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), list) else []
    by_name = {str(item.get("name")): item for item in manifest_artifacts if isinstance(item, dict) and item.get("name")}
    expected_names = {
        str(item)
        for key, item in artifacts.items()
        if key != "collection_proof_manifest" and isinstance(item, str)
    }
    names_ok = expected_names == set(by_name)
    add_check(checks, "collection-proof-manifest-artifacts", names_ok, f"expected={len(expected_names)}; actual={len(by_name)}")
    if not names_ok:
        missing = sorted(expected_names - set(by_name))
        unexpected = sorted(set(by_name) - expected_names)
        if missing:
            errors.append(f"collection proof manifest missing artifacts: {', '.join(missing)}")
        if unexpected:
            errors.append(f"collection proof manifest has unexpected artifacts: {', '.join(unexpected)}")

    for name in sorted(expected_names & set(by_name)):
        artifact_path = source_dir / name
        entry = by_name[name]
        if not artifact_path.exists():
            add_check(checks, f"collection-proof-artifact:{name}", False, "missing")
            errors.append(f"collection proof artifact not found: {name}")
            continue
        size_ok = entry.get("size_bytes") == artifact_path.stat().st_size
        hash_ok = entry.get("sha256") == sha256_file(artifact_path)
        ok = size_ok and hash_ok
        add_check(checks, f"collection-proof-artifact:{name}", ok, "checksum and size match" if ok else "checksum or size mismatch")
        if not size_ok:
            errors.append(f"collection proof artifact size mismatch: {name}")
        if not hash_ok:
            errors.append(f"collection proof artifact checksum mismatch: {name}")


def read_json(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read JSON: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append(f"{path}: JSON root must be an object")
        return {}
    return payload


def add_check(checks: list[dict[str, Any]], name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})


def validate_tls_state_map(
    label: str,
    states: dict[str, Any],
    required_keys: tuple[str, ...],
    checks: list[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
) -> bool:
    ok = True
    for key in required_keys:
        if not validate_tls_state(f"{label}:{key}", states.get(key), checks, errors, warnings, add_individual_check=False):
            ok = False
    return ok


def validate_tls_state(
    label: str,
    value: Any,
    checks: list[dict[str, Any]],
    errors: list[str],
    warnings: list[str],
    *,
    add_individual_check: bool = False,
) -> bool:
    state = str(value or "")
    ok = state in ALLOWED_TLS_VERIFICATION_STATES
    if add_individual_check:
        add_check(checks, f"{label}-tls-verification", ok, state or "missing")
    if not ok:
        errors.append(f"{label} TLS verification state must be one of: {', '.join(sorted(ALLOWED_TLS_VERIFICATION_STATES))}")
        return False
    if state == "not_configured":
        errors.append(f"{label} TLS verification state must not be not_configured for external live proof")
        return False
    if state == "disabled":
        warnings.append(f"{label} TLS certificate verification was disabled; confirm this was an approved exception")
    return True


def validate_assessment_intake_binding(
    value: Any,
    label: str,
    checks: list[dict[str, Any]],
    errors: list[str],
) -> bool:
    if not isinstance(value, dict):
        add_check(checks, label, False, "missing")
        errors.append(f"{label} must include validated assessment intake proof")
        return False

    source_sha256 = str(value.get("source_sha256") or "")
    ok = (
        value.get("status") == "pass"
        and value.get("schema_version") == ASSESSMENT_INTAKE_VALIDATION_SCHEMA_VERSION
        and value.get("values_serialized") is False
        and int_value(value.get("rows")) > 0
        and len(source_sha256) == 64
        and all(character in "0123456789abcdef" for character in source_sha256.lower())
    )
    add_check(checks, label, ok, f"status={value.get('status')}; rows={value.get('rows')}")
    if not ok:
        errors.append(
            f"{label} must prove validated {ASSESSMENT_INTAKE_VALIDATION_SCHEMA_VERSION} with checksum and no serialized values"
        )
    return ok


def tls_state_detail(states: dict[str, Any]) -> str:
    if not states:
        return "missing"
    return ", ".join(f"{key}={states.get(key)}" for key in sorted(states))


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
