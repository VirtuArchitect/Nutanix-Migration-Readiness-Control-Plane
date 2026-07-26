from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .github_readiness import DEFAULT_REPO_URL, validate_github_publication_review
from .product_readiness import validate_product_readiness_report
from .publication_handoff import validate_publication_handoff
from .publication_staging import validate_publication_staging_manifest
from .vault_readiness import DEFAULT_VAULT_PATH


PULL_REQUEST_READINESS_SCHEMA_VERSION = "nmrcp_pull_request_readiness_v1"


@dataclass(frozen=True)
class PullRequestReadinessCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class PullRequestReadiness:
    status: str
    repo_root: str
    checks: tuple[PullRequestReadinessCheck, ...]
    next_actions: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.status == "ready_after_operator_staging"

    def summary(self) -> str:
        errors = sum(1 for check in self.checks if check.status == "fail")
        return f"{self.status}: checks={len(self.checks)}, errors={errors}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PULL_REQUEST_READINESS_SCHEMA_VERSION,
            "status": self.status,
            "repo_root": self.repo_root,
            "checks": [check.to_dict() for check in self.checks],
            "next_actions": list(self.next_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Pull Request Readiness Packet",
            "",
            f"- Status: `{self.status}`",
            f"- Repository root: `{self.repo_root}`",
            f"- Check count: `{len(self.checks)}`",
            "",
            "## Checks",
            "",
            "| Status | Check | Detail |",
            "| --- | --- | --- |",
        ]
        for check in self.checks:
            lines.append(f"| `{check.status}` | `{check.name}` | {escape_markdown_cell(check.detail)} |")
        lines.extend(["", "## Next Actions", ""])
        for action in self.next_actions:
            lines.append(f"- {action}")
        lines.extend(
            [
                "",
                "## Operator Boundaries",
                "",
                "- This packet did not stage, commit, push, publish, open a pull request, or mutate infrastructure.",
                "- Run the staging command only after operator approval and review of the staging manifest hashes.",
                "- After staging, rerun tests, security scan, smoke, GitHub readiness, and product readiness before opening a pull request.",
                "- Do not claim external handoff readiness until approved endpoint evidence and approved Nutanix Move appliance proof are present.",
                "",
            ]
        )
        return "\n".join(lines)


@dataclass(frozen=True)
class PullRequestReadinessValidation:
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{'PASS' if self.ok else 'FAIL'}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def build_pull_request_readiness(
    repo_root: Path,
    *,
    github_report_path: Path,
    github_json_path: Path,
    product_report_path: Path,
    product_json_path: Path,
    publication_handoff_path: Path,
    publication_handoff_json_path: Path,
    staging_manifest_path: Path,
    staging_manifest_json_path: Path,
    smoke_log_path: Path,
    security_scan_status: str,
    vault_path: Path = DEFAULT_VAULT_PATH,
    expected_remote: str = DEFAULT_REPO_URL,
    ignored_staging_forbidden_paths: tuple[Path, ...] = (),
) -> PullRequestReadiness:
    root = repo_root.resolve()
    checks = [
        github_review_check(root, github_report_path, github_json_path, expected_remote),
        product_report_check(root, product_report_path, product_json_path, github_report_path, github_json_path, vault_path, expected_remote),
        handoff_check(
            root,
            publication_handoff_path,
            publication_handoff_json_path,
            github_report_path,
            github_json_path,
            product_report_path,
            product_json_path,
            smoke_log_path,
            security_scan_status,
            vault_path,
            expected_remote,
        ),
        staging_manifest_check(root, staging_manifest_path, staging_manifest_json_path, ignored_staging_forbidden_paths),
        security_scan_check(security_scan_status),
    ]
    status = "blocked" if any(check.status == "fail" for check in checks) else "ready_after_operator_staging"
    return PullRequestReadiness(status, str(root), tuple(checks), next_actions(status))


def validate_pull_request_readiness(
    repo_root: Path,
    json_report_path: Path,
    *,
    markdown_report_path: Path | None = None,
    github_report_path: Path,
    github_json_path: Path,
    product_report_path: Path,
    product_json_path: Path,
    publication_handoff_path: Path,
    publication_handoff_json_path: Path,
    staging_manifest_path: Path,
    staging_manifest_json_path: Path,
    smoke_log_path: Path,
    security_scan_status: str,
    vault_path: Path = DEFAULT_VAULT_PATH,
    expected_remote: str = DEFAULT_REPO_URL,
) -> PullRequestReadinessValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    ignored_staging_forbidden_paths = (json_report_path,) if not markdown_report_path else (json_report_path, markdown_report_path)
    expected = build_pull_request_readiness(
        repo_root,
        github_report_path=github_report_path,
        github_json_path=github_json_path,
        product_report_path=product_report_path,
        product_json_path=product_json_path,
        publication_handoff_path=publication_handoff_path,
        publication_handoff_json_path=publication_handoff_json_path,
        staging_manifest_path=staging_manifest_path,
        staging_manifest_json_path=staging_manifest_json_path,
        smoke_log_path=smoke_log_path,
        security_scan_status=security_scan_status,
        vault_path=vault_path,
        expected_remote=expected_remote,
        ignored_staging_forbidden_paths=ignored_staging_forbidden_paths,
    )
    expected_payload = expected.to_dict()
    checks += 1
    try:
        payload = json.loads(json_report_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validation returns data.
        return PullRequestReadinessValidation(checks, (f"Pull request readiness JSON is unreadable: {exc}",), ())
    if not isinstance(payload, dict):
        return PullRequestReadinessValidation(checks, ("Pull request readiness JSON must be an object",), ())
    checks += 1
    if payload.get("schema_version") != PULL_REQUEST_READINESS_SCHEMA_VERSION:
        errors.append(f"Pull request readiness schema_version must be {PULL_REQUEST_READINESS_SCHEMA_VERSION}")
    for key in ("status", "repo_root", "checks", "next_actions"):
        checks += 1
        if payload.get(key) != expected_payload[key]:
            errors.append(f"Pull request readiness JSON field {key} does not match current PR readiness inputs")
    if markdown_report_path:
        checks += 1
        try:
            markdown = markdown_report_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - validation returns data.
            errors.append(f"Pull request readiness Markdown is unreadable: {exc}")
        else:
            for fragment in required_markdown_fragments(expected):
                checks += 1
                if fragment not in markdown:
                    errors.append(f"Pull request readiness Markdown missing required text: {fragment}")
    return PullRequestReadinessValidation(checks, tuple(errors), tuple(warnings))


def github_review_check(root: Path, markdown_path: Path, json_path: Path, expected_remote: str) -> PullRequestReadinessCheck:
    result = validate_github_publication_review(root, json_path, markdown_report_path=markdown_path, expected_remote=expected_remote)
    return PullRequestReadinessCheck("github-publication-review", "pass" if result.ok else "fail", result.summary() if result.ok else "; ".join(result.errors))


def product_report_check(
    root: Path,
    markdown_path: Path,
    json_path: Path,
    github_report_path: Path,
    github_json_path: Path,
    vault_path: Path,
    expected_remote: str,
) -> PullRequestReadinessCheck:
    result = validate_product_readiness_report(
        root,
        json_path,
        markdown_report_path=markdown_path,
        vault_path=vault_path,
        expected_remote=expected_remote,
        github_publication_review_path=github_report_path,
        github_publication_review_json_path=github_json_path,
    )
    return PullRequestReadinessCheck("product-readiness-report", "pass" if result.ok else "fail", result.summary() if result.ok else "; ".join(result.errors))


def handoff_check(
    root: Path,
    markdown_path: Path,
    json_path: Path,
    github_report_path: Path,
    github_json_path: Path,
    product_report_path: Path,
    product_json_path: Path,
    smoke_log_path: Path,
    security_scan_status: str,
    vault_path: Path,
    expected_remote: str,
) -> PullRequestReadinessCheck:
    result = validate_publication_handoff(
        root,
        json_path,
        markdown_report_path=markdown_path,
        github_report_path=github_report_path,
        github_json_path=github_json_path,
        product_report_path=product_report_path,
        product_json_path=product_json_path,
        smoke_log_path=smoke_log_path,
        security_scan_status=security_scan_status,
        vault_path=vault_path,
        expected_remote=expected_remote,
    )
    return PullRequestReadinessCheck("publication-handoff", "pass" if result.ok else "fail", result.summary() if result.ok else "; ".join(result.errors))


def staging_manifest_check(root: Path, markdown_path: Path, json_path: Path, ignored_forbidden_paths: tuple[Path, ...] = ()) -> PullRequestReadinessCheck:
    result = validate_publication_staging_manifest(root, json_path, markdown_report_path=markdown_path, ignored_forbidden_paths=ignored_forbidden_paths)
    if not result.ok and ignored_forbidden_paths:
        exact_result = validate_publication_staging_manifest(root, json_path, markdown_report_path=markdown_path)
        if exact_result.ok:
            return PullRequestReadinessCheck("publication-staging-manifest", "pass", exact_result.summary())
    return PullRequestReadinessCheck("publication-staging-manifest", "pass" if result.ok else "fail", result.summary() if result.ok else "; ".join(result.errors))


def security_scan_check(status: str) -> PullRequestReadinessCheck:
    normalized = status.strip().lower()
    if normalized not in {"pass", "passed"}:
        return PullRequestReadinessCheck("security-scan", "fail", f"security scan status is {status!r}; expected pass")
    return PullRequestReadinessCheck("security-scan", "pass", "Security scan passed: no disallowed secret patterns found")


def next_actions(status: str) -> tuple[str, ...]:
    if status == "blocked":
        return ("Regenerate or fix failed PR readiness inputs, then rerun pull-request-readiness.",)
    return (
        "Review the pull request readiness packet and publication staging manifest with the branch owner.",
        "After operator approval, run the manifest staging command, then rerun full tests, security scan, smoke, github-readiness, product-readiness, and this PR readiness packet.",
        "Commit, push, and open a pull request only after the post-staging gates pass.",
        "Keep external handoff claims blocked until approved endpoint evidence and approved Nutanix Move appliance proof are present.",
    )


def required_markdown_fragments(expected: PullRequestReadiness) -> tuple[str, ...]:
    fragments = [
        "# Pull Request Readiness Packet",
        f"- Status: `{expected.status}`",
        f"- Repository root: `{expected.repo_root}`",
        f"- Check count: `{len(expected.checks)}`",
        "## Checks",
        "## Next Actions",
        "## Operator Boundaries",
        "This packet did not stage, commit, push, publish, open a pull request, or mutate infrastructure.",
        "Run the staging command only after operator approval and review of the staging manifest hashes.",
        "After staging, rerun tests, security scan, smoke, GitHub readiness, and product readiness before opening a pull request.",
        "Do not claim external handoff readiness until approved endpoint evidence and approved Nutanix Move appliance proof are present.",
    ]
    fragments.extend(f"| `{check.status}` | `{check.name}` | {escape_markdown_cell(check.detail)} |" for check in expected.checks)
    fragments.extend(f"- {action}" for action in expected.next_actions)
    return tuple(fragments)


def escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
