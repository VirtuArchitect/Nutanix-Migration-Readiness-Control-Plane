from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


MIGRATION_WAVES_COLUMNS = (
    "wave",
    "workload_id",
    "name",
    "owner",
    "target",
    "readiness",
    "risk_score",
    "top_findings",
)


@dataclass(frozen=True)
class MigrationWavesValidation:
    status: str
    rows: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: rows={self.rows}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def validate_migration_waves(waves_path: Path, assessment_path: Path) -> MigrationWavesValidation:
    errors: list[str] = []
    warnings: list[str] = []
    rows = read_rows(waves_path, errors)
    assessment = read_assessment(assessment_path, errors)
    if errors:
        return MigrationWavesValidation("fail", len(rows), tuple(errors), tuple(warnings))

    expected = expected_wave_assignment_rows(assessment, errors)
    by_workload = {row.get("workload_id", ""): row for row in rows}
    if len(by_workload) != len(rows):
        errors.append("migration-waves.csv contains duplicate workload_id rows")

    missing = sorted(set(expected).difference(by_workload))
    extra = sorted(set(by_workload).difference(expected))
    for workload_id in missing:
        errors.append(f"Missing migration waves row: {workload_id}")
    for workload_id in extra:
        errors.append(f"Unexpected migration waves row: {workload_id}")

    for workload_id, expected_row in expected.items():
        row = by_workload.get(workload_id)
        if not row:
            continue
        for field, expected_value in expected_row.items():
            actual = (row.get(field) or "").strip()
            if actual != expected_value:
                errors.append(f"{workload_id}: {field} expected {expected_value!r}, got {actual!r}")

    if not rows:
        errors.append("migration-waves.csv cannot be empty")

    return MigrationWavesValidation("pass" if not errors else "fail", len(rows), tuple(errors), tuple(warnings))


def read_rows(path: Path, errors: list[str]) -> list[dict[str, str]]:
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            missing = [column for column in MIGRATION_WAVES_COLUMNS if column not in fieldnames]
            if missing:
                errors.append(f"Missing required columns: {', '.join(missing)}")
            return [dict(row) for row in reader]
    except OSError as exc:
        errors.append(f"{path}: could not read migration waves CSV: {exc}")
        return []


def read_assessment(path: Path, errors: list[str]) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path}: could not read assessment JSON: {exc}")
        return {}


def expected_wave_assignment_rows(assessment: dict[str, Any], errors: list[str]) -> dict[str, dict[str, str]]:
    assessments = {
        str(item.get("workload_id") or ""): item
        for item in assessment.get("assessments", [])
        if isinstance(item, dict)
    }
    wave_by_workload: dict[str, str] = {}
    for wave in assessment.get("waves", []):
        if not isinstance(wave, dict):
            continue
        wave_name = str(wave.get("name") or "Unassigned")
        workload_ids = wave.get("workload_ids") if isinstance(wave.get("workload_ids"), list) else []
        for workload_id in workload_ids:
            if not isinstance(workload_id, str):
                continue
            if workload_id not in assessments:
                errors.append(f"assessment.json wave {wave_name!r} references unknown workload_id {workload_id!r}")
            previous_wave = wave_by_workload.get(workload_id)
            if previous_wave:
                errors.append(
                    f"assessment.json workload_id {workload_id!r} appears in multiple waves: "
                    f"{previous_wave!r} and {wave_name!r}"
                )
            wave_by_workload[workload_id] = wave_name

    expected: dict[str, dict[str, str]] = {}
    for workload_id, row in assessments.items():
        findings = row.get("findings") if isinstance(row.get("findings"), list) else []
        top_findings = [
            str(finding.get("code") or "")
            for finding in findings[:3]
            if isinstance(finding, dict)
        ]
        expected[workload_id] = {
            "wave": wave_by_workload.get(workload_id, "Unassigned"),
            "workload_id": workload_id,
            "name": str(row.get("name") or ""),
            "owner": str(row.get("owner") or "Unassigned"),
            "target": str(row.get("target") or ""),
            "readiness": str(row.get("readiness") or ""),
            "risk_score": str(int(row.get("risk_score") or 0)),
            "top_findings": "; ".join(top_findings),
        }
    return expected
