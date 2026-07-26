from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


OPERATOR_REVIEW_SCHEMA_VERSION = "nmrcp_operator_review_v1"
REVIEW_STATUSES = {"approved", "needs_changes", "rejected", "draft"}
TRISTATE_VALUES = {"yes", "no", "not_applicable"}
REQUIRED_APPROVAL_FIELDS = (
    "coverage_reviewed",
    "readiness_reviewed",
    "move_plan_reviewed",
    "evidence_reviewed",
    "redaction_reviewed",
    "rollback_reviewed",
)
OPTIONAL_CONTEXT_FIELDS = (
    "capacity_reviewed",
    "target_reconciliation_reviewed",
    "network_mapping_reviewed",
    "app_map_reviewed",
)
REQUIRED_TEXT_FIELDS = ("reviewed_by", "reviewed_at", "change_reference", "notes")
OPERATOR_REVIEW_FIELDS = (
    "schema_version",
    "assessment_dir",
    "review_status",
    "reviewed_by",
    "reviewed_at",
    "change_reference",
    *REQUIRED_APPROVAL_FIELDS,
    *OPTIONAL_CONTEXT_FIELDS,
    "notes",
)


@dataclass(frozen=True)
class OperatorReviewValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "rows": self.rows,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def write_operator_review_template(assessment_dir: Path, out_path: Path) -> Path:
    row = {
        "schema_version": OPERATOR_REVIEW_SCHEMA_VERSION,
        "assessment_dir": str(assessment_dir),
        "review_status": "draft",
        "reviewed_by": "",
        "reviewed_at": datetime.now(UTC).isoformat(),
        "change_reference": "",
        "coverage_reviewed": "no",
        "readiness_reviewed": "no",
        "move_plan_reviewed": "no",
        "evidence_reviewed": "no",
        "redaction_reviewed": "no",
        "rollback_reviewed": "no",
        "capacity_reviewed": artifact_state(assessment_dir / "target-capacity-fit.csv"),
        "target_reconciliation_reviewed": artifact_state(assessment_dir / "target-reconciliation.csv"),
        "network_mapping_reviewed": artifact_state(assessment_dir / "target-network-mapping.csv"),
        "app_map_reviewed": app_map_state(assessment_dir),
        "notes": "Draft operator review. Complete required fields before final change-board handoff.",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OPERATOR_REVIEW_FIELDS)
        writer.writeheader()
        writer.writerow(row)
    return out_path


def validate_operator_review(
    review_path: Path,
    allow_draft: bool = False,
    assessment_dir: Path | None = None,
) -> OperatorReviewValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_review_rows(review_path, errors)
    if not rows:
        return OperatorReviewValidation("fail", 0, tuple(errors or [f"{review_path}: no review rows found"]), tuple(warnings))
    if len(rows) != 1:
        errors.append(f"{review_path}: expected exactly one operator review row, found {len(rows)}")

    row = rows[0]
    schema = clean(row.get("schema_version"))
    if schema != OPERATOR_REVIEW_SCHEMA_VERSION:
        errors.append(f"schema_version must be {OPERATOR_REVIEW_SCHEMA_VERSION}")

    review_status = clean(row.get("review_status")).lower()
    if review_status not in REVIEW_STATUSES:
        errors.append(f"review_status must be one of {', '.join(sorted(REVIEW_STATUSES))}")

    if assessment_dir is not None:
        review_assessment_dir = clean(row.get("assessment_dir"))
        if not review_assessment_dir:
            errors.append("assessment_dir is required when validating operator review against an assessment")
        elif not assessment_dir_matches(review_assessment_dir, assessment_dir):
            errors.append(f"assessment_dir {review_assessment_dir!r} does not match gated assessment {display_path(assessment_dir)!r}")

    for field in REQUIRED_APPROVAL_FIELDS + OPTIONAL_CONTEXT_FIELDS:
        value = clean(row.get(field)).lower()
        if value not in TRISTATE_VALUES:
            errors.append(f"{field} must be yes, no, or not_applicable")

    if review_status == "approved":
        for field in REQUIRED_TEXT_FIELDS:
            if not clean(row.get(field)):
                errors.append(f"{field} is required for approved operator review")
        for field in REQUIRED_APPROVAL_FIELDS:
            if clean(row.get(field)).lower() != "yes":
                errors.append(f"{field} must be yes for approved operator review")
        for field in OPTIONAL_CONTEXT_FIELDS:
            value = clean(row.get(field)).lower()
            if value == "no":
                warnings.append(f"{field} is no; optional operator context was not reviewed")
    elif allow_draft:
        warnings.append(f"operator review is {review_status or 'unset'}; allowed for draft review only")
    else:
        errors.append("operator review must be approved unless --allow-draft is used")

    status = "pass" if not errors else "fail"
    return OperatorReviewValidation(status, len(rows), tuple(errors), tuple(warnings))


def read_review_rows(review_path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with review_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if reader.fieldnames is None:
                errors.append(f"{review_path}: missing CSV header")
                return []
            missing = [field for field in OPERATOR_REVIEW_FIELDS if field not in reader.fieldnames]
            if missing:
                errors.append(f"{review_path}: missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{review_path}: could not read operator review: {exc}")
        return []


def artifact_state(path: Path) -> str:
    return "no" if path.exists() else "not_applicable"


def app_map_state(assessment_dir: Path) -> str:
    dependency_sequence = assessment_dir / "dependency-sequence.csv"
    return "no" if dependency_sequence.exists() else "not_applicable"


def clean(value: str | None) -> str:
    return (value or "").strip()


def assessment_dir_matches(review_value: str, assessment_dir: Path) -> bool:
    review_path = Path(review_value)
    if review_path.is_absolute():
        try:
            return review_path.resolve() == assessment_dir.resolve()
        except OSError:
            return normalize_path(review_path) == normalize_path(assessment_dir)
    review_normalized = normalize_text_path(review_value)
    assessment_normalized = normalize_path(assessment_dir)
    return assessment_normalized == review_normalized or assessment_normalized.endswith(f"/{review_normalized}")


def normalize_path(path: Path) -> str:
    return normalize_text_path(str(path))


def normalize_text_path(value: str) -> str:
    return value.replace("\\", "/").rstrip("/").lower()


def display_path(path: Path) -> str:
    return str(path).replace("\\", "/")
