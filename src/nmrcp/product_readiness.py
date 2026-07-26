from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .github_readiness import DEFAULT_REPO_URL, check_github_readiness, validate_github_publication_review
from .mvp_audit import audit_mvp
from .mvp_proof_bundle import verify_mvp_proof_package
from .publication_staging import validate_publication_staging_manifest
from .vault_readiness import DEFAULT_VAULT_PATH, check_vault_readiness


PRODUCT_READINESS_SCHEMA_VERSION = "nmrcp_product_readiness_v1"


@dataclass(frozen=True)
class ProductGate:
    name: str
    status: str
    summary: str
    blockers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "summary": self.summary,
            "blockers": list(self.blockers),
        }


@dataclass(frozen=True)
class ProductReadiness:
    status: str
    repo_root: str
    gates: tuple[ProductGate, ...]
    next_actions: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    def summary(self) -> str:
        counts = {"pass": 0, "partial": 0, "fail": 0}
        for gate in self.gates:
            counts[gate.status] = counts.get(gate.status, 0) + 1
        return f"{self.status.upper()}: gates={len(self.gates)}, fail={counts['fail']}, partial={counts['partial']}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PRODUCT_READINESS_SCHEMA_VERSION,
            "status": self.status,
            "repo_root": self.repo_root,
            "gates": [gate.to_dict() for gate in self.gates],
            "next_actions": list(self.next_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Product Readiness Report",
            "",
            f"- Status: `{self.status}`",
            f"- Repository root: `{self.repo_root}`",
            f"- Gate count: `{len(self.gates)}`",
            "",
            "## Gates",
            "",
            "| Status | Gate | Summary |",
            "| --- | --- | --- |",
        ]
        for gate in self.gates:
            lines.append(f"| `{gate.status}` | `{gate.name}` | {escape_markdown_cell(gate.summary)} |")
        lines.extend(["", "## Blockers", ""])
        blockers = [(gate.name, blocker) for gate in self.gates for blocker in gate.blockers]
        if blockers:
            for gate_name, blocker in blockers:
                lines.append(f"- `{gate_name}`: {blocker}")
        else:
            lines.append("- None")
        lines.extend(["", "## Next Actions", ""])
        for action in self.next_actions:
            lines.append(f"- {action}")
        lines.extend(
            [
                "",
                "## Completion Boundary",
                "",
                "- This report did not contact vCenter, Prism Central, or Nutanix Move.",
                "- This report did not stage, commit, push, publish, or mutate infrastructure.",
                "- Do not claim external handoff readiness until every gate passes with approved endpoint and Nutanix Move evidence.",
                "",
            ]
        )
        return "\n".join(lines)


@dataclass(frozen=True)
class ProductReadinessReportValidation:
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{'PASS' if self.ok else 'FAIL'}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def check_product_readiness(
    repo_root: Path,
    *,
    vault_path: Path = DEFAULT_VAULT_PATH,
    expected_remote: str = DEFAULT_REPO_URL,
    assessment_dir: Path | None = None,
    assessment_intake_path: Path | None = None,
    live_proof_path: Path | None = None,
    move_proof_path: Path | None = None,
    evidence_bundle_path: Path | None = None,
    validation_results_path: Path | None = None,
    remediation_tracker_path: Path | None = None,
    signoffs_path: Path | None = None,
    approval_exceptions_path: Path | None = None,
    operator_review_path: Path | None = None,
    move_lab_capture_validation_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
    warning_acceptance_path: Path | None = None,
    mvp_proof_package_path: Path | None = None,
    github_publication_review_path: Path | None = None,
    github_publication_review_json_path: Path | None = None,
    publication_staging_manifest_path: Path | None = None,
    publication_staging_manifest_json_path: Path | None = None,
    publication_staging_ignored_paths: tuple[Path, ...] = (),
) -> ProductReadiness:
    root = repo_root.resolve()
    mvp = audit_mvp(
        root,
        assessment_dir=assessment_dir,
        assessment_intake_path=assessment_intake_path,
        live_proof_path=live_proof_path,
        move_proof_path=move_proof_path,
        evidence_bundle_path=evidence_bundle_path,
        validation_results_path=validation_results_path,
        remediation_tracker_path=remediation_tracker_path,
        signoffs_path=signoffs_path,
        approval_exceptions_path=approval_exceptions_path,
        operator_review_path=operator_review_path,
        move_lab_capture_validation_path=move_lab_capture_validation_path,
        move_lab_evidence_intake_path=move_lab_evidence_intake_path,
        warning_acceptance_path=warning_acceptance_path,
    )
    github = check_github_readiness(root, expected_remote=expected_remote)
    vault = check_vault_readiness(root, vault_path=vault_path)
    gates = [
        ProductGate(
            "mvp-audit",
            normalize_status(mvp.status),
            mvp.summary(),
            tuple(
                f"{requirement.id}: {item}"
                for requirement in mvp.requirements
                for item in (*requirement.errors, *requirement.warnings)
            ),
        ),
        ProductGate(
            "github-readiness",
            normalize_status(github.status),
            github.summary(),
            tuple(f"{check.name}: {check.detail}" for check in github.checks if check.status == "fail"),
        ),
        ProductGate(
            "vault-readiness",
            normalize_status(vault.status),
            vault.summary(),
            tuple(f"{check.name}: {check.detail}" for check in vault.checks if check.status == "fail"),
        ),
    ]
    if mvp_proof_package_path:
        gates.append(mvp_proof_package_gate(mvp_proof_package_path))
    if github_publication_review_path or github_publication_review_json_path:
        gates.append(publication_review_gate(root, github_publication_review_path, github_publication_review_json_path, expected_remote))
    if publication_staging_manifest_path or publication_staging_manifest_json_path:
        gates.append(
            publication_staging_gate(
                root,
                publication_staging_manifest_path,
                publication_staging_manifest_json_path,
                ignored_forbidden_paths=publication_staging_ignored_paths,
            )
        )
    gate_tuple = tuple(gates)
    if any(gate.status == "fail" for gate in gate_tuple):
        status = "fail"
    elif any(gate.status == "partial" for gate in gate_tuple):
        status = "partial"
    else:
        status = "pass"
    return ProductReadiness(status, str(root), gate_tuple, next_actions(gate_tuple, github.next_actions))


def validate_product_readiness_report(
    repo_root: Path,
    json_report_path: Path,
    *,
    markdown_report_path: Path | None = None,
    vault_path: Path = DEFAULT_VAULT_PATH,
    expected_remote: str = DEFAULT_REPO_URL,
    assessment_dir: Path | None = None,
    assessment_intake_path: Path | None = None,
    live_proof_path: Path | None = None,
    move_proof_path: Path | None = None,
    evidence_bundle_path: Path | None = None,
    validation_results_path: Path | None = None,
    remediation_tracker_path: Path | None = None,
    signoffs_path: Path | None = None,
    approval_exceptions_path: Path | None = None,
    operator_review_path: Path | None = None,
    move_lab_capture_validation_path: Path | None = None,
    move_lab_evidence_intake_path: Path | None = None,
    warning_acceptance_path: Path | None = None,
    mvp_proof_package_path: Path | None = None,
    github_publication_review_path: Path | None = None,
    github_publication_review_json_path: Path | None = None,
    publication_staging_manifest_path: Path | None = None,
    publication_staging_manifest_json_path: Path | None = None,
) -> ProductReadinessReportValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    expected = check_product_readiness(
        repo_root,
        vault_path=vault_path,
        expected_remote=expected_remote,
        assessment_dir=assessment_dir,
        assessment_intake_path=assessment_intake_path,
        live_proof_path=live_proof_path,
        move_proof_path=move_proof_path,
        evidence_bundle_path=evidence_bundle_path,
        validation_results_path=validation_results_path,
        remediation_tracker_path=remediation_tracker_path,
        signoffs_path=signoffs_path,
        approval_exceptions_path=approval_exceptions_path,
        operator_review_path=operator_review_path,
        move_lab_capture_validation_path=move_lab_capture_validation_path,
        move_lab_evidence_intake_path=move_lab_evidence_intake_path,
        warning_acceptance_path=warning_acceptance_path,
        mvp_proof_package_path=mvp_proof_package_path,
        github_publication_review_path=github_publication_review_path,
        github_publication_review_json_path=github_publication_review_json_path,
        publication_staging_manifest_path=publication_staging_manifest_path,
        publication_staging_manifest_json_path=publication_staging_manifest_json_path,
        publication_staging_ignored_paths=tuple(path for path in (markdown_report_path, json_report_path) if path),
    )
    expected_payload = expected.to_dict()
    checks += 1
    try:
        payload = json.loads(json_report_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validation should return errors as data.
        return ProductReadinessReportValidation(checks, (f"Product readiness report JSON is unreadable: {exc}",), ())
    if not isinstance(payload, dict):
        return ProductReadinessReportValidation(checks, ("Product readiness report JSON must be an object",), ())
    checks += 1
    if payload.get("schema_version") != PRODUCT_READINESS_SCHEMA_VERSION:
        errors.append(f"Product readiness report schema_version must be {PRODUCT_READINESS_SCHEMA_VERSION}")
    for key in ("status", "repo_root", "gates", "next_actions"):
        checks += 1
        if payload.get(key) != expected_payload[key]:
            errors.append(f"Product readiness report JSON field {key} does not match current product-readiness")
    if markdown_report_path:
        checks += 1
        try:
            markdown = markdown_report_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - validation should return errors as data.
            errors.append(f"Product readiness report Markdown is unreadable: {exc}")
        else:
            for fragment in required_product_markdown_fragments(expected):
                checks += 1
                if fragment not in markdown:
                    errors.append(f"Product readiness report Markdown missing required text: {fragment}")
    return ProductReadinessReportValidation(checks, tuple(errors), tuple(warnings))


def required_product_markdown_fragments(expected: ProductReadiness) -> tuple[str, ...]:
    fragments = [
        "# Product Readiness Report",
        f"- Status: `{expected.status}`",
        f"- Repository root: `{expected.repo_root}`",
        f"- Gate count: `{len(expected.gates)}`",
        "## Gates",
        "## Blockers",
        "## Next Actions",
        "## Completion Boundary",
        "This report did not contact vCenter, Prism Central, or Nutanix Move.",
        "This report did not stage, commit, push, publish, or mutate infrastructure.",
        "Do not claim external handoff readiness until every gate passes with approved endpoint and Nutanix Move evidence.",
    ]
    fragments.extend(f"| `{gate.status}` | `{gate.name}` | {escape_markdown_cell(gate.summary)} |" for gate in expected.gates)
    blockers = [(gate.name, blocker) for gate in expected.gates for blocker in gate.blockers]
    fragments.extend(f"- `{gate_name}`: {blocker}" for gate_name, blocker in blockers)
    if not blockers:
        fragments.append("- None")
    fragments.extend(f"- {action}" for action in expected.next_actions)
    return tuple(fragments)


def normalize_status(status: str) -> str:
    if status in {"pass", "fail"}:
        return status
    return "partial"


def publication_review_gate(
    repo_root: Path,
    markdown_path: Path | None,
    json_path: Path | None,
    expected_remote: str,
) -> ProductGate:
    if not json_path:
        return ProductGate(
            "github-publication-review",
            "fail",
            "FAIL: JSON publication review path missing",
            ("github-publication-review-json: required when publication review evidence is supplied",),
        )
    result = validate_github_publication_review(
        repo_root,
        json_path,
        markdown_report_path=markdown_path,
        expected_remote=expected_remote,
    )
    return ProductGate(
        "github-publication-review",
        "pass" if result.ok else "fail",
        result.summary(),
        tuple(result.errors),
    )


def publication_staging_gate(
    repo_root: Path,
    markdown_path: Path | None,
    json_path: Path | None,
    *,
    ignored_forbidden_paths: tuple[Path, ...] = (),
) -> ProductGate:
    if not json_path:
        return ProductGate(
            "publication-staging-manifest",
            "fail",
            "FAIL: JSON publication staging manifest path missing",
            ("publication-staging-manifest-json: required when publication staging evidence is supplied",),
        )
    result = validate_publication_staging_manifest(
        repo_root,
        json_path,
        markdown_report_path=markdown_path,
        ignored_forbidden_paths=ignored_forbidden_paths,
    )
    return ProductGate(
        "publication-staging-manifest",
        "pass" if result.ok else "fail",
        result.summary(),
        tuple(result.errors),
    )


def mvp_proof_package_gate(package_path: Path) -> ProductGate:
    try:
        result = verify_mvp_proof_package(package_path)
    except Exception as exc:  # noqa: BLE001 - readiness reports errors as gate data.
        return ProductGate(
            "mvp-proof-package",
            "fail",
            "FAIL: proof package validation raised an exception",
            (f"mvp-proof-package: {exc}",),
        )
    return ProductGate(
        "mvp-proof-package",
        "pass" if result.ok else "fail",
        result.summary(),
        tuple(result.errors),
    )


def next_actions(gates: tuple[ProductGate, ...], github_actions: tuple[str, ...] = ()) -> tuple[str, ...]:
    actions: list[str] = []
    by_name = {gate.name: gate for gate in gates}
    if by_name["github-readiness"].status == "fail":
        actions.extend(github_actions or ("Track, commit, and push required repository files after operator approval; rerun github-readiness.",))
    if "github-publication-review" not in by_name and by_name["github-readiness"].status == "fail":
        actions.append("Generate and validate GitHub publication review artifacts with github-readiness --out and validate-github-publication-review.")
    if by_name.get("github-publication-review") and by_name["github-publication-review"].status == "fail":
        actions.append("Regenerate GitHub publication review artifacts and rerun validate-github-publication-review.")
    if by_name.get("publication-staging-manifest") and by_name["publication-staging-manifest"].status == "fail":
        actions.append("Regenerate and validate the publication staging manifest before operator staging.")
    if by_name.get("mvp-proof-package") and by_name["mvp-proof-package"].status == "fail":
        actions.append("Regenerate and verify the MVP proof package; rerun product-readiness with --mvp-proof-package.")
    if by_name["mvp-audit"].status != "pass":
        actions.append("Supply approved live endpoint and Nutanix Move proof evidence; rerun mvp-audit with proof paths.")
    if by_name["vault-readiness"].status == "fail":
        actions.append("Add missing vault notes or README links; rerun vault-readiness.")
    if not actions:
        actions.append("Run full tests, security scan, smoke, and publication checks before marking the product complete.")
    return tuple(actions)


def escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
