from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path


ASSESSMENT_INTAKE_SCHEMA_VERSION = "nmrcp_assessment_intake_v1"
INTAKE_COLUMNS = ("schema_version", "field", "value", "required", "description")
BOOLEAN_FIELDS = {
    "secrets_stay_local_ack",
    "redacted_evidence_ack",
    "read_only_collection_ack",
    "no_production_mutation_ack",
}
REQUIRED_FIELDS = {
    "customer_or_program",
    "assessment_owner",
    "migration_target",
    "source_scope",
    "target_scope",
    "dependency_source",
    "planned_assessment_window",
    *BOOLEAN_FIELDS,
}
VALID_TARGETS = {"ahv", "nc2", "both"}
SECRET_PATTERNS = (
    re.compile(r"password\s*[:=]", re.IGNORECASE),
    re.compile(r"secret\s*[:=]", re.IGNORECASE),
    re.compile(r"token\s*[:=]", re.IGNORECASE),
    re.compile(r"https?://[^\s,]+", re.IGNORECASE),
)


@dataclass(frozen=True)
class AssessmentIntakeValidation:
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"{status}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def write_assessment_intake_template(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ("customer_or_program", "", "true", "Customer, partner, or migration program label. Do not enter secrets or endpoint URLs."),
        ("assessment_owner", "", "true", "Responsible person or team for this assessment."),
        ("migration_target", "ahv", "true", "One of ahv, nc2, or both."),
        ("source_scope", "", "true", "Source estate scope, such as clusters, folders, waves, or excluded environments."),
        ("target_scope", "", "true", "Target Prism Central, AHV, or NC2 scope by non-secret label only."),
        ("dependency_source", "", "true", "Dependency source such as app map, CMDB, RVTools, workshop, or manual review."),
        ("planned_assessment_window", "", "true", "Planned assessment window or change reference."),
        ("secrets_stay_local_ack", "false", "true", "Set true to confirm credentials remain local and are never committed."),
        ("redacted_evidence_ack", "false", "true", "Set true to confirm evidence will be redacted before sharing."),
        ("read_only_collection_ack", "false", "true", "Set true to confirm vCenter and Prism collection is read-only."),
        ("no_production_mutation_ack", "false", "true", "Set true to confirm the assessment will not mutate production systems."),
        ("rvtools_export_available", "false", "false", "Optional true or false flag for offline RVTools input."),
        ("approved_move_lab_available", "false", "false", "Optional true or false flag for approved non-production Move proof window."),
        ("notes", "", "false", "Optional non-secret implementation notes."),
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=INTAKE_COLUMNS)
        writer.writeheader()
        for field, value, required, description in rows:
            writer.writerow(
                {
                    "schema_version": ASSESSMENT_INTAKE_SCHEMA_VERSION,
                    "field": field,
                    "value": value,
                    "required": required,
                    "description": description,
                }
            )
    return path


def validate_assessment_intake(path: Path) -> AssessmentIntakeValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(path, errors)
    if not rows:
        return AssessmentIntakeValidation(0, tuple(errors or [f"{path}: assessment intake cannot be empty"]), tuple(warnings))
    by_field: dict[str, dict[str, str]] = {}
    for index, row in enumerate(rows, start=2):
        if row.get("schema_version") != ASSESSMENT_INTAKE_SCHEMA_VERSION:
            errors.append(f"Row {index}: schema_version must be {ASSESSMENT_INTAKE_SCHEMA_VERSION}")
        field = (row.get("field") or "").strip()
        value = (row.get("value") or "").strip()
        if not field:
            errors.append(f"Row {index}: field is required")
            continue
        if field in by_field:
            errors.append(f"Row {index}: duplicate intake field {field}")
        by_field[field] = row
        if contains_secret_like_value(value):
            errors.append(f"Row {index}: value for {field} appears to contain an endpoint or secret; keep secrets local and out of intake files")
    missing = sorted(REQUIRED_FIELDS.difference(by_field))
    for field in missing:
        errors.append(f"Missing required intake field: {field}")
    for field in sorted(REQUIRED_FIELDS.intersection(by_field)):
        value = (by_field[field].get("value") or "").strip()
        if not value:
            errors.append(f"{field}: required value is empty")
    target = (by_field.get("migration_target", {}).get("value") or "").strip().lower()
    if target and target not in VALID_TARGETS:
        errors.append(f"migration_target must be one of {', '.join(sorted(VALID_TARGETS))}")
    for field in sorted(BOOLEAN_FIELDS.intersection(by_field)):
        value = (by_field[field].get("value") or "").strip().lower()
        if value != "true":
            errors.append(f"{field}: must be true before assessment handoff")
    for field in ("rvtools_export_available", "approved_move_lab_available"):
        if field in by_field:
            value = (by_field[field].get("value") or "").strip().lower()
            if value and value not in {"true", "false"}:
                warnings.append(f"{field}: expected true or false")
    if (by_field.get("approved_move_lab_available", {}).get("value") or "").strip().lower() != "true":
        warnings.append("Approved non-production Move lab proof is not marked available; MVP closure will remain partial.")
    return AssessmentIntakeValidation(len(rows), tuple(errors), tuple(warnings))


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    if not path.exists():
        errors.append(f"{path}: missing")
        return []
    try:
        with path.open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            missing = [column for column in INTAKE_COLUMNS if column not in (reader.fieldnames or [])]
            if missing:
                errors.append(f"{path}: missing required columns: {', '.join(missing)}")
                return []
            return list(reader)
    except OSError as exc:
        errors.append(f"{path}: could not read assessment intake: {exc}")
        return []


def contains_secret_like_value(value: str) -> bool:
    return any(pattern.search(value) for pattern in SECRET_PATTERNS)
