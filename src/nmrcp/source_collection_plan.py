from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .assessment_intake import ASSESSMENT_INTAKE_SCHEMA_VERSION, validate_assessment_intake, read_rows


SOURCE_COLLECTION_PLAN_SCHEMA_VERSION = "nmrcp_source_collection_plan_v1"
SECRET_OR_ENDPOINT_RE = re.compile(
    r"(?i)(https?://|password\s*[:=]|passwd\s*[:=]|token\s*[:=]|secret\s*[:=]|api[_-]?key\s*[:=]|authorization\s*[:=])"
)


@dataclass(frozen=True)
class SourceCollectionPlanValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def write_source_collection_plan(intake_path: Path, out_path: Path) -> SourceCollectionPlanValidation:
    validation = validate_assessment_intake(intake_path)
    if not validation.ok:
        return SourceCollectionPlanValidation(
            "fail",
            1,
            tuple(f"Assessment intake invalid: {error}" for error in validation.errors),
            validation.warnings,
        )
    rows = read_rows(intake_path, [])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render_source_collection_plan(intake_path, rows, validation.warnings), encoding="utf-8")
    return validate_source_collection_plan(out_path, intake_path)


def validate_source_collection_plan(plan_path: Path, intake_path: Path) -> SourceCollectionPlanValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    try:
        actual = plan_path.read_text(encoding="utf-8")
    except OSError as exc:
        return SourceCollectionPlanValidation("fail", 1, (f"{plan_path}: could not read source collection plan: {exc}",), ())

    intake_validation = validate_assessment_intake(intake_path)
    checks += 1
    if not intake_validation.ok:
        errors.extend(f"Assessment intake invalid: {error}" for error in intake_validation.errors)
        return SourceCollectionPlanValidation("fail", checks, tuple(errors), intake_validation.warnings)

    rows = read_rows(intake_path, errors)
    checks += 1
    if errors:
        return SourceCollectionPlanValidation("fail", checks, tuple(errors), tuple(warnings))
    expected = render_source_collection_plan(intake_path, rows, intake_validation.warnings)

    static_validation = validate_source_collection_plan_text(actual)
    checks += static_validation.checks
    errors.extend(static_validation.errors)

    checks += 1
    if normalize_text(actual) != normalize_text(expected):
        errors.append("Source collection plan does not match assessment intake")

    warnings.extend(intake_validation.warnings)
    return SourceCollectionPlanValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def validate_source_collection_plan_text(text: str) -> SourceCollectionPlanValidation:
    errors: list[str] = []
    checks = 0
    for required in (
        "# Source Collection Plan",
        SOURCE_COLLECTION_PLAN_SCHEMA_VERSION,
        "## Approved Scope",
        "## Local Secret Handling",
        "## Read-Only Collection Sequence",
        "## Required Proof Outputs",
        "## Stop Conditions",
        "credentials_serialized=false",
        "endpoint_values_serialized=false",
        "python -m nmrcp.cli live-readiness",
        "python -m nmrcp.cli collect-sources",
        "python -m nmrcp.cli validate-live-proof",
    ):
        checks += 1
        if required not in text:
            errors.append(f"Source collection plan missing required text: {required}")

    checks += 1
    if SECRET_OR_ENDPOINT_RE.search(text):
        allowed_fragments = (
            "credentials_serialized=false",
            "endpoint_values_serialized=false",
        )
        scrubbed = text
        for fragment in allowed_fragments:
            scrubbed = scrubbed.replace(fragment, "")
        if SECRET_OR_ENDPOINT_RE.search(scrubbed):
            errors.append("Source collection plan contains endpoint or secret-like material")

    checks += 1
    if "vcenter01.corp.local" in text or "prism-central.example.com" in text:
        errors.append("Source collection plan leaked sample endpoint hostname")

    return SourceCollectionPlanValidation("pass" if not errors else "fail", checks, tuple(errors), ())


def render_source_collection_plan(
    intake_path: Path,
    rows: list[dict[str, str]],
    intake_warnings: tuple[str, ...] = (),
) -> str:
    intake = intake_by_field(rows)
    lines = [
        "# Source Collection Plan",
        "",
        f"Schema: `{SOURCE_COLLECTION_PLAN_SCHEMA_VERSION}`",
        f"Intake schema: `{ASSESSMENT_INTAKE_SCHEMA_VERSION}`",
        f"Intake file: `{intake_path.name}`",
        "",
        "## Approved Scope",
        "",
        f"- Program: {safe_value(intake, 'customer_or_program')}",
        f"- Assessment owner: {safe_value(intake, 'assessment_owner')}",
        f"- Migration target: `{safe_value(intake, 'migration_target')}`",
        f"- Source scope: {safe_value(intake, 'source_scope')}",
        f"- Target scope: {safe_value(intake, 'target_scope')}",
        f"- Dependency source: {safe_value(intake, 'dependency_source')}",
        f"- Planned assessment window: {safe_value(intake, 'planned_assessment_window')}",
        f"- RVTools export available: `{safe_value(intake, 'rvtools_export_available')}`",
        f"- Approved Move lab available: `{safe_value(intake, 'approved_move_lab_available')}`",
        "",
        "## Local Secret Handling",
        "",
        "- Store vCenter and Prism Central endpoint URLs, usernames, and passwords only in local environment variables or secure prompts.",
        "- Do not paste endpoint URLs, usernames, passwords, tokens, API keys, support bundles, FQDNs, or IP addresses into this plan.",
        "- Required privacy posture: `credentials_serialized=false` and `endpoint_values_serialized=false`.",
        "- Keep generated source inventory in the approved migration workspace.",
        "",
        "## Read-Only Collection Sequence",
        "",
        "```powershell",
        "$env:PYTHONPATH = \"src\"",
        "python -m nmrcp.cli validate-assessment-intake `",
        "  --intake outputs\\assessment-intake.csv",
        "",
        "python -m nmrcp.cli live-readiness `",
        "  --require-vcenter `",
        "  --require-prism `",
        "  --out outputs\\source-collection\\live-readiness.json",
        "",
        "python -m nmrcp.cli collect-sources `",
        "  --assessment-intake outputs\\assessment-intake.csv `",
        "  --out-dir outputs\\source-collection",
        "",
        "python -m nmrcp.cli validate-live-proof `",
        "  --live-readiness outputs\\source-collection\\live-readiness.json `",
        "  --collection-summary outputs\\source-collection\\collection-summary.json `",
        "  --source-dir outputs\\source-collection `",
        "  --out outputs\\source-collection\\live-proof-validation.json",
        "```",
        "",
        "## Required Proof Outputs",
        "",
        "- `live-readiness.json`: redacted endpoint readiness proof with read-only call names and counts.",
        "- `collection-summary.json`: redacted collection summary with `mutating_calls=0` and intake checksum binding.",
        "- `collection-proof-manifest.json`: redacted artifact checksum manifest and read-only API allowlist.",
        "- `vcenter-inventory.json`: local source inventory for assessment.",
        "- `vcenter-networks.json`: local source network evidence.",
        "- `prism-inventory.json`: local Prism reference inventory.",
        "- `prism-capacity.json`: local target capacity draft.",
        "- `live-proof-validation.json`: `nmrcp_live_endpoint_proof_v1` validation output.",
        "",
        "## Stop Conditions",
        "",
        "- Stop if `validate-assessment-intake` does not pass.",
        "- Stop if live readiness or collection output serializes endpoint values, usernames, passwords, tokens, FQDNs, or IP addresses.",
        "- Stop if any connector attempts a mutating vCenter, Prism Central, AHV, NC2, or Nutanix Move operation.",
        "- Stop if TLS verification is disabled outside an approved exception or loopback simulator smoke.",
        "- Stop if `validate-live-proof` does not produce `status=pass` for approved external proof closeout.",
    ]
    if intake_warnings:
        lines.extend(["", "## Intake Warnings", ""])
        lines.extend(f"- {warning}" for warning in intake_warnings)
    return "\n".join(lines) + "\n"


def intake_by_field(rows: list[dict[str, str]]) -> dict[str, str]:
    return {str(row.get("field") or ""): str(row.get("value") or "") for row in rows}


def safe_value(intake: dict[str, str], field: str) -> str:
    value = (intake.get(field) or "").strip()
    return value if value else "not supplied"


def normalize_text(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.strip().splitlines())
