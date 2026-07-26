import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.assessment_intake import write_assessment_intake_template
from nmrcp.cli import main
from nmrcp.source_collection_plan import validate_source_collection_plan, write_source_collection_plan


class SourceCollectionPlanTests(unittest.TestCase):
    def test_completed_intake_generates_credential_safe_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake = write_completed_intake(root / "assessment-intake.csv")
            plan = root / "source-collection-plan.md"

            result = write_source_collection_plan(intake, plan)
            validation = validate_source_collection_plan(plan, intake)
            text = plan.read_text(encoding="utf-8")

        self.assertTrue(result.ok, result.errors)
        self.assertTrue(validation.ok, validation.errors)
        self.assertIn("# Source Collection Plan", text)
        self.assertIn("nmrcp_source_collection_plan_v1", text)
        self.assertIn("sample customer_or_program", text)
        self.assertIn("credentials_serialized=false", text)
        self.assertIn("endpoint_values_serialized=false", text)
        self.assertIn("python -m nmrcp.cli live-readiness", text)
        self.assertIn("python -m nmrcp.cli collect-sources", text)
        self.assertIn("python -m nmrcp.cli validate-live-proof", text)
        self.assertNotIn("https://", text)
        self.assertNotIn("vcenter01.corp.local", text)

    def test_generation_fails_when_intake_is_incomplete(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake = write_assessment_intake_template(root / "assessment-intake.csv")
            plan = root / "source-collection-plan.md"

            result = write_source_collection_plan(intake, plan)

        self.assertFalse(result.ok)
        self.assertFalse(plan.exists())
        self.assertTrue(any("Assessment intake invalid" in error for error in result.errors))

    def test_validator_rejects_tampered_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake = write_completed_intake(root / "assessment-intake.csv")
            plan = root / "source-collection-plan.md"
            write_source_collection_plan(intake, plan)
            plan.write_text(
                plan.read_text(encoding="utf-8").replace("credentials_serialized=false", "credentials_serialized=true", 1),
                encoding="utf-8",
            )

            result = validate_source_collection_plan(plan, intake)

        self.assertFalse(result.ok)
        self.assertTrue(any("credentials_serialized=false" in error or "does not match" in error for error in result.errors))

    def test_validator_rejects_endpoint_leakage(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake = write_completed_intake(root / "assessment-intake.csv")
            plan = root / "source-collection-plan.md"
            write_source_collection_plan(intake, plan)
            with plan.open("a", encoding="utf-8") as handle:
                handle.write("\nLeaked endpoint: https://vcenter01.corp.local/sdk\n")

            result = validate_source_collection_plan(plan, intake)

        self.assertFalse(result.ok)
        self.assertTrue(any("endpoint or secret-like material" in error for error in result.errors))

    def test_cli_generates_and_validates_source_collection_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake = write_completed_intake(root / "assessment-intake.csv")
            plan = root / "source-collection-plan.md"

            with patch("sys.stdout"):
                generate_code = main(["source-collection-plan", "--intake", str(intake), "--out", str(plan)])
                validate_code = main(["validate-source-collection-plan", "--plan", str(plan), "--intake", str(intake)])

        self.assertEqual(generate_code, 0)
        self.assertEqual(validate_code, 0)


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
