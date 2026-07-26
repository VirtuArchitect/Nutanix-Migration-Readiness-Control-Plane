from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .github_readiness import DEFAULT_REPO_URL, validate_github_publication_review
from .product_readiness import validate_product_readiness_report
from .vault_readiness import DEFAULT_VAULT_PATH


PUBLICATION_HANDOFF_SCHEMA_VERSION = "nmrcp_publication_handoff_v1"


@dataclass(frozen=True)
class PublicationHandoffCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class PublicationHandoff:
    status: str
    repo_root: str
    checks: tuple[PublicationHandoffCheck, ...]
    next_actions: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.status == "ready_for_branch_owner"

    def summary(self) -> str:
        counts = {"pass": 0, "warn": 0, "fail": 0}
        for check in self.checks:
            counts[check.status] = counts.get(check.status, 0) + 1
        return f"{self.status}: checks={len(self.checks)}, errors={counts['fail']}, warnings={counts['warn']}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PUBLICATION_HANDOFF_SCHEMA_VERSION,
            "status": self.status,
            "repo_root": self.repo_root,
            "checks": [check.to_dict() for check in self.checks],
            "next_actions": list(self.next_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Publication Handoff",
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
                "- This handoff did not stage, commit, push, publish, or mutate infrastructure.",
                "- Generated `outputs/` artifacts remain local review evidence and must not be published unless explicitly approved.",
                "- External handoff remains blocked until approved endpoint evidence and approved Nutanix Move appliance proof are present.",
                "",
            ]
        )
        return "\n".join(lines)


@dataclass(frozen=True)
class PublicationHandoffValidation:
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{'PASS' if self.ok else 'FAIL'}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def build_publication_handoff(
    repo_root: Path,
    *,
    github_report_path: Path,
    github_json_path: Path,
    product_report_path: Path,
    product_json_path: Path,
    smoke_log_path: Path,
    security_scan_status: str,
    vault_path: Path = DEFAULT_VAULT_PATH,
    expected_remote: str = DEFAULT_REPO_URL,
) -> PublicationHandoff:
    root = repo_root.resolve()
    checks = [
        github_review_check(root, github_report_path, github_json_path, expected_remote),
        product_report_check(root, product_report_path, product_json_path, github_report_path, github_json_path, vault_path, expected_remote),
        smoke_log_check(smoke_log_path),
        security_scan_check(security_scan_status),
    ]
    status = "blocked" if any(check.status == "fail" for check in checks) else "ready_for_branch_owner"
    return PublicationHandoff(status, str(root), tuple(checks), next_actions(checks))


def validate_publication_handoff(
    repo_root: Path,
    json_report_path: Path,
    *,
    markdown_report_path: Path | None = None,
    github_report_path: Path,
    github_json_path: Path,
    product_report_path: Path,
    product_json_path: Path,
    smoke_log_path: Path,
    security_scan_status: str,
    vault_path: Path = DEFAULT_VAULT_PATH,
    expected_remote: str = DEFAULT_REPO_URL,
) -> PublicationHandoffValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    expected = build_publication_handoff(
        repo_root,
        github_report_path=github_report_path,
        github_json_path=github_json_path,
        product_report_path=product_report_path,
        product_json_path=product_json_path,
        smoke_log_path=smoke_log_path,
        security_scan_status=security_scan_status,
        vault_path=vault_path,
        expected_remote=expected_remote,
    )
    expected_payload = expected.to_dict()
    checks += 1
    try:
        payload = json.loads(json_report_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validation reports file problems as data.
        return PublicationHandoffValidation(checks, (f"Publication handoff JSON is unreadable: {exc}",), ())
    if not isinstance(payload, dict):
        return PublicationHandoffValidation(checks, ("Publication handoff JSON must be an object",), ())
    checks += 1
    if payload.get("schema_version") != PUBLICATION_HANDOFF_SCHEMA_VERSION:
        errors.append(f"Publication handoff schema_version must be {PUBLICATION_HANDOFF_SCHEMA_VERSION}")
    for key in ("status", "repo_root", "checks", "next_actions"):
        checks += 1
        if payload.get(key) != expected_payload[key]:
            errors.append(f"Publication handoff JSON field {key} does not match current handoff inputs")
    if markdown_report_path:
        checks += 1
        try:
            markdown = markdown_report_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - validation reports file problems as data.
            errors.append(f"Publication handoff Markdown is unreadable: {exc}")
        else:
            for fragment in required_handoff_markdown_fragments(expected):
                checks += 1
                if fragment not in markdown:
                    errors.append(f"Publication handoff Markdown missing required text: {fragment}")
    return PublicationHandoffValidation(checks, tuple(errors), tuple(warnings))


def github_review_check(root: Path, markdown_path: Path, json_path: Path, expected_remote: str) -> PublicationHandoffCheck:
    result = validate_github_publication_review(root, json_path, markdown_report_path=markdown_path, expected_remote=expected_remote)
    return PublicationHandoffCheck(
        "github-publication-review",
        "pass" if result.ok else "fail",
        result.summary() if result.ok else "; ".join(result.errors),
    )


def product_report_check(
    root: Path,
    markdown_path: Path,
    json_path: Path,
    github_report_path: Path,
    github_json_path: Path,
    vault_path: Path,
    expected_remote: str,
) -> PublicationHandoffCheck:
    result = validate_product_readiness_report(
        root,
        json_path,
        markdown_report_path=markdown_path,
        vault_path=vault_path,
        expected_remote=expected_remote,
        github_publication_review_path=github_report_path,
        github_publication_review_json_path=github_json_path,
    )
    return PublicationHandoffCheck(
        "product-readiness-report",
        "pass" if result.ok else "fail",
        result.summary() if result.ok else "; ".join(result.errors),
    )


def smoke_log_check(path: Path) -> PublicationHandoffCheck:
    try:
        content = read_text_with_fallback(path)
    except Exception as exc:  # noqa: BLE001 - validation reports file problems as data.
        return PublicationHandoffCheck("smoke-log", "fail", f"unreadable smoke log: {exc}")
    required = (
        "Smoke test passed:",
        "External handoff decision: blocked_for_external_handoff",
        "Required evidence ID list:",
    )
    missing = tuple(fragment for fragment in required if fragment not in content)
    if missing:
        return PublicationHandoffCheck("smoke-log", "fail", f"missing required smoke evidence: {', '.join(missing)}")
    return PublicationHandoffCheck("smoke-log", "pass", f"{path}: required smoke evidence present")


def security_scan_check(status: str) -> PublicationHandoffCheck:
    normalized = status.strip().lower()
    if normalized not in {"pass", "passed"}:
        return PublicationHandoffCheck("security-scan", "fail", f"security scan status is {status!r}; expected pass")
    return PublicationHandoffCheck("security-scan", "pass", "Security scan passed: no disallowed secret patterns found")


def read_text_with_fallback(path: Path) -> str:
    last_error: Exception | None = None
    for encoding in ("utf-8", "utf-16"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeError as exc:
            last_error = exc
    if last_error:
        raise last_error
    return path.read_text(encoding="utf-8")


def next_actions(checks: list[PublicationHandoffCheck]) -> tuple[str, ...]:
    failed = [check for check in checks if check.status == "fail"]
    if failed:
        return tuple(f"Resolve {check.name}: {check.detail}" for check in failed)
    return (
        "Branch-owner handoff package is current; review generated reports before staging.",
        "After operator approval, stage required publication paths, commit, push, and rerun github-readiness plus product-readiness.",
        "Do not claim external handoff readiness until approved endpoint evidence and approved Nutanix Move appliance proof are present.",
    )


def required_handoff_markdown_fragments(expected: PublicationHandoff) -> tuple[str, ...]:
    fragments = [
        "# Publication Handoff",
        f"- Status: `{expected.status}`",
        f"- Repository root: `{expected.repo_root}`",
        f"- Check count: `{len(expected.checks)}`",
        "## Checks",
        "## Next Actions",
        "## Operator Boundaries",
        "This handoff did not stage, commit, push, publish, or mutate infrastructure.",
        "Generated `outputs/` artifacts remain local review evidence and must not be published unless explicitly approved.",
        "External handoff remains blocked until approved endpoint evidence and approved Nutanix Move appliance proof are present.",
    ]
    fragments.extend(f"| `{check.status}` | `{check.name}` | {escape_markdown_cell(check.detail)} |" for check in expected.checks)
    fragments.extend(f"- {action}" for action in expected.next_actions)
    return tuple(fragments)


def escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")
