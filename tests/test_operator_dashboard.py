import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.operator_dashboard import validate_operator_dashboard
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class OperatorDashboardTests(unittest.TestCase):
    def test_generated_operator_dashboard_passes_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_operator_dashboard(out_dir / "operator-dashboard.html", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("PASS", result.summary())

    def test_operator_dashboard_rejects_tampered_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            dashboard = out_dir / "operator-dashboard.html"
            dashboard.write_text(
                dashboard.read_text(encoding="utf-8").replace("nmrcp_operator_dashboard_v1", "nmrcp_old_dashboard_v1"),
                encoding="utf-8",
            )

            result = validate_operator_dashboard(dashboard, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("schema_version" in error for error in result.errors))

    def test_operator_dashboard_rejects_tampered_workload_finding(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            dashboard = out_dir / "operator-dashboard.html"
            dashboard.write_text(
                dashboard.read_text(encoding="utf-8").replace("snapshot_age_exceeds_policy", "snapshot_policy_removed"),
                encoding="utf-8",
            )

            result = validate_operator_dashboard(dashboard, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("snapshot_age_exceeds_policy" in error for error in result.errors))

    def test_operator_dashboard_rejects_tampered_dependency_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            dashboard = out_dir / "operator-dashboard.html"
            dashboard.write_text(
                dashboard.read_text(encoding="utf-8").replace('"dependency_count":1', '"dependency_count":9', 1),
                encoding="utf-8",
            )

            result = validate_operator_dashboard(dashboard, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("dependency_count expected 1" in error for error in result.errors))

    def test_operator_dashboard_rejects_tampered_unmatched_dependency_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            dashboard = out_dir / "operator-dashboard.html"
            dashboard.write_text(
                dashboard.read_text(encoding="utf-8").replace('"unmatched_dependencies":0', '"unmatched_dependencies":3'),
                encoding="utf-8",
            )

            result = validate_operator_dashboard(dashboard, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("unmatched_dependencies expected 0" in error for error in result.errors))

    def test_cli_validate_operator_dashboard(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-operator-dashboard",
                        "--dashboard",
                        str(out_dir / "operator-dashboard.html"),
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
