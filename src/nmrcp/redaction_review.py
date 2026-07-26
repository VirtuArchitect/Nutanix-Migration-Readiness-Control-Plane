from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .evidence_bundle import load_manifest
from .redaction import EMAIL_RE, HOST_RE, IP_RE, URL_RE


TEXT_SUFFIXES = {".csv", ".html", ".json", ".md", ".txt"}
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b(password|passwd|token|api[_-]?key|secret|authorization)\s*[:=]\s*['\"]?[^'\"\s,}]{4,}"
)
PATTERNS = (
    ("url", URL_RE),
    ("email", EMAIL_RE),
    ("ip", IP_RE),
    ("host", HOST_RE),
    ("secret-assignment", SECRET_ASSIGNMENT_RE),
)


@dataclass(frozen=True)
class RedactionReview:
    checked: int
    findings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.findings

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"{status}: checked={self.checked}, findings={len(self.findings)}"


def review_evidence_dir(out_dir: Path) -> RedactionReview:
    manifest = load_manifest(out_dir / "evidence-manifest.json")
    paths = [out_dir / "evidence-manifest.json"]
    paths.extend(out_dir / artifact["name"] for artifact in manifest["artifacts"])
    findings: list[str] = []
    checked = 0
    for path in paths:
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        checked += 1
        if not path.exists():
            findings.append(f"{path.name}: missing")
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append(f"{path.name}: not utf-8 text")
            continue
        findings.extend(scan_text(path.name, text))
    return RedactionReview(checked=checked, findings=tuple(findings))


def scan_text(name: str, text: str) -> list[str]:
    findings: list[str] = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        if "[REDACTED_" in line:
            line = remove_redacted_markers(line)
        for label, pattern in PATTERNS:
            if pattern.search(line):
                findings.append(f"{name}:{line_number}: potential {label} leak")
    return findings


def remove_redacted_markers(line: str) -> str:
    return re.sub(r"\[REDACTED_[A-Z_]+\]", "", line)
