import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.change_gate import run_change_gate
from nmrcp.cli import main
from nmrcp.dependencies import merge_dependencies, read_dependency_csv
from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.scoring import assess_inventory
from nmrcp.what_will_break import read_rows, validate_what_will_break, validate_what_will_break_brief
from nmrcp.waves import plan_waves


class WhatWillBreakTests(unittest.TestCase):
    def test_generated_report_answers_breakage_by_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment = json.loads((out_dir / "assessment.json").read_text(encoding="utf-8"))

            result = validate_what_will_break(out_dir / "what-will-break-report.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "what-will-break-report.csv", [])
            by_code = {(row["workload_id"], row["finding_code"]): row for row in rows}

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(assessment["what_will_break_context"]["schema_version"], "nmrcp_what_will_break_report_v1")
            self.assertEqual(assessment["inventory_coverage_context"]["schema_version"], "nmrcp_inventory_coverage_context_v1")
            self.assertIn(("vm-1001", "no_open_readiness_breakage"), by_code)
            self.assertEqual(by_code[("vm-1001", "no_open_readiness_breakage")]["move_staging_decision"], "include_after_validation")
            self.assertEqual(by_code[("vm-1001", "no_open_readiness_breakage")]["coverage_risk"], "complete")
            self.assertEqual(by_code[("vm-1001", "no_open_readiness_breakage")]["inventory_coverage_gaps"], "none")
            self.assertIn(("vm-2020", "snapshot_age_exceeds_policy"), by_code)
            self.assertEqual(by_code[("vm-2020", "snapshot_age_exceeds_policy")]["operator_signal"], "do_not_schedule")
            self.assertEqual(by_code[("vm-2020", "snapshot_age_exceeds_policy")]["coverage_risk"], "critical_coverage_gap")
            self.assertIn("guest_identity", by_code[("vm-2020", "snapshot_age_exceeds_policy")]["inventory_coverage_gaps"])
            self.assertIn(("vm-3030", "virtio_not_ready"), by_code)
            self.assertIn("failed cutover", by_code[("vm-3030", "nsx_dependency")]["impact"])
            self.assertIn("remediation-tracker.csv#vm-3030:nsx_dependency", by_code[("vm-3030", "nsx_dependency")]["evidence_refs"])

            brief_result = validate_what_will_break_brief(out_dir / "what-will-break-brief.md", out_dir / "assessment.json")
            brief = (out_dir / "what-will-break-brief.md").read_text(encoding="utf-8")

            self.assertTrue(brief_result.ok, brief_result.errors)
            self.assertIn("# What Will Break Brief", brief)
            self.assertIn("nmrcp_what_will_break_brief_v1", brief)
            self.assertIn("Decision signal: Hold blocked workloads out of Nutanix Move", brief)
            self.assertIn("Do-not-schedule signals:", brief)
            self.assertIn("[critical] payments-edge-01 (`vm-3030`)", brief)
            self.assertIn("`nsx_dependency`", brief)
            self.assertIn("Owner `Payments`, wave `Excluded Until Cleared`", brief)
            self.assertIn("what-will-break-report.csv", brief)
            self.assertIn("remediation-tracker.csv", brief)
            self.assertNotIn("vcenter01.corp.local", brief)

    def test_validator_rejects_tampered_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "what-will-break-report.csv"
            rows = read_rows(path, [])
            rows[0]["move_staging_decision"] = "include_now"
            rows[0]["coverage_risk"] = "complete"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_what_will_break(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("move_staging_decision expected" in error for error in result.errors))

    def test_validator_rejects_tampered_embedded_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["what_will_break_context"]["rows"][0]["operator_signal"] = "schedule_anyway"
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_what_will_break(out_dir / "what-will-break-report.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(
                any("what_will_break_context does not match assessments" in error for error in result.errors)
            )

    def test_brief_validator_rejects_tampered_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "what-will-break-brief.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("Do not stage workloads", "Stage workloads", 1),
                encoding="utf-8",
            )

            result = validate_what_will_break_brief(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("missing required text" in error or "does not match" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "what-will-break-report.csv"
            path.write_text(
                path.read_text(encoding="utf-8").replace("do_not_schedule", "schedule_anyway", 1),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "what-will-break-report" and check["status"] == "fail" for check in result.checks))

    def test_change_gate_fails_on_tampered_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "what-will-break-brief.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("nmrcp_what_will_break_brief_v1", "nmrcp_softened_brief_v1"),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "what-will-break-brief" and check["status"] == "fail" for check in result.checks))

    def test_cli_validates_what_will_break_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-what-will-break",
                        "--report",
                        str(out_dir / "what-will-break-report.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(code, 0)

    def test_cli_validates_what_will_break_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-what-will-break-brief",
                        "--brief",
                        str(out_dir / "what-will-break-brief.md"),
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


if __name__ == "__main__":
    unittest.main()
