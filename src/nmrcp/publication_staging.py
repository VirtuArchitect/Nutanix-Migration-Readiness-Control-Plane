from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .github_readiness import (
    FORBIDDEN_TRACKED_NAMES,
    FORBIDDEN_TRACKED_PREFIXES,
    FORBIDDEN_TRACKED_SUFFIXES,
    git_command,
    required_publication_paths,
)


PUBLICATION_STAGING_SCHEMA_VERSION = "nmrcp_publication_staging_v1"


@dataclass(frozen=True)
class PublicationStagingEntry:
    path: str
    status: str
    tracked: bool
    size_bytes: int | None
    sha256: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "status": self.status,
            "tracked": self.tracked,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class PublicationStagingManifest:
    status: str
    repo_root: str
    required_publication_paths: tuple[str, ...]
    entries: tuple[PublicationStagingEntry, ...]
    forbidden_candidates: tuple[str, ...]
    staging_command: str
    next_actions: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.status == "ready_for_operator_staging"

    def summary(self) -> str:
        missing = sum(1 for entry in self.entries if entry.status == "missing")
        tracked = sum(1 for entry in self.entries if entry.tracked)
        return f"{self.status}: paths={len(self.entries)}, tracked={tracked}, missing={missing}, forbidden_candidates={len(self.forbidden_candidates)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PUBLICATION_STAGING_SCHEMA_VERSION,
            "status": self.status,
            "repo_root": self.repo_root,
            "required_publication_paths": list(self.required_publication_paths),
            "entries": [entry.to_dict() for entry in self.entries],
            "forbidden_candidates": list(self.forbidden_candidates),
            "staging_command": self.staging_command,
            "next_actions": list(self.next_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Publication Staging Manifest",
            "",
            f"- Status: `{self.status}`",
            f"- Repository root: `{self.repo_root}`",
            f"- Required publication paths: `{len(self.entries)}`",
            f"- Forbidden candidates: `{len(self.forbidden_candidates)}`",
            "",
            "## Staging Command",
            "",
            f"`{self.staging_command}`",
            "",
            "## Required Paths",
            "",
            "| Status | Tracked | Size | SHA-256 | Path |",
            "| --- | --- | ---: | --- | --- |",
        ]
        for entry in self.entries:
            size = "" if entry.size_bytes is None else str(entry.size_bytes)
            digest = entry.sha256 or ""
            lines.append(f"| `{entry.status}` | `{str(entry.tracked).lower()}` | {size} | `{digest}` | `{entry.path}` |")
        lines.extend(["", "## Forbidden Candidates", ""])
        if self.forbidden_candidates:
            for path in self.forbidden_candidates:
                lines.append(f"- `{path}`")
        else:
            lines.append("- None")
        lines.extend(["", "## Next Actions", ""])
        for action in self.next_actions:
            lines.append(f"- {action}")
        lines.extend(
            [
                "",
                "## Operator Boundaries",
                "",
                "- This manifest did not stage, commit, push, remove, publish, or mutate files.",
                "- Review every hash before running the staging command.",
                "- Do not stage generated `outputs/`, credentials, customer exports, or lab appliance identifiers.",
                "",
            ]
        )
        return "\n".join(lines)


@dataclass(frozen=True)
class PublicationStagingValidation:
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{'PASS' if self.ok else 'FAIL'}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def build_publication_staging_manifest(repo_root: Path, *, ignored_forbidden_paths: tuple[Path, ...] = ()) -> PublicationStagingManifest:
    root = repo_root.resolve()
    required_paths = required_publication_paths(root)
    entries = tuple(build_entry(root, path) for path in required_paths)
    ignored = tuple(path.resolve() for path in ignored_forbidden_paths)
    forbidden_candidates = local_forbidden_candidates(root, ignored_paths=ignored)
    if any(entry.status == "missing" for entry in entries):
        status = "blocked"
    else:
        status = "ready_for_operator_staging"
    command_paths = [entry.path for entry in entries if not entry.tracked and entry.status == "present"]
    if not command_paths:
        staging_command = "git add -- " + " ".join(entry.path for entry in entries)
    else:
        staging_command = "git add -- " + " ".join(command_paths)
    return PublicationStagingManifest(status, str(root), required_paths, entries, forbidden_candidates, staging_command, next_actions(status, command_paths, forbidden_candidates))


def validate_publication_staging_manifest(
    repo_root: Path,
    json_report_path: Path,
    *,
    markdown_report_path: Path | None = None,
    ignored_forbidden_paths: tuple[Path, ...] = (),
) -> PublicationStagingValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    ignored_paths = (json_report_path, *ignored_forbidden_paths) if not markdown_report_path else (json_report_path, markdown_report_path, *ignored_forbidden_paths)
    expected = build_publication_staging_manifest(repo_root, ignored_forbidden_paths=ignored_paths)
    expected_payload = expected.to_dict()
    checks += 1
    try:
        payload = json.loads(json_report_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - validation returns data.
        return PublicationStagingValidation(checks, (f"Publication staging manifest JSON is unreadable: {exc}",), ())
    if not isinstance(payload, dict):
        return PublicationStagingValidation(checks, ("Publication staging manifest JSON must be an object",), ())
    checks += 1
    if payload.get("schema_version") != PUBLICATION_STAGING_SCHEMA_VERSION:
        errors.append(f"Publication staging manifest schema_version must be {PUBLICATION_STAGING_SCHEMA_VERSION}")
    for key in ("status", "repo_root", "required_publication_paths", "entries", "forbidden_candidates", "staging_command", "next_actions"):
        checks += 1
        if payload.get(key) != expected_payload[key]:
            errors.append(f"Publication staging manifest JSON field {key} does not match current staging state")
    if markdown_report_path:
        checks += 1
        try:
            markdown = markdown_report_path.read_text(encoding="utf-8")
        except Exception as exc:  # noqa: BLE001 - validation returns data.
            errors.append(f"Publication staging manifest Markdown is unreadable: {exc}")
        else:
            for fragment in required_markdown_fragments(expected):
                checks += 1
                if fragment not in markdown:
                    errors.append(f"Publication staging manifest Markdown missing required text: {fragment}")
    return PublicationStagingValidation(checks, tuple(errors), tuple(warnings))


def build_entry(root: Path, path: str) -> PublicationStagingEntry:
    full_path = root / path
    tracked = is_tracked(root, path)
    if not full_path.exists() or not full_path.is_file():
        return PublicationStagingEntry(path, "missing", tracked, None, None)
    content = full_path.read_bytes()
    return PublicationStagingEntry(path, "present", tracked, len(content), hashlib.sha256(content).hexdigest())


def is_tracked(root: Path, path: str) -> bool:
    return git_command(root, "ls-files", "--error-unmatch", path).returncode == 0


def local_forbidden_candidates(root: Path, *, ignored_paths: tuple[Path, ...] = ()) -> tuple[str, ...]:
    candidates: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        resolved = path.resolve()
        if resolved in ignored_paths:
            continue
        relative = path.relative_to(root).as_posix()
        if is_forbidden_path(relative):
            candidates.append(relative)
    return tuple(sorted(candidates))


def is_forbidden_path(path: str) -> bool:
    return (
        path in FORBIDDEN_TRACKED_NAMES
        or any(path.startswith(prefix) for prefix in FORBIDDEN_TRACKED_PREFIXES)
        or any(path.endswith(suffix) for suffix in FORBIDDEN_TRACKED_SUFFIXES)
    )


def next_actions(status: str, command_paths: list[str], forbidden_candidates: tuple[str, ...]) -> tuple[str, ...]:
    if status == "blocked":
        return ("Restore missing required publication paths, then regenerate and validate the staging manifest.",)
    actions: list[str] = []
    if forbidden_candidates:
        actions.append("Review forbidden local candidates and confirm they are not staged or published.")
    if command_paths:
        actions.append("Review the manifest hashes, then run the staging command only after operator approval.")
        actions.append("After staging, rerun github-readiness, product-readiness, full tests, security scan, and smoke before commit or pull request.")
    else:
        actions.append("All required paths are already tracked; rerun github-readiness before commit or pull request.")
    return tuple(actions)


def required_markdown_fragments(expected: PublicationStagingManifest) -> tuple[str, ...]:
    fragments = [
        "# Publication Staging Manifest",
        f"- Status: `{expected.status}`",
        f"- Repository root: `{expected.repo_root}`",
        f"- Required publication paths: `{len(expected.entries)}`",
        f"- Forbidden candidates: `{len(expected.forbidden_candidates)}`",
        "## Staging Command",
        expected.staging_command,
        "## Required Paths",
        "## Forbidden Candidates",
        "## Next Actions",
        "## Operator Boundaries",
        "This manifest did not stage, commit, push, remove, publish, or mutate files.",
        "Review every hash before running the staging command.",
        "Do not stage generated `outputs/`, credentials, customer exports, or lab appliance identifiers.",
    ]
    fragments.extend(f"`{entry.path}`" for entry in expected.entries)
    fragments.extend(f"`{entry.sha256}`" for entry in expected.entries if entry.sha256)
    fragments.extend(f"- `{path}`" for path in expected.forbidden_candidates)
    if not expected.forbidden_candidates:
        fragments.append("- None")
    fragments.extend(f"- {action}" for action in expected.next_actions)
    return tuple(fragments)
