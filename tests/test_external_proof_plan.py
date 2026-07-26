import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.external_proof_plan import build_external_proof_plan, validate_external_proof_plan
from nmrcp.github_readiness import REQUIRED_PUBLICATION_PATHS

from tests.test_github_readiness import init_repo, write_required_paths


class ExternalProofPlanTests(unittest.TestCase):
    def test_required_publication_paths_include_external_proof_plan(self):
        self.assertIn("docs/operations/external-proof-plan.md", REQUIRED_PUBLICATION_PATHS)
        self.assertIn("src/nmrcp/external_proof_plan.py", REQUIRED_PUBLICATION_PATHS)
        self.assertIn("tests/test_external_proof_plan.py", REQUIRED_PUBLICATION_PATHS)

    def test_external_proof_plan_carries_current_blockers_and_commands(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)

            plan = build_external_proof_plan(root)

        self.assertEqual(plan.status, "blocked_until_external_evidence")
        self.assertEqual(len(plan.steps), 2)
        markdown = plan.to_markdown()
        self.assertIn("nmrcp_live_endpoint_proof_v1", markdown)
        self.assertIn("nmrcp_move_lab_proof_validation_v1", markdown)
        self.assertIn("validate-live-proof", markdown)
        self.assertIn("validate-move-lab-evidence-intake", markdown)
        self.assertIn("Do not claim external handoff readiness", markdown)

    def test_validate_external_proof_plan_accepts_current_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            report = root / "outputs" / "external-proof-plan.md"
            report_json = root / "outputs" / "external-proof-plan.json"
            report.parent.mkdir(parents=True)
            plan = build_external_proof_plan(root)
            report.write_text(plan.to_markdown(), encoding="utf-8")
            report_json.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")

            result = validate_external_proof_plan(root, report_json, markdown_report_path=report)

        self.assertTrue(result.ok, result.errors)

    def test_validate_external_proof_plan_rejects_softened_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            report = root / "outputs" / "external-proof-plan.md"
            report_json = root / "outputs" / "external-proof-plan.json"
            report.parent.mkdir(parents=True)
            plan = build_external_proof_plan(root)
            report.write_text(plan.to_markdown().replace("Do not claim external handoff readiness", "External handoff is ready"), encoding="utf-8")
            report_json.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")

            result = validate_external_proof_plan(root, report_json, markdown_report_path=report)

        self.assertFalse(result.ok)
        self.assertTrue(any("Markdown missing required text" in error for error in result.errors))

    def test_cli_external_proof_plan_writes_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            report = root / "outputs" / "external-proof-plan.md"
            report_json = root / "outputs" / "external-proof-plan.json"

            with patch("sys.stdout") as stdout:
                code = main(["external-proof-plan", "--repo-root", str(root), "--out", str(report), "--json-out", str(report_json)])
            output = "".join(call.args[0] for call in stdout.write.call_args_list)

            with patch("sys.stdout") as validate_stdout:
                validation_code = main(["validate-external-proof-plan", "--repo-root", str(root), "--report", str(report), "--json-report", str(report_json)])
            validation_output = "".join(call.args[0] for call in validate_stdout.write.call_args_list)

        self.assertEqual(code, 0)
        self.assertIn("Wrote external proof plan:", output)
        self.assertEqual(validation_code, 0)
        self.assertIn("PASS:", validation_output)


if __name__ == "__main__":
    unittest.main()
