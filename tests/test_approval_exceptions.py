import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.approval_exceptions import read_rows, validate_approval_exception_approvals, validate_approval_exceptions
from nmrcp.cli import main
from nmrcp.dependencies import merge_dependencies, read_dependency_csv
from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class ApprovalExceptionsTests(unittest.TestCase):
    def test_approval_exceptions_include_held_high_risk_and_finding_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_approval_exceptions(out_dir / "approval-exceptions.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "approval-exceptions.csv", [])
            by_id = {row["exception_id"]: row for row in rows}

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(by_id["vm-2020:readiness_exception:readiness_prepare"]["severity"], "high")
            self.assertEqual(by_id["vm-3030:readiness_exception:readiness_blocked"]["severity"], "critical")
            self.assertEqual(by_id["vm-3030:high_risk_exception:risk_score_threshold"]["required_approval"], "risk_acceptance;migration_lead")
            self.assertEqual(by_id["vm-3030:finding_exception:nsx_dependency"]["required_approval"], "network_owner;risk_acceptance;migration_lead")
            self.assertEqual(by_id["vm-3030:finding_exception:vendor_support_unconfirmed"]["approval_status"], "required")
            self.assertIn("owner-signoff-matrix.csv#vm-3030", by_id["vm-3030:finding_exception:vendor_support_unconfirmed"]["evidence_refs"])

    def test_approval_exceptions_validator_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "approval-exceptions.csv"
            rows = read_rows(path, [])
            rows[0]["approval_status"] = "approved"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_approval_exceptions(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("approval_status expected 'required'" in error for error in result.errors))

    def test_cli_validates_approval_exceptions(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-approval-exceptions",
                        "--exceptions",
                        str(out_dir / "approval-exceptions.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(code, 0)

    def test_approval_exception_approvals_require_final_closure(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            draft = validate_approval_exception_approvals(
                out_dir / "approval-exceptions.csv",
                allow_required=True,
                assessment_path=out_dir / "assessment.json",
            )
            final = validate_approval_exception_approvals(
                out_dir / "approval-exceptions.csv",
                assessment_path=out_dir / "assessment.json",
            )

            self.assertTrue(draft.ok, draft.errors)
            self.assertFalse(final.ok)
            self.assertTrue(any("required approval exception blocks final closure" in error for error in final.errors))

    def test_approval_exception_approvals_accept_approved_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            approved = approved_exceptions_copy(out_dir, Path(tmp) / "approved-approval-exceptions.csv")

            result = validate_approval_exception_approvals(approved, assessment_path=out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.approved_count, result.row_count)

    def test_cli_validates_approval_exception_approvals(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            approved = approved_exceptions_copy(out_dir, Path(tmp) / "approved-approval-exceptions.csv")

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-approval-exception-approvals",
                        "--exceptions",
                        str(approved),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(code, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
    inventory = merge_dependencies(inventory, read_dependency_csv(Path("examples/sample_dependencies.csv")))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


def approved_exceptions_copy(out_dir: Path, path: Path) -> Path:
    rows = read_rows(out_dir / "approval-exceptions.csv", [])
    for index, row in enumerate(rows, start=1):
        row["approval_status"] = "approved"
        row["approval_ref"] = f"CHG-2026-EXC-{index:03d}"
        row["approved_by"] = "Migration Lead"
        row["approved_at"] = "2026-07-25T00:00:00Z"
        row["notes"] = "Approved for lab change-board review."
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


if __name__ == "__main__":
    unittest.main()
