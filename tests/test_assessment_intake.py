import csv
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.assessment_intake import validate_assessment_intake, write_assessment_intake_template
from nmrcp.cli import main


class AssessmentIntakeTests(unittest.TestCase):
    def test_generated_template_requires_completion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_assessment_intake_template(Path(tmp) / "intake.csv")

            result = validate_assessment_intake(path)

        self.assertFalse(result.ok)
        self.assertTrue(any("required value is empty" in error for error in result.errors))
        self.assertTrue(any("secrets_stay_local_ack" in error for error in result.errors))

    def test_completed_intake_passes_with_move_lab_warning(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_completed_intake(Path(tmp) / "intake.csv")

            result = validate_assessment_intake(path)

        self.assertTrue(result.ok, result.errors)
        self.assertTrue(any("Approved non-production Move lab proof" in warning for warning in result.warnings))

    def test_intake_rejects_endpoint_or_secret_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_completed_intake(Path(tmp) / "intake.csv")
            rows = read_rows(path)
            rows[0]["value"] = "https://vcenter01.example.test"
            write_rows(path, rows)

            result = validate_assessment_intake(path)

        self.assertFalse(result.ok)
        self.assertTrue(any("endpoint or secret" in error for error in result.errors))

    def test_cli_generates_and_validates_intake_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template = root / "intake.csv"
            with patch("sys.stdout"):
                generate_code = main(["generate-assessment-intake", "--out", str(template)])
            rows = read_rows(template)
            for row in rows:
                if row["field"] in {"secrets_stay_local_ack", "redacted_evidence_ack", "read_only_collection_ack", "no_production_mutation_ack"}:
                    row["value"] = "true"
                elif row["required"] == "true" and not row["value"]:
                    row["value"] = f"sample {row['field']}"
            rows_by_field = {row["field"]: row for row in rows}
            rows_by_field["migration_target"]["value"] = "both"
            write_rows(template, rows)

            stdout = io.StringIO()
            with patch("sys.stdout", stdout):
                validate_code = main(["validate-assessment-intake", "--intake", str(template), "--json"])
            payload = json.loads(stdout.getvalue())
            template_exists = template.exists()

        self.assertEqual(generate_code, 0)
        self.assertEqual(validate_code, 0)
        self.assertTrue(template_exists)
        self.assertEqual(payload.get("schema_version"), "nmrcp_assessment_intake_validation_v1")


def write_completed_intake(path: Path) -> Path:
    write_assessment_intake_template(path)
    rows = read_rows(path)
    for row in rows:
        if row["field"] in {"secrets_stay_local_ack", "redacted_evidence_ack", "read_only_collection_ack", "no_production_mutation_ack"}:
            row["value"] = "true"
        elif row["field"] == "migration_target":
            row["value"] = "ahv"
        elif row["field"] == "rvtools_export_available":
            row["value"] = "true"
        elif row["field"] == "approved_move_lab_available":
            row["value"] = "false"
        elif row["required"] == "true":
            row["value"] = f"sample {row['field']}"
    write_rows(path, rows)
    return path


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
