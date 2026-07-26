from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import WorkloadAssessment


REQUIRED_SECTIONS = (
    "# Source Endpoint Evidence Request",
    "## Purpose",
    "## Requested Source Scope",
    "## Workload Context",
    "## Required Controls",
    "## Evidence To Capture",
    "## Closeout Commands",
    "## Stop Conditions",
)

REQUIRED_FRAGMENTS = (
    "vCenter",
    "Prism Central",
    "read-only",
    "mutating_calls=0",
    "credentials_serialized=false",
    "endpoint_values_serialized=false",
    "live-readiness",
    "assessment-intake",
    "validate-assessment-intake",
    "collect-sources",
    "--assessment-intake",
    "validate-live-proof",
    "--require-vcenter",
    "--require-prism",
    "nmrcp_live_endpoint_proof_v1",
)


@dataclass(frozen=True)
class SourceEndpointEvidenceRequestValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def write_source_endpoint_evidence_request(assessments: list[WorkloadAssessment], path: Path) -> Path:
    owners = sorted({assessment.owner for assessment in assessments if assessment.owner and assessment.owner != "Unassigned"})
    readiness_counts = {status: sum(1 for item in assessments if item.readiness == status) for status in ("ready", "research", "prepare", "blocked")}
    lines = [
        "# Source Endpoint Evidence Request",
        "",
        "## Purpose",
        "",
        "Request an approved read-only vCenter and Prism Central validation window for NMRCP source collection.",
        "This request exists so operators can prove live endpoint access and collection safety without exposing credentials, endpoint values, or raw customer identifiers in the proof file.",
        "",
        "## Requested Source Scope",
        "",
        "- vCenter: approved source inventory endpoint, read-only collection only.",
        "- Prism Central: approved target/reference inventory endpoint, read-only list collection only.",
        "- vCenter calls: `/api/session`, `/api/vcenter/vm`, and `/api/vcenter/network`.",
        "- Prism Central calls: `/api/nutanix/v3/vms/list` and `/api/nutanix/v3/clusters/list`.",
        "- Mutation allowance: none; require `mutating_calls=0`.",
        "- Privacy requirements: `credentials_serialized=false` and `endpoint_values_serialized=false`.",
        "",
        "## Workload Context",
        "",
        f"- Current assessment workloads: `{len(assessments)}`.",
        f"- Readiness counts: `ready={readiness_counts['ready']}`, `research={readiness_counts['research']}`, `prepare={readiness_counts['prepare']}`, `blocked={readiness_counts['blocked']}`.",
        f"- Workload owners represented: `{', '.join(owners) if owners else 'Unassigned only'}`.",
        "",
        "## Required Controls",
        "",
        "- Store endpoint URLs, usernames, and passwords only in local environment variables or secure prompts.",
        "- Do not commit, package, or paste endpoint URLs, usernames, passwords, tokens, FQDNs, IP addresses, or support bundles.",
        "- Keep source inventory outputs in the approved migration workspace.",
        "- Complete and validate `assessment-intake.csv` before live collection.",
        "- Validate collection audit metadata before assessment or handoff.",
        "- Stop if a connector attempts any mutating vCenter, Prism Central, AHV, NC2, or Nutanix Move operation.",
        "",
        "## Evidence To Capture",
        "",
        "- `nmrcp_live_readiness_v1` from strict `live-readiness` with vCenter and Prism required.",
        "- Completed `nmrcp_assessment_intake_v1` with local-safety acknowledgements set to `true`.",
        "- `nmrcp_collection_summary_v1` with read-only checks and `mutating_calls=0`.",
        "- `vcenter-inventory.json` with collection audit metadata.",
        "- `vcenter-networks.json` with read-only network inventory evidence.",
        "- `prism-inventory.json` with collection audit metadata.",
        "- `prism-capacity.json` from Prism Central cluster list evidence.",
        "- `nmrcp_live_endpoint_proof_v1` from `validate-live-proof`.",
        "",
        "## Closeout Commands",
        "",
        "Run these from the repository root during an approved read-only validation window:",
        "",
        "```powershell",
        "python -m nmrcp.cli live-readiness `",
        "  --require-vcenter `",
        "  --require-prism `",
        "  --out outputs\\source-collection\\live-readiness.json",
        "",
        "python -m nmrcp.cli validate-assessment-intake `",
        "  --intake outputs\\assessment-intake.csv",
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
        "## Stop Conditions",
        "",
        "- Stop if vCenter or Prism Central scope is not approved for read-only validation.",
        "- Stop if `validate-assessment-intake` does not pass before source collection.",
        "- Stop if any output serializes credentials, endpoint values, usernames, FQDNs, IP addresses, tokens, or passwords.",
        "- Stop if collection summary or inventory audit reports any mutating call.",
        "- Stop if `validate-live-proof` does not produce `nmrcp_live_endpoint_proof_v1` with `status=pass`.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def validate_source_endpoint_evidence_request(path: Path) -> SourceEndpointEvidenceRequestValidation:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return SourceEndpointEvidenceRequestValidation("fail", 1, (f"{path}: could not read source endpoint evidence request: {exc}",), ())

    errors: list[str] = []
    checks = 0
    for section in REQUIRED_SECTIONS:
        checks += 1
        if section not in text:
            errors.append(f"Source endpoint evidence request missing required section: {section}")
    for fragment in REQUIRED_FRAGMENTS:
        checks += 1
        if fragment not in text:
            errors.append(f"Source endpoint evidence request missing required proof request reference: {fragment}")

    checks += 1
    if "password" not in text.lower() or "token" not in text.lower():
        errors.append("Source endpoint evidence request must include credential and token handling controls")
    checks += 1
    if "mutating" not in text.lower():
        errors.append("Source endpoint evidence request must include mutation stop conditions")

    return SourceEndpointEvidenceRequestValidation("pass" if not errors else "fail", checks, tuple(errors), ())
