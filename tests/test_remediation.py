import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.change_gate import run_change_gate
from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.remediation import validate_remediation_tracker, validate_remediation_tracker_contract
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class RemediationValidationTests(unittest.TestCase):
    def test_generated_tracker_passes_draft_and_fails_final_with_open_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            tracker = out_dir / "remediation-tracker.csv"

            draft = validate_remediation_tracker(tracker, allow_open=True)
            final = validate_remediation_tracker(tracker)

            self.assertTrue(draft.ok, draft.errors)
            self.assertFalse(final.ok)
            self.assertGreater(draft.open_count, 0)
            self.assertTrue(any("open remediation row blocks" in error for error in final.errors))

    def test_generated_tracker_contract_matches_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))

            result = validate_remediation_tracker_contract(out_dir / "remediation-tracker.csv", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("rows=", result.summary())

    def test_generated_tracker_contract_rejects_tampered_finding_action(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            tracker = out_dir / "remediation-tracker.csv"
            tracker.write_text(
                tracker.read_text(encoding="utf-8").replace(
                    "Map port groups, VLANs, and IPAM expectations to the target Nutanix network.",
                    "Skip network remediation.",
                    1,
                ),
                encoding="utf-8",
            )

            result = validate_remediation_tracker_contract(tracker, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("recommended_action expected" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_generated_tracker(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            tracker = out_dir / "remediation-tracker.csv"
            tracker.write_text(
                tracker.read_text(encoding="utf-8").replace("assessment.json#vm-2020/vds_mapping_required", "assessment.json#vm-2020/other"),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "remediation-tracker-baseline" and check["status"] == "fail" for check in result.checks))

    def test_closed_tracker_passes_final_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            closed = Path(tmp) / "closed-remediation.csv"
            write_status_copy(out_dir / "remediation-tracker.csv", closed, "closed")

            result = validate_remediation_tracker(closed)

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.open_count, 0)
            self.assertEqual(result.closed_count, result.row_count)

    def test_accepted_high_risk_tracker_warns_without_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            accepted = Path(tmp) / "accepted-remediation.csv"
            write_status_copy(out_dir / "remediation-tracker.csv", accepted, "accepted", notes="")

            result = validate_remediation_tracker(accepted)

            self.assertTrue(result.ok, result.errors)
            self.assertTrue(any("risk-acceptance notes" in warning for warning in result.warnings))

    def test_cli_validates_draft_and_final_remediation(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            closed = Path(tmp) / "closed-remediation.csv"
            write_status_copy(out_dir / "remediation-tracker.csv", closed, "closed")

            with patch("sys.stdout"):
                draft_code = main(["validate-remediation", "--tracker", str(out_dir / "remediation-tracker.csv"), "--allow-open"])
                final_open_code = main(["validate-remediation", "--tracker", str(out_dir / "remediation-tracker.csv")])
                final_closed_code = main(["validate-remediation", "--tracker", str(closed)])

            self.assertEqual(draft_code, 0)
            self.assertEqual(final_open_code, 1)
            self.assertEqual(final_closed_code, 0)

    def test_cli_validates_generated_tracker_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))

            with patch("sys.stdout"):
                result = main(
                    [
                        "validate-remediation-tracker",
                        "--tracker",
                        str(out_dir / "remediation-tracker.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(result, 0)


def build_sample_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


def write_status_copy(source: Path, target: Path, status: str, notes: str = "Closure proof reviewed") -> None:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        rows = list(reader)
    if not fieldnames:
        raise AssertionError("remediation tracker fieldnames missing")
    for index, row in enumerate(rows, start=1):
        row["status"] = status
        row["closure_ref"] = f"CHG-1001/remediation-{index}"
        row["closed_by"] = "Migration Lead"
        row["closed_at"] = "2026-07-24T13:00:00Z"
        row["notes"] = notes
    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
