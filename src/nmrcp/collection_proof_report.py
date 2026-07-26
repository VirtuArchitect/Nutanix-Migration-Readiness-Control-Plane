from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .redaction_review import scan_text


COLLECTION_PROOF_REPORT_SCHEMA_VERSION = "nmrcp_collection_proof_report_v1"
COLLECTION_SUMMARY_SCHEMA_VERSION = "nmrcp_collection_summary_v1"
REQUIRED_SECTIONS = (
    "# Source Collection Proof Report",
    "## Collection Status",
    "## Read-Only Evidence",
    "## Privacy Posture",
    "## Assessment Intake Binding",
    "## Artifact Manifest",
    "## Stop Conditions",
)
REQUIRED_FRAGMENTS = (
    COLLECTION_PROOF_REPORT_SCHEMA_VERSION,
    COLLECTION_SUMMARY_SCHEMA_VERSION,
    "mutating_calls=0",
    "credentials_serialized=false",
    "endpoint_values_serialized=false",
    "summary_redacted=true",
    "collection-proof-manifest.json",
    "validate-live-proof",
)


@dataclass(frozen=True)
class CollectionProofReportValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def write_collection_proof_report(collection_summary_path: Path, out_path: Path) -> CollectionProofReportValidation:
    summary = read_json(collection_summary_path)
    text = render_collection_proof_report(summary)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(text, encoding="utf-8")
    return validate_collection_proof_report(out_path, collection_summary_path=collection_summary_path)


def render_collection_proof_report(summary: dict[str, Any]) -> str:
    artifacts = summary.get("artifacts") if isinstance(summary.get("artifacts"), dict) else {}
    privacy = summary.get("privacy") if isinstance(summary.get("privacy"), dict) else {}
    tls = privacy.get("tls_verification") if isinstance(privacy.get("tls_verification"), dict) else {}
    governance = summary.get("governance") if isinstance(summary.get("governance"), dict) else {}
    intake = governance.get("assessment_intake") if isinstance(governance.get("assessment_intake"), dict) else {}
    checks = [check for check in (summary.get("checks") or []) if isinstance(check, dict)]

    lines = [
        "# Source Collection Proof Report",
        "",
        f"- Report schema: `{COLLECTION_PROOF_REPORT_SCHEMA_VERSION}`.",
        f"- Collection summary schema: `{summary.get('schema_version') or 'missing'}`.",
        f"- Collection status: `{summary.get('status') or 'missing'}`.",
        f"- Generated at: `{summary.get('generated_at') or 'unknown'}`.",
        "",
        "## Collection Status",
        "",
        "- This report summarizes approved source collection proof without serializing endpoint URLs, usernames, passwords, tokens, hostnames, IP addresses, or customer contact values.",
        "- Use the JSON artifacts as the authoritative machine proof; use this Markdown report for operator, partner, and change-board review.",
        "",
        "## Read-Only Evidence",
        "",
    ]
    for check in checks:
        lines.append(
            "- "
            + f"`{check.get('name') or 'unknown'}`: "
            + f"status=`{check.get('status') or 'missing'}`, "
            + metric_text(check)
            + f", mutating_calls={check.get('mutating_calls')}, "
            + f"tls_verification=`{check.get('tls_verification') or 'missing'}`, "
            + f"api_paths=`{', '.join(str(path) for path in check.get('api_paths') or []) or 'none'}`."
        )
    if not checks:
        lines.append("- No collection checks were present in the summary.")

    lines.extend(
        [
            "",
            "## Privacy Posture",
            "",
            f"- credentials_serialized={str(privacy.get('credentials_serialized')).lower()}.",
            f"- endpoint_values_serialized={str(privacy.get('endpoint_values_serialized')).lower()}.",
            f"- summary_redacted={str(privacy.get('summary_redacted')).lower()}.",
            f"- TLS verification: vCenter=`{tls.get('vcenter') or 'missing'}`, Prism Central=`{tls.get('prism-central') or 'missing'}`.",
            "",
            "## Assessment Intake Binding",
            "",
            f"- Intake status: `{intake.get('status') or 'not_supplied'}`.",
            f"- Intake schema: `{intake.get('schema_version') or 'missing'}`.",
            f"- Intake rows: `{intake.get('rows') if intake.get('rows') is not None else 'missing'}`.",
            f"- Intake checksum present: `{bool(intake.get('source_sha256'))}`.",
            f"- Intake values serialized: `{str(intake.get('values_serialized')).lower()}`.",
            "",
            "## Artifact Manifest",
            "",
        ]
    )
    for key in sorted(artifacts):
        value = artifacts.get(key)
        if isinstance(value, str):
            lines.append(f"- `{key}`: `{value}`.")
    if "collection_proof_manifest" not in artifacts:
        lines.append("- `collection_proof_manifest`: `missing`.")

    lines.extend(
        [
            "",
            "## Stop Conditions",
            "",
            "- Stop if any collection check reports a non-pass status or `mutating_calls` greater than zero.",
            "- Stop if `credentials_serialized=false`, `endpoint_values_serialized=false`, or `summary_redacted=true` is not preserved.",
            "- Stop if `collection-proof-manifest.json` is missing or `validate-live-proof` does not pass against the source directory.",
            "- Stop if the report contains endpoint URLs, usernames, passwords, tokens, hostnames, IP addresses, or secret-like assignments.",
            "",
        ]
    )
    return "\n".join(lines)


def validate_collection_proof_report(
    report_path: Path,
    *,
    collection_summary_path: Path | None = None,
) -> CollectionProofReportValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    try:
        text = report_path.read_text(encoding="utf-8")
    except OSError as exc:
        return CollectionProofReportValidation("fail", 1, (f"{report_path}: could not read report: {exc}",), ())

    findings = scan_text(report_path.name, text)
    checks += 1
    errors.extend(f"Collection proof report leak: {finding}" for finding in findings)

    for section in REQUIRED_SECTIONS:
        checks += 1
        if section not in text:
            errors.append(f"Collection proof report missing required section: {section}")
    for fragment in REQUIRED_FRAGMENTS:
        checks += 1
        if fragment not in text:
            errors.append(f"Collection proof report missing required reference: {fragment}")

    if collection_summary_path:
        summary = read_json(collection_summary_path)
        summary_errors, summary_warnings, summary_checks = validate_report_against_summary(text, summary)
        checks += summary_checks
        errors.extend(summary_errors)
        warnings.extend(summary_warnings)

    return CollectionProofReportValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def validate_report_against_summary(text: str, summary: dict[str, Any]) -> tuple[list[str], list[str], int]:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    checks += 1
    if summary.get("schema_version") != COLLECTION_SUMMARY_SCHEMA_VERSION:
        errors.append(f"collection summary schema_version must be {COLLECTION_SUMMARY_SCHEMA_VERSION}")
    checks += 1
    if summary.get("status") != "pass":
        errors.append("collection summary status must be pass")

    privacy = summary.get("privacy") if isinstance(summary.get("privacy"), dict) else {}
    for key, expected in (
        ("credentials_serialized", False),
        ("endpoint_values_serialized", False),
        ("summary_redacted", True),
    ):
        checks += 1
        if privacy.get(key) is not expected:
            errors.append(f"collection summary privacy.{key} must be {expected}")
    checks += 1
    if "collection-proof-manifest.json" not in text:
        errors.append("collection proof report must reference collection-proof-manifest.json")

    for check in summary.get("checks") or []:
        if not isinstance(check, dict):
            continue
        name = str(check.get("name") or "")
        checks += 1
        if name and name not in text:
            errors.append(f"collection proof report missing collection check: {name}")
        checks += 1
        if check.get("status") != "pass":
            errors.append(f"{name or 'collection check'} status must be pass")
        checks += 1
        if int_value(check.get("mutating_calls")) != 0:
            errors.append(f"{name or 'collection check'} must report mutating_calls=0")

    intake = (
        summary.get("governance", {}).get("assessment_intake")
        if isinstance(summary.get("governance"), dict)
        else None
    )
    checks += 1
    if not isinstance(intake, dict) or intake.get("status") != "pass" or intake.get("values_serialized") is not False:
        errors.append("collection proof report requires validated assessment intake proof with no serialized values")
    if isinstance(intake, dict) and not intake.get("source_sha256"):
        warnings.append("collection proof report intake checksum was not present")

    return errors, warnings, checks


def metric_text(check: dict[str, Any]) -> str:
    for key in ("workloads", "networks", "targets"):
        if key in check:
            return f"{key}=`{check.get(key)}`"
    return "items=`not_reported`"


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: JSON root must be an object")
    return payload


def int_value(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return -1
