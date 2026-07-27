from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


GITHUB_READINESS_SCHEMA_VERSION = "nmrcp_github_readiness_v1"
DEFAULT_REPO_URL = "https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane"

ROOT_PUBLICATION_FILES: tuple[str, ...] = (
    "README.md",
    "pyproject.toml",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "TESTING_GUIDE.md",
    "SECURITY_REVIEW.md",
    "CODE_REVIEW.md",
    "PENTEST_SCOPE_TEMPLATE.md",
    "AGENTS.md",
    ".editorconfig",
    ".env.example",
    ".gitignore",
)

PUBLICATION_DISCOVERY_DIRS: tuple[str, ...] = (
    ".github",
    "docs",
    "examples",
    "scripts",
    "src/nmrcp",
    "tests",
)

PUBLICATION_DISCOVERY_EXCLUDED_PARTS: tuple[str, ...] = (
    "__pycache__",
)

PUBLICATION_DISCOVERY_EXCLUDED_SUFFIXES: tuple[str, ...] = (
    ".pyc",
    ".pyo",
)

REQUIRED_PUBLICATION_PATHS: tuple[str, ...] = (
    "README.md",
    "pyproject.toml",
    "LICENSE",
    "SECURITY.md",
    "CONTRIBUTING.md",
    "TESTING_GUIDE.md",
    "SECURITY_REVIEW.md",
    "CODE_REVIEW.md",
    "AGENTS.md",
    ".gitignore",
    ".github/CODEOWNERS",
    ".github/pull_request_template.md",
    ".github/workflows/ci.yml",
    ".github/ISSUE_TEMPLATE/bug_report.md",
    ".github/ISSUE_TEMPLATE/feature_request.md",
    ".github/ISSUE_TEMPLATE/security_review.md",
    "docs/operations/README.md",
    "docs/operations/github-readiness.md",
    "docs/operations/vault-readiness.md",
    "docs/operations/product-readiness.md",
    "docs/operations/mvp-proof-package.md",
    "docs/operations/publication-handoff.md",
    "docs/operations/publication-staging.md",
    "docs/operations/pull-request-readiness.md",
    "docs/operations/external-proof-plan.md",
    "docs/operations/environment-access-gates.md",
    "docs/operations/version-control.md",
    "docs/operations/what-will-break-report.md",
    "docs/operations/move-staging-readiness.md",
    "docs/operations/source-collection-plan.md",
    "docs/operations/collection-proof-report.md",
    "docs/operations/move-plan-brief.md",
    "docs/security/README.md",
    "examples/sample_inventory.json",
    "scripts/security_scan.py",
    "scripts/smoke.ps1",
    "src/nmrcp/cli.py",
    "src/nmrcp/change_gate.py",
    "src/nmrcp/evidence.py",
    "src/nmrcp/github_readiness.py",
    "src/nmrcp/mvp_audit.py",
    "src/nmrcp/vault_readiness.py",
    "src/nmrcp/product_readiness.py",
    "src/nmrcp/mvp_proof_bundle.py",
    "src/nmrcp/operator_portal.py",
    "src/nmrcp/publication_handoff.py",
    "src/nmrcp/publication_staging.py",
    "src/nmrcp/pull_request_readiness.py",
    "src/nmrcp/external_proof_plan.py",
    "src/nmrcp/environment_access.py",
    "src/nmrcp/move_staging_readiness.py",
    "src/nmrcp/what_will_break.py",
    "src/nmrcp/source_collection_plan.py",
    "src/nmrcp/collection_proof_report.py",
    "src/nmrcp/move_plan_brief.py",
    "tests/test_github_ci.py",
    "tests/test_github_readiness.py",
    "tests/test_vault_readiness.py",
    "tests/test_product_readiness.py",
    "tests/test_mvp_audit.py",
    "tests/test_mvp_proof_bundle.py",
    "tests/test_operator_portal.py",
    "tests/test_publication_handoff.py",
    "tests/test_publication_staging.py",
    "tests/test_pull_request_readiness.py",
    "tests/test_external_proof_plan.py",
    "tests/test_environment_access.py",
    "tests/test_waves_and_evidence.py",
    "tests/test_move_staging_readiness.py",
    "tests/test_what_will_break.py",
    "tests/test_source_collection_plan.py",
    "tests/test_collection_proof_report.py",
    "tests/test_move_plan_brief.py",
)

FORBIDDEN_TRACKED_PREFIXES: tuple[str, ...] = (
    "outputs/",
    "build/",
    "dist/",
)

FORBIDDEN_TRACKED_SUFFIXES: tuple[str, ...] = (
    ".egg-info/PKG-INFO",
)

FORBIDDEN_TRACKED_NAMES: tuple[str, ...] = (
    ".env",
)


@dataclass(frozen=True)
class GitHubReadinessCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class GitHubReadiness:
    status: str
    repo_root: str
    expected_remote: str
    required_publication_paths: tuple[str, ...]
    checks: tuple[GitHubReadinessCheck, ...]
    next_actions: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.status == "pass"

    def summary(self) -> str:
        counts = {"pass": 0, "warn": 0, "fail": 0}
        for check in self.checks:
            counts[check.status] = counts.get(check.status, 0) + 1
        return f"{self.status.upper()}: checks={len(self.checks)}, errors={counts['fail']}, warnings={counts['warn']}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": GITHUB_READINESS_SCHEMA_VERSION,
            "status": self.status,
            "repo_root": self.repo_root,
            "expected_remote": self.expected_remote,
            "required_publication_paths": list(self.required_publication_paths),
            "checks": [check.to_dict() for check in self.checks],
            "next_actions": list(self.next_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# GitHub Publication Review",
            "",
            f"- Status: `{self.status}`",
            f"- Repository root: `{self.repo_root}`",
            f"- Expected remote: `{self.expected_remote}`",
            f"- Required publication paths: `{len(self.required_publication_paths)}`",
            "",
            "## Checks",
            "",
            "| Status | Check | Detail |",
            "| --- | --- | --- |",
        ]
        for check in self.checks:
            lines.append(f"| `{check.status}` | `{check.name}` | {escape_markdown_cell(check.detail)} |")
        lines.extend(
            [
                "",
                "## Next Actions",
                "",
            ]
        )
        for action in self.next_actions:
            lines.append(f"- {action}")
        lines.extend(
            [
                "",
                "## Required Publication Paths",
                "",
            ]
        )
        for path in self.required_publication_paths:
            lines.append(f"- `{path}`")
        lines.extend(
            [
                "",
                "## Operator Boundaries",
                "",
                "- This review did not stage, commit, push, remove, or publish files.",
                "- Do not publish generated `outputs/`, customer exports, support bundles, credentials, tokens, or lab appliance identifiers.",
                "- Rerun `github-readiness`, full tests, the security scan, and smoke after staging and before opening a pull request.",
                "",
            ]
        )
        return "\n".join(lines)


@dataclass(frozen=True)
class GitHubPublicationReviewValidation:
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{'PASS' if self.ok else 'FAIL'}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def check_github_readiness(
    repo_root: Path,
    *,
    expected_remote: str = DEFAULT_REPO_URL,
) -> GitHubReadiness:
    root = repo_root.resolve()
    checks: list[GitHubReadinessCheck] = []
    required_paths = required_publication_paths(root)
    missing_paths = missing_required_paths(root, required_paths)
    checks.append(required_paths_check(missing_paths, required_paths))

    git_root = git_command(root, "rev-parse", "--show-toplevel")
    git_available = git_root.returncode == 0
    checks.append(
        GitHubReadinessCheck(
            "git:repository",
            "pass" if git_available else "fail",
            git_root.stdout.strip() if git_available else (git_root.stderr.strip() or "not a git repository"),
        )
    )
    untracked_paths: tuple[str, ...] | None = None
    forbidden_paths: tuple[str, ...] | None = None
    if git_available:
        checks.append(remote_check(root, expected_remote))
        untracked_paths = untracked_required_paths(root, required_paths)
        checks.append(tracked_required_paths_check(untracked_paths, required_paths))
        forbidden_paths = forbidden_tracked_artifacts(root)
        checks.append(forbidden_tracked_artifacts_check(forbidden_paths))
    else:
        checks.append(GitHubReadinessCheck("git:remote-origin", "fail", "not evaluated without a git repository"))
        checks.append(GitHubReadinessCheck("git:required-paths-tracked", "fail", "not evaluated without a git repository"))

    status = "fail" if any(check.status == "fail" for check in checks) else "warn" if any(check.status == "warn" for check in checks) else "pass"
    return GitHubReadiness(
        status,
        str(root),
        expected_remote,
        required_paths,
        tuple(checks),
        publication_next_actions(
            checks,
            missing_paths=missing_paths,
            untracked_paths=untracked_paths,
            forbidden_paths=forbidden_paths,
            expected_remote=expected_remote,
        ),
    )


def validate_github_publication_review(
    repo_root: Path,
    json_report_path: Path,
    *,
    markdown_report_path: Path | None = None,
    expected_remote: str = DEFAULT_REPO_URL,
) -> GitHubPublicationReviewValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    expected = check_github_readiness(repo_root, expected_remote=expected_remote)
    expected_payload = expected.to_dict()
    checks += 1
    try:
        payload = json.loads(json_report_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validation should return data, not raise.
        return GitHubPublicationReviewValidation(checks, (f"GitHub publication review JSON is unreadable: {exc}",), ())
    if not isinstance(payload, dict):
        return GitHubPublicationReviewValidation(checks, ("GitHub publication review JSON must be an object",), ())
    checks += 1
    if payload.get("schema_version") != GITHUB_READINESS_SCHEMA_VERSION:
        errors.append(f"GitHub publication review schema_version must be {GITHUB_READINESS_SCHEMA_VERSION}")
    for key in ("status", "repo_root", "expected_remote", "required_publication_paths", "checks", "next_actions"):
        checks += 1
        if payload.get(key) != expected_payload[key]:
            errors.append(f"GitHub publication review JSON field {key} does not match current github-readiness")
    if markdown_report_path:
        checks += 1
        try:
            markdown = markdown_report_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - validation should return data, not raise.
            errors.append(f"GitHub publication review Markdown is unreadable: {exc}")
        else:
            for fragment in required_markdown_fragments(expected):
                checks += 1
                if fragment not in markdown:
                    errors.append(f"GitHub publication review Markdown missing required text: {fragment}")
    return GitHubPublicationReviewValidation(checks, tuple(errors), tuple(warnings))


def required_markdown_fragments(expected: GitHubReadiness) -> tuple[str, ...]:
    fragments = [
        "# GitHub Publication Review",
        f"- Status: `{expected.status}`",
        f"- Repository root: `{expected.repo_root}`",
        f"- Expected remote: `{expected.expected_remote}`",
        f"- Required publication paths: `{len(expected.required_publication_paths)}`",
        "## Checks",
        "## Next Actions",
        "## Required Publication Paths",
        "## Operator Boundaries",
        "This review did not stage, commit, push, remove, or publish files.",
        "Do not publish generated `outputs/`, customer exports, support bundles, credentials, tokens, or lab appliance identifiers.",
    ]
    fragments.extend(f"| `{check.status}` | `{check.name}` | {escape_markdown_cell(check.detail)} |" for check in expected.checks)
    fragments.extend(f"- {action}" for action in expected.next_actions)
    fragments.extend(f"- `{path}`" for path in expected.required_publication_paths)
    return tuple(fragments)


def required_publication_paths(root: Path | None = None) -> tuple[str, ...]:
    ordered_paths: list[str] = []
    seen: set[str] = set()
    for path in REQUIRED_PUBLICATION_PATHS:
        if path not in seen:
            ordered_paths.append(path)
            seen.add(path)
    if root is None:
        return tuple(ordered_paths)
    repo_root = root.resolve()
    for relative in ROOT_PUBLICATION_FILES:
        if (repo_root / relative).is_file() and relative not in seen:
            ordered_paths.append(relative)
            seen.add(relative)
    discovered: list[str] = []
    for directory in PUBLICATION_DISCOVERY_DIRS:
        base = repo_root / directory
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            relative_parts = path.relative_to(repo_root).parts
            if any(part in PUBLICATION_DISCOVERY_EXCLUDED_PARTS for part in relative_parts):
                continue
            relative = path.relative_to(repo_root).as_posix()
            if any(relative.endswith(suffix) for suffix in PUBLICATION_DISCOVERY_EXCLUDED_SUFFIXES):
                continue
            if is_forbidden_publication_candidate(relative):
                continue
            discovered.append(relative)
    for relative in sorted(discovered):
        if relative not in seen:
            ordered_paths.append(relative)
            seen.add(relative)
    return tuple(ordered_paths)


def is_forbidden_publication_candidate(path: str) -> bool:
    return (
        path in FORBIDDEN_TRACKED_NAMES
        or any(path.startswith(prefix) for prefix in FORBIDDEN_TRACKED_PREFIXES)
        or any(path.endswith(suffix) for suffix in FORBIDDEN_TRACKED_SUFFIXES)
    )


def missing_required_paths(root: Path, required_paths: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(path for path in required_paths if not (root / path).exists())


def required_paths_check(missing: tuple[str, ...], required_paths: tuple[str, ...]) -> GitHubReadinessCheck:
    return GitHubReadinessCheck(
        "workspace:required-publication-paths",
        "pass" if not missing else "fail",
        f"present={len(required_paths) - len(missing)}; missing={', '.join(missing) if missing else 'none'}",
    )


def remote_check(root: Path, expected_remote: str) -> GitHubReadinessCheck:
    result = git_command(root, "remote", "get-url", "origin")
    if result.returncode != 0:
        return GitHubReadinessCheck("git:remote-origin", "fail", result.stderr.strip() or "origin remote missing")
    actual = result.stdout.strip()
    normalized_actual = normalize_remote_url(actual)
    normalized_expected = normalize_remote_url(expected_remote)
    return GitHubReadinessCheck(
        "git:remote-origin",
        "pass" if normalized_actual == normalized_expected else "fail",
        f"origin={actual}; expected={expected_remote}",
    )


def untracked_required_paths(root: Path, required_paths: tuple[str, ...]) -> tuple[str, ...]:
    missing: list[str] = []
    for path in required_paths:
        result = git_command(root, "ls-files", "--error-unmatch", path)
        if result.returncode != 0:
            missing.append(path)
    return tuple(missing)


def tracked_required_paths_check(missing: tuple[str, ...], required_paths: tuple[str, ...]) -> GitHubReadinessCheck:
    return GitHubReadinessCheck(
        "git:required-paths-tracked",
        "pass" if not missing else "fail",
        f"tracked={len(required_paths) - len(missing)}; untracked_or_missing={', '.join(missing) if missing else 'none'}",
    )


def forbidden_tracked_artifacts(root: Path) -> tuple[str, ...]:
    result = git_command(root, "ls-files")
    if result.returncode != 0:
        return ("git ls-files failed",)
    tracked = [line.strip().replace("\\", "/") for line in result.stdout.splitlines() if line.strip()]
    return tuple(
        path
        for path in tracked
        if path in FORBIDDEN_TRACKED_NAMES
        or any(path.startswith(prefix) for prefix in FORBIDDEN_TRACKED_PREFIXES)
        or any(path.endswith(suffix) for suffix in FORBIDDEN_TRACKED_SUFFIXES)
    )


def forbidden_tracked_artifacts_check(forbidden: tuple[str, ...]) -> GitHubReadinessCheck:
    return GitHubReadinessCheck(
        "git:forbidden-tracked-artifacts",
        "pass" if not forbidden else "fail",
        f"forbidden={', '.join(forbidden) if forbidden else 'none'}",
    )


def publication_next_actions(
    checks: list[GitHubReadinessCheck],
    *,
    missing_paths: tuple[str, ...],
    untracked_paths: tuple[str, ...] | None,
    forbidden_paths: tuple[str, ...] | None,
    expected_remote: str,
) -> tuple[str, ...]:
    actions: list[str] = []
    by_name = {check.name: check for check in checks}
    if missing_paths:
        actions.append(f"Create or restore missing required publication paths before staging: {', '.join(missing_paths)}.")
    if by_name.get("git:repository", GitHubReadinessCheck("", "fail", "")).status == "fail":
        actions.append("Initialize the local Git repository before publication: git init.")
    if by_name.get("git:remote-origin", GitHubReadinessCheck("", "fail", "")).status == "fail":
        actions.append(f"Set the expected origin remote before publication: git remote add origin {expected_remote}.")
    if untracked_paths:
        actions.append(f"After operator review, stage required publication paths: git add -- {' '.join(untracked_paths)}.")
        actions.append("After staging, commit and push from an approved branch; rerun github-readiness before opening a pull request.")
    if forbidden_paths:
        actions.append(f"Remove forbidden generated artifacts from tracking before publication: git rm --cached -- {' '.join(forbidden_paths)}.")
    if not actions:
        actions.append("Publication gate passed locally; run full tests, security scan, smoke, and hosted CI before release claims.")
    return tuple(actions)


def normalize_remote_url(value: str) -> str:
    text = value.strip()
    if text.endswith(".git"):
        text = text[:-4]
    if text.startswith("git@github.com:"):
        text = "https://github.com/" + text.removeprefix("git@github.com:")
    return text.rstrip("/")


def escape_markdown_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def git_command(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ("git", *args),
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
