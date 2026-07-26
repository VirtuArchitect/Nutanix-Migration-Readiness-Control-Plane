import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.operator_portal import validate_operator_portal
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class OperatorPortalTests(unittest.TestCase):
    def test_generated_operator_portal_passes_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_operator_portal(out_dir / "operator-portal.html", out_dir / "assessment.json")
            portal = (out_dir / "operator-portal.html").read_text(encoding="utf-8")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("PASS", result.summary())
            self.assertIn("Required proof contracts", portal)
            self.assertIn("External proof plan", portal)
            self.assertIn("external-proof-plan.md", portal)
            self.assertIn("nmrcp_external_proof_plan_v1", portal)
            self.assertIn("proof/external-proof-plan.json", portal)
            self.assertIn("nmrcp_move_lab_proof_validation_v1", portal)
            self.assertIn("nmrcp_move_lab_evidence_intake_v1", portal)

    def test_operator_portal_rejects_missing_required_proof_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            portal = out_dir / "operator-portal.html"
            portal.write_text(
                portal.read_text(encoding="utf-8").replace("nmrcp_move_lab_evidence_intake_v1", "missing_contract"),
                encoding="utf-8",
            )

            result = validate_operator_portal(portal, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("nmrcp_move_lab_evidence_intake_v1" in error for error in result.errors))

    def test_operator_portal_rejects_missing_external_proof_plan_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            portal = out_dir / "operator-portal.html"
            portal.write_text(
                portal.read_text(encoding="utf-8").replace("nmrcp_external_proof_plan_v1", "missing_external_plan"),
                encoding="utf-8",
            )

            result = validate_operator_portal(portal, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("nmrcp_external_proof_plan_v1" in error for error in result.errors))

    def test_operator_portal_allows_external_proof_plan_to_be_generated_later(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            self.assertFalse((out_dir / "external-proof-plan.md").exists())

            result = validate_operator_portal(out_dir / "operator-portal.html", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)

    def test_operator_portal_rejects_tampered_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            portal = out_dir / "operator-portal.html"
            portal.write_text(
                portal.read_text(encoding="utf-8").replace("nmrcp_operator_portal_v1", "nmrcp_old_portal_v1"),
                encoding="utf-8",
            )

            result = validate_operator_portal(portal, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("schema_version" in error for error in result.errors))

    def test_operator_portal_rejects_tampered_visible_summary_metric(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            portal = out_dir / "operator-portal.html"
            portal.write_text(
                portal.read_text(encoding="utf-8").replace(
                    '<div class="metric"><strong>2</strong><span>Blocked</span></div>',
                    '<div class="metric"><strong>0</strong><span>Blocked</span></div>',
                ),
                encoding="utf-8",
            )

            result = validate_operator_portal(portal, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("Blocked=2" in error for error in result.errors))

    def test_operator_portal_rejects_tampered_proof_posture_workload_count(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            portal = out_dir / "operator-portal.html"
            portal.write_text(
                portal.read_text(encoding="utf-8").replace("<dt>Workloads</dt><dd>3</dd>", "<dt>Workloads</dt><dd>1</dd>"),
                encoding="utf-8",
            )

            result = validate_operator_portal(portal, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("workload count expected 3" in error for error in result.errors))

    def test_operator_portal_rejects_missing_artifact_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            portal = out_dir / "operator-portal.html"
            portal.write_text(
                portal.read_text(encoding="utf-8").replace('href="nutanix-move-plan.csv"', 'href="move-plan-removed.csv"'),
                encoding="utf-8",
            )

            result = validate_operator_portal(portal, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("nutanix-move-plan.csv" in error for error in result.errors))

    def test_operator_portal_rejects_missing_artifact_title(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            portal = out_dir / "operator-portal.html"
            portal.write_text(
                portal.read_text(encoding="utf-8").replace("Operator dashboard", "Dashboard title removed"),
                encoding="utf-8",
            )

            result = validate_operator_portal(portal, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("artifact title" in error and "operator-dashboard.html" in error for error in result.errors))

    def test_operator_portal_rejects_missing_artifact_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            portal = out_dir / "operator-portal.html"
            portal.write_text(
                portal.read_text(encoding="utf-8").replace("Include/hold plan for Nutanix Move review.", "Move plan description removed."),
                encoding="utf-8",
            )

            result = validate_operator_portal(portal, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("artifact description" in error and "nutanix-move-plan.csv" in error for error in result.errors))

    def test_cli_validate_operator_portal(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-operator-portal",
                        "--portal",
                        str(out_dir / "operator-portal.html"),
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


if __name__ == "__main__":
    unittest.main()
