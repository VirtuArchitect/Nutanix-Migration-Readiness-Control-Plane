import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.operator_report import validate_operator_report
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class OperatorReportTests(unittest.TestCase):
    def test_generated_operator_report_passes_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_operator_report(out_dir / "operator-report.html", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("PASS", result.summary())

    def test_operator_report_rejects_tampered_audit_proof(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            report = out_dir / "operator-report.html"
            report.write_text(report.read_text(encoding="utf-8").replace("Mutating calls", "Mutation count"), encoding="utf-8")

            result = validate_operator_report(report, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("Mutating calls" in error for error in result.errors))

    def test_operator_report_rejects_tampered_summary_card_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            report = out_dir / "operator-report.html"
            report.write_text(
                report.read_text(encoding="utf-8").replace(
                    '<div class="metric"><strong>2</strong><span>Blocked</span></div>',
                    '<div class="metric"><strong>0</strong><span>Blocked</span></div>',
                ),
                encoding="utf-8",
            )

            result = validate_operator_report(report, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("Blocked=2" in error for error in result.errors))

    def test_operator_report_rejects_tampered_unmatched_dependency_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            report = out_dir / "operator-report.html"
            report.write_text(
                report.read_text(encoding="utf-8").replace(
                    '<div class="metric"><strong>0</strong><span>Unmatched Dependencies</span></div>',
                    '<div class="metric"><strong>3</strong><span>Unmatched Dependencies</span></div>',
                ),
                encoding="utf-8",
            )

            result = validate_operator_report(report, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("Unmatched Dependencies=0" in error for error in result.errors))

    def test_operator_report_rejects_tampered_workload_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            report = out_dir / "operator-report.html"
            report.write_text(report.read_text(encoding="utf-8").replace("snapshot_age_exceeds_policy", "snapshot_policy_removed"), encoding="utf-8")

            result = validate_operator_report(report, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("snapshot_age_exceeds_policy" in error for error in result.errors))

    def test_cli_validate_operator_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-operator-report",
                        "--report",
                        str(out_dir / "operator-report.html"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(code, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir
