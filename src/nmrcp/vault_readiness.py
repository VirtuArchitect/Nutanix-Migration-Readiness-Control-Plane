from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


VAULT_READINESS_SCHEMA_VERSION = "nmrcp_vault_readiness_v1"

DEFAULT_VAULT_PATH = Path(
    r"C:\Users\john\OneDrive\09 Profile\Documents\OBSIDIAN VAULT GITS\Nutanix Migration & Readiness Control Plane"
)

OPERATION_NOTE_EXCEPTIONS: dict[str, str] = {
    "collection-audit": "Collection Audit Metadata",
    "handoff-package": "Handoff Package",
    "live-readiness": "Live Readiness",
    "metadata-enrichment": "Workload Metadata Enrichment",
    "move-lab-runbook": "Move Lab Execution Runbook",
    "move-lab-transcript": "Move Lab Transcript",
    "operator-review": "Operator Assessment Review",
    "owner-signoff-matrix": "Owner Sign-Off Matrix",
    "source-network-validation": "Source Network Validation",
}

REQUIRED_VAULT_NOTES: tuple[str, ...] = (
    "README.md",
    "Implementation Log.md",
    "Architecture.md",
    "Security Model.md",
    "GitHub Readiness.md",
)


@dataclass(frozen=True)
class VaultReadinessCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {"name": self.name, "status": self.status, "detail": self.detail}


@dataclass(frozen=True)
class VaultReadiness:
    status: str
    repo_root: str
    vault_path: str
    expected_notes: tuple[str, ...]
    checks: tuple[VaultReadinessCheck, ...]

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
            "schema_version": VAULT_READINESS_SCHEMA_VERSION,
            "status": self.status,
            "repo_root": self.repo_root,
            "vault_path": self.vault_path,
            "expected_notes": list(self.expected_notes),
            "checks": [check.to_dict() for check in self.checks],
        }


def check_vault_readiness(repo_root: Path, vault_path: Path = DEFAULT_VAULT_PATH) -> VaultReadiness:
    root = repo_root.resolve()
    vault = vault_path.resolve()
    operations_docs = operation_docs(root)
    expected_notes = tuple(sorted({*REQUIRED_VAULT_NOTES, *(operation_note_name(path) for path in operations_docs)}))
    checks: list[VaultReadinessCheck] = []

    checks.append(
        VaultReadinessCheck(
            "repo:operations-docs",
            "pass" if operations_docs else "fail",
            f"count={len(operations_docs)}",
        )
    )
    checks.append(
        VaultReadinessCheck(
            "vault:directory",
            "pass" if vault.exists() and vault.is_dir() else "fail",
            str(vault),
        )
    )
    if vault.exists() and vault.is_dir():
        checks.append(required_notes_check(vault, expected_notes))
        checks.append(readme_links_check(vault, expected_notes))
        checks.append(nonempty_notes_check(vault, expected_notes))
    else:
        checks.append(VaultReadinessCheck("vault:required-notes", "fail", "not evaluated without vault directory"))
        checks.append(VaultReadinessCheck("vault:readme-links", "fail", "not evaluated without vault directory"))
        checks.append(VaultReadinessCheck("vault:nonempty-notes", "fail", "not evaluated without vault directory"))

    status = "fail" if any(check.status == "fail" for check in checks) else "warn" if any(check.status == "warn" for check in checks) else "pass"
    return VaultReadiness(status, str(root), str(vault), expected_notes, tuple(checks))


def operation_docs(root: Path) -> tuple[Path, ...]:
    operations_dir = root / "docs" / "operations"
    if not operations_dir.exists():
        return ()
    return tuple(sorted(path for path in operations_dir.glob("*.md") if path.is_file()))


def operation_note_name(path: Path) -> str:
    stem = path.stem
    if stem.lower() == "readme":
        return "README.md"
    title = OPERATION_NOTE_EXCEPTIONS.get(stem, titleize_slug(stem))
    return f"{title}.md"


def titleize_slug(value: str) -> str:
    special = {
        "api": "API",
        "cmdb": "CMDB",
        "github": "GitHub",
        "mvp": "MVP",
        "rvtools": "RVTools",
    }
    return " ".join(special.get(part, part.capitalize()) for part in value.split("-"))


def required_notes_check(vault: Path, expected_notes: tuple[str, ...]) -> VaultReadinessCheck:
    missing = tuple(note for note in expected_notes if not (vault / note).exists())
    return VaultReadinessCheck(
        "vault:required-notes",
        "pass" if not missing else "fail",
        f"present={len(expected_notes) - len(missing)}; missing={', '.join(missing) if missing else 'none'}",
    )


def readme_links_check(vault: Path, expected_notes: tuple[str, ...]) -> VaultReadinessCheck:
    readme = vault / "README.md"
    if not readme.exists():
        return VaultReadinessCheck("vault:readme-links", "fail", "README.md missing")
    text = readme.read_text(encoding="utf-8")
    missing = []
    for note in expected_notes:
        if note == "README.md":
            continue
        title = note.removesuffix(".md")
        if f"[[{title}]]" not in text:
            missing.append(note)
    return VaultReadinessCheck(
        "vault:readme-links",
        "pass" if not missing else "fail",
        f"linked={len(expected_notes) - 1 - len(missing)}; missing={', '.join(missing) if missing else 'none'}",
    )


def nonempty_notes_check(vault: Path, expected_notes: tuple[str, ...]) -> VaultReadinessCheck:
    empty = []
    for note in expected_notes:
        path = vault / note
        if path.exists() and not path.read_text(encoding="utf-8").strip():
            empty.append(note)
    return VaultReadinessCheck(
        "vault:nonempty-notes",
        "pass" if not empty else "fail",
        f"empty={', '.join(empty) if empty else 'none'}",
    )
