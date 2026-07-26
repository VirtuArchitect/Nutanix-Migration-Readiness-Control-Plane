import json
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.launch_readiness import build_launch_readiness_report, validate_launch_readiness_report, write_launch_readiness_report
from nmrcp.mvp_proof_bundle import package_mvp_proof


class LaunchReadinessTests(unittest.TestCase):
    def test_launch_report_marks_simulated_move_proof_as_partner_review_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_partial_package(root)

            report = build_launch_readiness_report(
                package,
                repo_url="https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane",
            )

        self.assertEqual(report.package_verification_status, "pass")
        self.assertEqual(report.readiness, "ready_for_internal_or_partner_review")
        self.assertFalse(report.ready_for_external_handoff)
        self.assertEqual(report.external_handoff_decision, "blocked_for_external_handoff")
        self.assertTrue(any("move_lab_proof" in blocker for blocker in report.external_handoff_blockers))
        self.assertEqual(report.closure_summary["open_items"], len(report.open_items))
        self.assertEqual(
            report.closure_summary["blocking_open_items"],
            sum(1 for item in report.open_items if item["blocking"]),
        )
        self.assertGreaterEqual(report.closure_summary["required_evidence_id_count"], 2)
        self.assertIn("nmrcp_move_lab_evidence_intake_v1", report.closure_summary["required_evidence_ids"])
        self.assertIn("nmrcp_move_lab_proof_validation_v1", report.closure_summary["required_evidence_ids"])
        self.assertTrue(any(item["area"] == "move_lab_proof" for item in report.open_items))
        self.assertTrue(any("approved lab Move" in action for action in report.next_actions))
        self.assertTrue(any("generate-approved-move-lab-proof" in command for command in report.closeout_commands))
        self.assertTrue(any("validate-move-lab-evidence-intake" in command for command in report.closeout_commands))
        self.assertTrue(any("--move-lab-runbook" in command for command in report.closeout_commands))
        self.assertTrue(any("--move-lab-readiness-packet" in command for command in report.closeout_commands))
        self.assertTrue(any("--source-collection-plan" in command for command in report.closeout_commands))
        self.assertTrue(any("--source-endpoint-evidence-request" in command for command in report.closeout_commands))
        self.assertTrue(any("verify-mvp-proof" in command for command in report.closeout_commands))
        self.assertTrue(any("validate-mvp-proof-summary" in command for command in report.closeout_commands))
        self.assertTrue(any("validate-mvp-closure-report" in command for command in report.closeout_commands))
        self.assertTrue(any("validate-launch-readiness-report" in command for command in report.closeout_commands))
        self.assertIn("Real approved Nutanix Move appliance behavior remains unproven.", report.residual_risks)

    def test_launch_report_writes_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_partial_package(root)
            out = root / "launch.md"
            json_out = root / "launch.json"

            report = write_launch_readiness_report(
                package,
                out,
                json_out_path=json_out,
                repo_url="https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane",
            )
            text = out.read_text(encoding="utf-8")
            payload = json.loads(json_out.read_text(encoding="utf-8"))

        self.assertEqual(report.readiness, "ready_for_internal_or_partner_review")
        self.assertIn("# Launch Readiness Report", text)
        self.assertIn("Know exactly what will break", text)
        self.assertIn("ready_for_internal_or_partner_review", text)
        self.assertIn("## Closeout Commands", text)
        self.assertIn("## Handoff Package Roles", text)
        self.assertIn("## External Handoff Blockers", text)
        self.assertIn("- Blocking open items:", text)
        self.assertIn("- External handoff decision: `blocked_for_external_handoff`", text)
        self.assertIn("- Required evidence IDs:", text)
        self.assertIn("## Required Evidence IDs", text)
        self.assertIn("- `nmrcp_move_lab_evidence_intake_v1`", text)
        self.assertIn("- `nmrcp_move_lab_proof_validation_v1`", text)
        self.assertIn("generate-approved-move-lab-proof", text)
        self.assertIn("validate-move-lab-evidence-intake", text)
        self.assertEqual(payload["schema_version"], "nmrcp_launch_readiness_report_v1")
        self.assertEqual(payload["package_verification_status"], "pass")
        self.assertEqual(payload["external_handoff_decision"], "blocked_for_external_handoff")
        self.assertTrue(any("move_lab_proof" in blocker for blocker in payload["external_handoff_blockers"]))
        self.assertIn("handoff_roles", payload)
        self.assertIn("handoff_role_counts", payload)
        self.assertIn("closure_summary", payload)
        self.assertEqual(payload["closure_summary"]["open_items"], len(payload["open_items"]))
        self.assertTrue(any("validate-move-lab-evidence-intake" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("generate-approved-move-lab-proof" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("--move-lab-runbook" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("--move-lab-readiness-packet" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("--source-collection-plan" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("validate-mvp-proof-summary" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("validate-mvp-closure-report" in command for command in payload["closeout_commands"]))
        self.assertTrue(any("validate-launch-readiness-report" in command for command in payload["closeout_commands"]))

    def test_cli_launch_readiness_report_writes_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_partial_package(root)
            out = root / "launch.md"
            json_out = root / "launch.json"

            with patch("sys.stdout"):
                code = main(
                    [
                        "launch-readiness-report",
                        "--package",
                        str(package),
                        "--out",
                        str(out),
                        "--json-out",
                        str(json_out),
                        "--repo-url",
                        "https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane",
                    ]
                )
            out_exists = out.exists()
            json_out_exists = json_out.exists()

        self.assertEqual(code, 0)
        self.assertTrue(out_exists)
        self.assertTrue(json_out_exists)

    def test_cli_launch_readiness_report_prints_nested_handoff_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_partial_package(root)
            stdout = io.StringIO()

            with patch("sys.stdout", stdout):
                code = main(["launch-readiness-report", "--package", str(package)])

            output = stdout.getvalue()

        self.assertEqual(code, 0)
        self.assertIn("Nested handoff roles: 0", output)
        self.assertIn("Handoff readiness packet: missing", output)
        self.assertIn("External handoff decision: blocked_for_external_handoff", output)
        self.assertIn("Blocking open items:", output)
        self.assertIn("Required evidence IDs:", output)
        self.assertIn("Required evidence ID list:", output)

    def test_validate_launch_readiness_report_accepts_current_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_partial_package(root)
            out = root / "launch.md"
            json_out = root / "launch.json"
            write_launch_readiness_report(package, out, json_out_path=json_out)

            result = validate_launch_readiness_report(package, json_out, markdown_report_path=out)

        self.assertTrue(result.ok, result.errors)

    def test_validate_launch_readiness_report_accepts_equivalent_package_paths(self):
        with tempfile.TemporaryDirectory(dir=".") as tmp:
            root = Path(tmp)
            package = write_partial_package(root)
            out = root / "launch.md"
            json_out = root / "launch.json"
            write_launch_readiness_report(package.resolve(), out, json_out_path=json_out)

            result = validate_launch_readiness_report(package, json_out, markdown_report_path=out)

        self.assertTrue(result.ok, result.errors)

    def test_validate_launch_readiness_report_rejects_stale_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_partial_package(root)
            out = root / "launch.md"
            json_out = root / "launch.json"
            write_launch_readiness_report(package, out, json_out_path=json_out)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            payload["readiness"] = "ready_for_external_handoff"
            json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = validate_launch_readiness_report(package, json_out, markdown_report_path=out)

        self.assertFalse(result.ok)
        self.assertTrue(any("readiness" in error for error in result.errors))

    def test_validate_launch_readiness_report_rejects_missing_required_evidence_id_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_partial_package(root)
            out = root / "launch.md"
            json_out = root / "launch.json"
            write_launch_readiness_report(package, out, json_out_path=json_out)
            text = out.read_text(encoding="utf-8").replace("- `nmrcp_move_lab_evidence_intake_v1`\n", "")
            out.write_text(text, encoding="utf-8")

            result = validate_launch_readiness_report(package, json_out, markdown_report_path=out)

        self.assertFalse(result.ok)
        self.assertTrue(any("missing required evidence ID" in error for error in result.errors))

    def test_validate_launch_readiness_report_rejects_overclaimed_external_handoff_decision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_partial_package(root)
            out = root / "launch.md"
            json_out = root / "launch.json"
            write_launch_readiness_report(package, out, json_out_path=json_out)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            payload["external_handoff_decision"] = "approved_for_external_handoff"
            payload["external_handoff_blockers"] = []
            json_out.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = validate_launch_readiness_report(package, json_out, markdown_report_path=out)

        self.assertFalse(result.ok)
        self.assertTrue(any("external_handoff_decision" in error for error in result.errors))

    def test_validate_launch_readiness_report_rejects_missing_external_handoff_blocker_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_partial_package(root)
            out = root / "launch.md"
            json_out = root / "launch.json"
            write_launch_readiness_report(package, out, json_out_path=json_out)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            blocker = payload["external_handoff_blockers"][0]
            out.write_text(out.read_text(encoding="utf-8").replace(f"- {blocker}\n", ""), encoding="utf-8")

            result = validate_launch_readiness_report(package, json_out, markdown_report_path=out)

        self.assertFalse(result.ok)
        self.assertTrue(any("missing external handoff blocker" in error for error in result.errors))

    def test_validate_launch_readiness_report_rejects_missing_closeout_command_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_partial_package(root)
            out = root / "launch.md"
            json_out = root / "launch.json"
            write_launch_readiness_report(package, out, json_out_path=json_out)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            command = payload["closeout_commands"][0]
            out.write_text(out.read_text(encoding="utf-8").replace(f"{command}\n", ""), encoding="utf-8")

            result = validate_launch_readiness_report(package, json_out, markdown_report_path=out)

        self.assertFalse(result.ok)
        self.assertTrue(any("missing closeout command line" in error for error in result.errors))

    def test_validate_launch_readiness_report_rejects_tampered_summary_count_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_partial_package(root)
            out = root / "launch.md"
            json_out = root / "launch.json"
            write_launch_readiness_report(package, out, json_out_path=json_out)
            payload = json.loads(json_out.read_text(encoding="utf-8"))
            expected = payload["closure_summary"]["closeout_command_lines"]
            out.write_text(
                out.read_text(encoding="utf-8").replace(
                    f"- Closeout command lines: `{expected}`",
                    "- Closeout command lines: `0`",
                ),
                encoding="utf-8",
            )

            result = validate_launch_readiness_report(package, json_out, markdown_report_path=out)

        self.assertFalse(result.ok)
        self.assertTrue(any("Closeout command lines" in error for error in result.errors))

    def test_cli_validate_launch_readiness_report_reports_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            package = write_partial_package(root)
            out = root / "launch.md"
            json_out = root / "launch.json"
            write_launch_readiness_report(package, out, json_out_path=json_out)

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-launch-readiness-report",
                        "--package",
                        str(package),
                        "--report",
                        str(out),
                        "--json-report",
                        str(json_out),
                    ]
                )

        self.assertEqual(code, 0)


def write_partial_package(root: Path) -> Path:
    audit = write_json(root / "mvp-audit.json", mvp_audit())
    live = write_json(root / "live-proof.json", live_endpoint_proof())
    submit = write_json(root / "move-submit.json", {"schema_version": "nmrcp_move_submit_readiness_v1", "status": "pass", "errors": []})
    transcript = write_json(
        root / "move-lab-transcript.json",
        {"schema_version": "nmrcp_move_lab_transcript_validation_v1", "status": "warn", "errors": [], "warnings": []},
    )
    move = write_json(
        root / "move-proof.json",
        {
            "schema_version": "nmrcp_move_lab_proof_validation_v1",
            "status": "warn",
            "checks": [{"name": "move-lab-proof-scope", "status": "pass", "detail": "simulated_contract"}],
            "errors": [],
            "warnings": ["simulated proof only"],
        },
    )
    runbook = write_valid_runbook(root / "move-lab-runbook.md")
    package = root / "mvp-proof.zip"
    package_mvp_proof(
        package,
        mvp_audit_path=audit,
        live_proof_path=live,
        move_submit_readiness_path=submit,
        move_lab_transcript_path=transcript,
        move_lab_proof_path=move,
        move_lab_runbook_path=runbook,
    )
    return package


def mvp_audit() -> dict:
    return {
        "schema_version": "nmrcp_mvp_readiness_audit_v1",
        "status": "partial",
        "summary": {"pass": 6, "partial": 1, "fail": 0},
        "requirements": [
            {
                "id": "move_ready_plan",
                "status": "partial",
                "warnings": ["Real Nutanix Move appliance API behavior is not validated"],
                "errors": [],
            }
        ],
    }


def live_endpoint_proof() -> dict:
    required_checks = (
        "live-readiness-status",
        "live-readiness-security",
        "collection-summary-schema",
        "collection-summary-privacy",
        "collection-summary-assessment-intake",
        "collection-proof-manifest-security",
        "collection-proof-manifest-api-allowlist",
        "collection-proof-manifest-assessment-intake",
        "collection-proof-manifest-assessment-intake-match",
    )
    return {
        "schema_version": "nmrcp_live_endpoint_proof_v1",
        "status": "pass",
        "checks": [
            {"name": name, "status": "pass", "detail": "validated"}
            for name in required_checks
        ],
        "errors": [],
        "warnings": [],
    }


def write_json(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def write_valid_runbook(path: Path) -> Path:
    return write_text(
        path,
        "\n".join(
            [
                "# Move Lab Execution Runbook",
                "",
                "This runbook is for non-production Nutanix Move appliance proof only.",
                "",
                "## Inputs",
                "",
                "- Payload contract: `nmrcp_move_api_payload_dry_run_v1`",
                "",
                "## Required Environment",
                "",
                '$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"',
                "",
                "## Pre-Run Gates",
                "",
                "- Confirm `dry_run_only=true` and `mutation_allowed=false`.",
                "- Confirm `start_immediately=false`.",
                "",
                "## Stop Conditions",
                "",
                "- Stop if any endpoint, workload, or target is production.",
                "- Stop if evidence contains credentials, secrets, or unredacted endpoint values.",
                "",
                "## Validation Commands",
                "",
                "python -m nmrcp.cli validate-move-submit-readiness",
                "python -m nmrcp.cli validate-move-lab-transcript",
                "python -m nmrcp.cli generate-approved-move-lab-proof",
                "python -m nmrcp.cli validate-move-lab-proof --transcript-validation outputs\\move-lab-transcript-validation.json",
                "python -m nmrcp.cli validate-move-lab-evidence-intake --capture-kit-validation outputs\\move-lab-capture-kit-validation.json",
                "",
                "## Evidence To Capture",
                "",
                "- Move lab evidence intake JSON with `status=pass`.",
                "- Confirmation that `created_plans=0` and `started_migrations=0` for MVP proof.",
                "- Redacted operator notes.",
                "",
                "## Workload Scope",
                "",
                "| VM ID | Wave | Target | Readiness | Risk | Dependency Count |",
                "| --- | --- | --- | --- | --- | --- |",
                "",
                "## Closeout",
                "",
                "Run `mvp-audit --move-proof --move-lab-evidence-intake` after proof validation and intake pass.",
                "",
            ]
        ),
    )


if __name__ == "__main__":
    unittest.main()
