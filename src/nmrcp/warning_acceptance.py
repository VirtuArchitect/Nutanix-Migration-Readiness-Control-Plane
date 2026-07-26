from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any


WARNING_ACCEPTANCE_SCHEMA_VERSION = "nmrcp_change_gate_warning_acceptance_v1"

REQUIRED_COLUMNS = (
    "schema_version",
    "warning_text",
    "acceptance_status",
    "acceptance_ref",
    "accepted_by",
    "accepted_at",
    "notes",
)


@dataclass(frozen=True)
class WarningAcceptanceValidation:
    path: str
    expected_count: int
    accepted_count: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    accepted_warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return (
            f"{status}: expected={self.expected_count}, accepted={self.accepted_count}, "
            f"errors={len(self.errors)}, warnings={len(self.warnings)}"
        )


def validate_warning_acceptance(path: Path, expected_warnings: tuple[str, ...]) -> WarningAcceptanceValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    expected = tuple(dict.fromkeys(warning for warning in expected_warnings if warning))
    expected_set = set(expected)
    accepted_by_text: dict[str, dict[str, str]] = {}

    for index, row in enumerate(rows, start=2):
        warning_text = row.get("warning_text", "").strip()
        if row.get("schema_version", "").strip() != WARNING_ACCEPTANCE_SCHEMA_VERSION:
            errors.append(f"Row {index}: schema_version must be {WARNING_ACCEPTANCE_SCHEMA_VERSION}")
        if not warning_text:
            errors.append(f"Row {index}: warning_text is required")
        elif warning_text in accepted_by_text:
            errors.append(f"Row {index}: duplicate warning_text")
        else:
            accepted_by_text[warning_text] = row
        if row.get("acceptance_status", "").strip().lower() != "accepted":
            errors.append(f"Row {index}: acceptance_status must be accepted")
        for field in ("acceptance_ref", "accepted_by", "accepted_at"):
            if not row.get(field, "").strip():
                errors.append(f"Row {index}: {field} is required")
        if not row.get("notes", "").strip():
            warnings.append(f"Row {index}: notes recommended for accepted warning")

    accepted_texts = set(accepted_by_text)
    for warning in expected:
        if warning not in accepted_texts:
            errors.append(f"Missing accepted warning: {warning}")
    for warning in sorted(accepted_texts - expected_set):
        errors.append(f"Unexpected accepted warning: {warning}")

    accepted_warnings = tuple(warning for warning in expected if warning in accepted_by_text)
    return WarningAcceptanceValidation(
        path=str(path),
        expected_count=len(expected),
        accepted_count=len(accepted_warnings),
        errors=tuple(errors),
        warnings=tuple(warnings),
        accepted_warnings=accepted_warnings,
    )


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        errors.append(f"{path}: missing")
        return []
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            missing = [column for column in REQUIRED_COLUMNS if column not in (reader.fieldnames or [])]
            if missing:
                errors.append(f"{path}: missing required columns: {', '.join(missing)}")
                return []
            return [
                {str(key): str(value or "") for key, value in row.items() if key is not None}
                for row in reader
            ]
    except OSError as exc:
        errors.append(f"{path}: could not read CSV: {exc}")
        return []
