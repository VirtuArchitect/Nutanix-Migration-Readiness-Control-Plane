from __future__ import annotations

import re
import sys
from pathlib import Path


SKIP_DIRS = {".git", ".pytest_cache", "__pycache__", "outputs"}
TEXT_SUFFIXES = {
    ".csv",
    ".json",
    ".md",
    ".ps1",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yml",
    ".yaml",
}
PATTERNS = [
    ("private-key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "literal-secret-assignment",
        re.compile(r"(?i)\b(password|token|api[_-]?key|secret)\s*[:=]\s*['\"][^'\"]{8,}['\"]"),
    ),
]
ALLOW_TEXT = {
    "synthetic-password",
    "super-secret-value",
    "<local secret>",
    "secret-value",
}


def main() -> int:
    root = Path.cwd()
    findings: list[str] = []
    for path in iter_files(root):
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for name, pattern in PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(0)
                if any(allowed in value for allowed in ALLOW_TEXT):
                    continue
                line_number = text.count("\n", 0, match.start()) + 1
                findings.append(f"{path.relative_to(root)}:{line_number}: {name}")
    if findings:
        print("Potential secret material found:")
        for finding in findings:
            print(f"- {finding}")
        return 1
    print("Security scan passed: no disallowed secret patterns found")
    return 0


def iter_files(root: Path):
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        yield path


if __name__ == "__main__":
    raise SystemExit(main())
