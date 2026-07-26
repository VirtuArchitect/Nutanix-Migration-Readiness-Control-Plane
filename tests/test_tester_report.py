import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.tester_report import build_tester_report, write_tester_report
from nmrcp.waves import plan_waves


class TesterReportTests(unittest.TestCase):
    def test_build_tester_report_summarizes_redacted_console_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = build_console_data(Path(tmp))

            report = build_tester_report(data_dir)

            self.assertEqual(report["schema_version"], "nmrcp_tester_report_v1")
            self.assertEqual(report["status"], "ready_for_tester_feedback")
            self.assertEqual(report["summary"]["workloads"], 3)
            self.assertEqual(report["summary"]["ready"], 1)
            self.assertEqual(report["summary"]["blocked"], 2)
            self.assertEqual(report["missing_artifacts"], [])
            self.assertTrue(report["safe_to_share"]["never_attach_credentials"])

    def test_write_tester_report_writes_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = build_console_data(root)
            report_path = root / "tester-report.md"
            json_path = root / "tester-report.json"

            report = write_tester_report(data_dir, report_path, json_path)

            self.assertEqual(report["status"], "ready_for_tester_feedback")
            self.assertIn("NMRCP Tester Report", report_path.read_text(encoding="utf-8"))
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "nmrcp_tester_report_v1")

    def test_cli_tester_report_returns_nonzero_until_artifacts_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("sys.stdout"):
                code = main(["tester-report", "--data-dir", str(root / "missing"), "--out", str(root / "report.md")])

            self.assertEqual(code, 1)

    def test_cli_tester_report_passes_with_complete_console_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            data_dir = build_console_data(root)

            with patch("sys.stdout"):
                code = main(
                    [
                        "tester-report",
                        "--data-dir",
                        str(data_dir),
                        "--out",
                        str(root / "report.md"),
                        "--json-out",
                        str(root / "report.json"),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertTrue((root / "report.md").exists())
            self.assertTrue((root / "report.json").exists())


def build_console_data(root: Path) -> Path:
    data_dir = root / "data"
    source_dir = data_dir / "source-collection"
    source_dir.mkdir(parents=True)
    (data_dir / "live-readiness.json").write_text(
        json.dumps({"schema_version": "nmrcp_live_readiness_v1", "status": "pass"}),
        encoding="utf-8",
    )
    (source_dir / "collection-summary.json").write_text(
        json.dumps({"schema_version": "nmrcp_collection_summary_v1", "status": "pass"}),
        encoding="utf-8",
    )
    (source_dir / "collection-proof-report.md").write_text("# Redacted collection proof\n", encoding="utf-8")
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    assessment_dir = data_dir / "assessment"
    write_assessment(inventory, assessments, waves, assessment_dir)
    return data_dir


if __name__ == "__main__":
    unittest.main()
