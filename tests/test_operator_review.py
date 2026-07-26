import csv
import tempfile
import unittest
from pathlib import Path

from nmrcp.operator_review import validate_operator_review, write_operator_review_template


class OperatorReviewTests(unittest.TestCase):
    def test_generate_operator_review_template_is_draft_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            assessment_dir = Path(tmp) / "assessment"
            assessment_dir.mkdir()
            (assessment_dir / "target-capacity-fit.csv").write_text("header\n", encoding="utf-8")
            review = Path(tmp) / "operator-review.csv"

            write_operator_review_template(assessment_dir, review)
            result = validate_operator_review(review, allow_draft=True)

            self.assertTrue(result.ok, result.errors)
            with review.open("r", encoding="utf-8", newline="") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["schema_version"], "nmrcp_operator_review_v1")
            self.assertEqual(row["review_status"], "draft")
            self.assertEqual(row["capacity_reviewed"], "no")
            self.assertEqual(row["target_reconciliation_reviewed"], "not_applicable")

    def test_approved_operator_review_passes(self):
        result = validate_operator_review(Path("examples/sample_operator_review_approved.csv"))

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.status, "pass")

    def test_approved_operator_review_can_be_bound_to_assessment_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp) / "operator-review.csv"
            write_approved_review(review, Path(tmp) / "assessment")

            result = validate_operator_review(review, assessment_dir=Path(tmp) / "assessment")

            self.assertTrue(result.ok, result.errors)

    def test_approved_operator_review_rejects_wrong_assessment_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp) / "operator-review.csv"
            write_approved_review(review, Path(tmp) / "assessment-a")

            result = validate_operator_review(review, assessment_dir=Path(tmp) / "assessment-b")

            self.assertFalse(result.ok)
            self.assertTrue(any("does not match gated assessment" in error for error in result.errors))

    def test_approved_review_requires_required_review_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp) / "operator-review.csv"
            review.write_text(
                "\n".join(
                    [
                        "schema_version,assessment_dir,review_status,reviewed_by,reviewed_at,change_reference,coverage_reviewed,readiness_reviewed,move_plan_reviewed,evidence_reviewed,redaction_reviewed,rollback_reviewed,capacity_reviewed,target_reconciliation_reviewed,network_mapping_reviewed,app_map_reviewed,notes",
                        "nmrcp_operator_review_v1,assessment,approved,Lead,2026-07-24T12:00:00+00:00,CHG-1,yes,no,yes,yes,yes,yes,not_applicable,not_applicable,not_applicable,not_applicable,reviewed",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = validate_operator_review(review)

            self.assertFalse(result.ok)
            self.assertTrue(any("readiness_reviewed must be yes" in error for error in result.errors))

    def test_draft_review_fails_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp) / "operator-review.csv"
            write_operator_review_template(Path(tmp), review)

            result = validate_operator_review(review)

            self.assertFalse(result.ok)
            self.assertTrue(any("must be approved" in error for error in result.errors))

    def test_missing_required_columns_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            review = Path(tmp) / "operator-review.csv"
            review.write_text("schema_version,review_status\nnmrcp_operator_review_v1,approved\n", encoding="utf-8")

            result = validate_operator_review(review)

            self.assertFalse(result.ok)
            self.assertTrue(any("missing required columns" in error for error in result.errors))


def write_approved_review(path: Path, assessment_dir: Path) -> Path:
    path.write_text(
        "\n".join(
            [
                "schema_version,assessment_dir,review_status,reviewed_by,reviewed_at,change_reference,coverage_reviewed,readiness_reviewed,move_plan_reviewed,evidence_reviewed,redaction_reviewed,rollback_reviewed,capacity_reviewed,target_reconciliation_reviewed,network_mapping_reviewed,app_map_reviewed,notes",
                f"nmrcp_operator_review_v1,{assessment_dir},approved,Lead,2026-07-24T12:00:00+00:00,CHG-1,yes,yes,yes,yes,yes,yes,not_applicable,not_applicable,not_applicable,not_applicable,reviewed",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
