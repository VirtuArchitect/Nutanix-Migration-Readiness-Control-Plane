import csv
import json
import tempfile
import unittest
from pathlib import Path

from nmrcp.change_gate import run_change_gate
from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.signoff import validate_signoff_matrix_contract, validate_signoffs
from nmrcp.waves import plan_waves


class SignoffValidationTests(unittest.TestCase):
    def test_generated_matrix_passes_draft_and_fails_final_with_pending_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            signoffs = out_dir / "owner-signoff-matrix.csv"

            draft = validate_signoffs(signoffs, allow_pending=True)
            final = validate_signoffs(signoffs)

            self.assertTrue(draft.ok, draft.errors)
            self.assertFalse(final.ok)
            self.assertEqual(draft.pending_count, 3)
            self.assertTrue(any("pending sign-off blocks" in error for error in final.errors))

    def test_assessment_contains_redacted_signoff_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            assessment = json.loads((out_dir / "assessment.json").read_text(encoding="utf-8"))

            context = assessment["signoff_context"]

            self.assertEqual(context["schema_version"], "nmrcp_signoff_context_v1")
            business_apps = next(row for row in context["workloads"] if row["workload_id"] == "vm-2020")
            self.assertIn("dependency_owner", business_apps["required_signoffs"])
            self.assertNotIn("password", json.dumps(context).lower())

    def test_generated_matrix_contract_matches_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))

            result = validate_signoff_matrix_contract(out_dir / "owner-signoff-matrix.csv", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("rows=3", result.summary())

    def test_generated_matrix_contract_rejects_tampered_required_roles(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            matrix = out_dir / "owner-signoff-matrix.csv"
            matrix.write_text(
                matrix.read_text(encoding="utf-8").replace(
                    "application_owner;dependency_owner;migration_lead;network_owner;risk_acceptance;rollback_owner",
                    "application_owner;migration_lead;risk_acceptance;rollback_owner",
                ),
                encoding="utf-8",
            )

            result = validate_signoff_matrix_contract(matrix, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("vm-2020: required_signoffs expected" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_generated_signoff_matrix(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            matrix = out_dir / "owner-signoff-matrix.csv"
            matrix.write_text(
                matrix.read_text(encoding="utf-8").replace(
                    "application_owner;dependency_owner;migration_lead;network_owner;risk_acceptance;rollback_owner",
                    "application_owner;migration_lead;risk_acceptance;rollback_owner",
                ),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "owner-signoff-matrix" and check["status"] == "fail" for check in result.checks))

    def test_cli_validates_generated_signoff_matrix_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))

            result = main(
                [
                    "validate-signoff-matrix",
                    "--matrix",
                    str(out_dir / "owner-signoff-matrix.csv"),
                    "--assessment",
                    str(out_dir / "assessment.json"),
                ]
            )

            self.assertEqual(result, 0)

    def test_approved_matrix_passes_final_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            approved = Path(tmp) / "approved-signoffs.csv"
            write_status_copy(out_dir / "owner-signoff-matrix.csv", approved, "approved")

            result = validate_signoffs(approved)

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.approved_count, 3)

    def test_approved_matrix_requires_closure_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            approved = Path(tmp) / "approved-signoffs.csv"
            write_status_copy(out_dir / "owner-signoff-matrix.csv", approved, "approved", include_closure=False)

            result = validate_signoffs(approved)

            self.assertFalse(result.ok)
            self.assertTrue(any("approval_ref is required when status is approved or waived" in error for error in result.errors))
            self.assertTrue(any("approved_by is required when status is approved or waived" in error for error in result.errors))
            self.assertTrue(any("approved_at is required when status is approved or waived" in error for error in result.errors))

    def test_rejected_matrix_fails_change_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            rejected = Path(tmp) / "rejected-signoffs.csv"
            write_status_copy(out_dir / "owner-signoff-matrix.csv", rejected, "rejected")

            result = run_change_gate(out_dir, signoffs_path=rejected)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "signoffs" and check["status"] == "fail" for check in result.checks))
            self.assertTrue(any("rejected sign-off blocks" in error for error in result.errors))

    def test_cli_validates_draft_signoffs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))

            draft_code = main(["validate-signoffs", "--signoffs", str(out_dir / "owner-signoff-matrix.csv"), "--allow-pending"])
            final_code = main(["validate-signoffs", "--signoffs", str(out_dir / "owner-signoff-matrix.csv")])

            self.assertEqual(draft_code, 0)
            self.assertEqual(final_code, 1)

    def test_storage_risk_requires_storage_owner_signoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
            inventory["workloads"][0]["storage"]["raw_device_mapping"] = True
            assessments = assess_inventory(inventory)
            waves = plan_waves(assessments)
            out_dir = Path(tmp) / "assessment"
            write_assessment(inventory, assessments, waves, out_dir)

            matrix = (out_dir / "owner-signoff-matrix.csv").read_text(encoding="utf-8")
            draft = validate_signoffs(out_dir / "owner-signoff-matrix.csv", allow_pending=True)

            self.assertIn("storage_owner", matrix)
            self.assertTrue(draft.ok, draft.errors)

    def test_generated_matrix_requires_rollback_owner_signoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            matrix = (out_dir / "owner-signoff-matrix.csv").read_text(encoding="utf-8")
            draft = validate_signoffs(out_dir / "owner-signoff-matrix.csv", allow_pending=True)

            self.assertIn("rollback_owner", matrix)
            self.assertTrue(draft.ok, draft.errors)


def build_sample_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


def write_status_copy(source: Path, target: Path, status: str, include_closure: bool = True) -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not fieldnames:
        raise AssertionError("signoff matrix fieldnames missing")
    for row in rows:
        row["status"] = status
        if status in {"approved", "waived"} and include_closure:
            row["approval_ref"] = f"CHG-2026-SIGNOFF-{row['workload_id']}"
            row["approved_by"] = "Migration Lead"
            row["approved_at"] = "2026-07-25T00:00:00Z"
            row["notes"] = "Approved for lab change-board review."
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
