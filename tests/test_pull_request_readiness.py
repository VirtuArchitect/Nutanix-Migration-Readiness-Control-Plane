import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.github_readiness import REQUIRED_PUBLICATION_PATHS
from nmrcp.publication_staging import build_publication_staging_manifest
from nmrcp.pull_request_readiness import build_pull_request_readiness, validate_pull_request_readiness

from tests.test_publication_handoff import build_current_inputs
from tests.test_product_readiness import fake_mvp_audit


class PullRequestReadinessTests(unittest.TestCase):
    def test_required_publication_paths_include_pull_request_readiness(self):
        self.assertIn("docs/operations/pull-request-readiness.md", REQUIRED_PUBLICATION_PATHS)
        self.assertIn("src/nmrcp/pull_request_readiness.py", REQUIRED_PUBLICATION_PATHS)
        self.assertIn("tests/test_pull_request_readiness.py", REQUIRED_PUBLICATION_PATHS)

    def test_pull_request_readiness_accepts_current_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = build_pr_inputs(Path(tmp))

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = build_pull_request_readiness(**inputs)

        self.assertEqual(result.status, "ready_after_operator_staging")
        checks = {check.name: check for check in result.checks}
        self.assertEqual(checks["github-publication-review"].status, "pass")
        self.assertEqual(checks["product-readiness-report"].status, "pass")
        self.assertEqual(checks["publication-handoff"].status, "pass")
        self.assertEqual(checks["publication-staging-manifest"].status, "pass")
        self.assertIn("# Pull Request Readiness Packet", result.to_markdown())
        self.assertTrue(any("Commit, push, and open a pull request" in action for action in result.next_actions))

    def test_pull_request_readiness_blocks_failed_security_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = build_pr_inputs(Path(tmp))
            inputs["security_scan_status"] = "fail"

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = build_pull_request_readiness(**inputs)

        self.assertEqual(result.status, "blocked")
        self.assertTrue(any(check.name == "security-scan" and check.status == "fail" for check in result.checks))

    def test_validate_pull_request_readiness_accepts_current_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = build_pr_inputs(Path(tmp))
            report = inputs["repo_root"] / "outputs" / "pull-request-readiness.md"
            report_json = inputs["repo_root"] / "outputs" / "pull-request-readiness.json"

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = build_pull_request_readiness(**inputs)
                report.write_text(result.to_markdown(), encoding="utf-8")
                report_json.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
                validation = validate_pull_request_readiness(
                    inputs["repo_root"],
                    report_json,
                    markdown_report_path=report,
                    **{key: value for key, value in inputs.items() if key != "repo_root"},
                )

        self.assertTrue(validation.ok, validation.errors)

    def test_pull_request_readiness_accepts_staging_manifest_from_repeated_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = build_pr_inputs(Path(tmp))
            report = inputs["repo_root"] / "outputs" / "pull-request-readiness.md"
            report_json = inputs["repo_root"] / "outputs" / "pull-request-readiness.json"
            report.write_text("# prior packet\n", encoding="utf-8")
            report_json.write_text("{}\n", encoding="utf-8")
            staging = build_publication_staging_manifest(
                inputs["repo_root"],
                ignored_forbidden_paths=(inputs["staging_manifest_path"], inputs["staging_manifest_json_path"]),
            )
            inputs["staging_manifest_path"].write_text(staging.to_markdown(), encoding="utf-8")
            inputs["staging_manifest_json_path"].write_text(json.dumps(staging.to_dict(), indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = build_pull_request_readiness(
                    **inputs,
                    ignored_staging_forbidden_paths=(report, report_json),
                )

        checks = {check.name: check for check in result.checks}
        self.assertEqual(checks["publication-staging-manifest"].status, "pass")
        self.assertEqual(result.status, "ready_after_operator_staging")

    def test_validate_pull_request_readiness_rejects_stale_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = build_pr_inputs(Path(tmp))
            report_json = inputs["repo_root"] / "outputs" / "pull-request-readiness.json"

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                payload = build_pull_request_readiness(**inputs).to_dict()
            payload["status"] = "blocked"
            report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                validation = validate_pull_request_readiness(
                    inputs["repo_root"],
                    report_json,
                    **{key: value for key, value in inputs.items() if key != "repo_root"},
                )

        self.assertFalse(validation.ok)
        self.assertTrue(any("field status does not match current PR readiness inputs" in error for error in validation.errors))

    def test_validate_pull_request_readiness_rejects_tampered_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = build_pr_inputs(Path(tmp))
            report = inputs["repo_root"] / "outputs" / "pull-request-readiness.md"
            report_json = inputs["repo_root"] / "outputs" / "pull-request-readiness.json"

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = build_pull_request_readiness(**inputs)
                report.write_text(result.to_markdown().replace("This packet did not stage, commit, push, publish, open a pull request, or mutate infrastructure.", "Ready."), encoding="utf-8")
                report_json.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
                validation = validate_pull_request_readiness(
                    inputs["repo_root"],
                    report_json,
                    markdown_report_path=report,
                    **{key: value for key, value in inputs.items() if key != "repo_root"},
                )

        self.assertFalse(validation.ok)
        self.assertTrue(any("Markdown missing required text" in error for error in validation.errors))

    def test_cli_pull_request_readiness_writes_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            inputs = build_pr_inputs(Path(tmp))
            report = inputs["repo_root"] / "outputs" / "pull-request-readiness.md"
            report_json = inputs["repo_root"] / "outputs" / "pull-request-readiness.json"

            args = cli_args(inputs)
            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()), patch("sys.stdout") as stdout:
                code = main(["pull-request-readiness", *args, "--out", str(report), "--json-out", str(report_json)])
            output = "".join(call.args[0] for call in stdout.write.call_args_list)

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()), patch("sys.stdout") as validate_stdout:
                validation_code = main(["validate-pull-request-readiness", *args, "--report", str(report), "--json-report", str(report_json)])
            validation_output = "".join(call.args[0] for call in validate_stdout.write.call_args_list)

        self.assertEqual(code, 0)
        self.assertIn("Wrote pull request readiness packet:", output)
        self.assertEqual(validation_code, 0)
        self.assertIn("PASS:", validation_output)


def build_pr_inputs(tmp: Path):
    root, vault, github_report, github_json, product_report, product_json, smoke_log = build_current_inputs(tmp)
    handoff_report = root / "outputs" / "publication-handoff.md"
    handoff_json = root / "outputs" / "publication-handoff.json"
    staging_report = root / "outputs" / "publication-staging-manifest.md"
    staging_json = root / "outputs" / "publication-staging-manifest.json"
    with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
        from nmrcp.publication_handoff import build_publication_handoff

        handoff = build_publication_handoff(
            root,
            github_report_path=github_report,
            github_json_path=github_json,
            product_report_path=product_report,
            product_json_path=product_json,
            smoke_log_path=smoke_log,
            security_scan_status="pass",
            vault_path=vault,
        )
    handoff_report.write_text(handoff.to_markdown(), encoding="utf-8")
    handoff_json.write_text(json.dumps(handoff.to_dict(), indent=2), encoding="utf-8")
    staging = build_publication_staging_manifest(root, ignored_forbidden_paths=(staging_report, staging_json))
    staging_report.write_text(staging.to_markdown(), encoding="utf-8")
    staging_json.write_text(json.dumps(staging.to_dict(), indent=2), encoding="utf-8")
    return {
        "repo_root": root,
        "vault_path": vault,
        "github_report_path": github_report,
        "github_json_path": github_json,
        "product_report_path": product_report,
        "product_json_path": product_json,
        "publication_handoff_path": handoff_report,
        "publication_handoff_json_path": handoff_json,
        "staging_manifest_path": staging_report,
        "staging_manifest_json_path": staging_json,
        "smoke_log_path": smoke_log,
        "security_scan_status": "pass",
    }


def cli_args(inputs: dict[str, object]) -> list[str]:
    return [
        "--repo-root",
        str(inputs["repo_root"]),
        "--vault",
        str(inputs["vault_path"]),
        "--github-publication-review",
        str(inputs["github_report_path"]),
        "--github-publication-review-json",
        str(inputs["github_json_path"]),
        "--product-readiness-report",
        str(inputs["product_report_path"]),
        "--product-readiness-report-json",
        str(inputs["product_json_path"]),
        "--publication-handoff",
        str(inputs["publication_handoff_path"]),
        "--publication-handoff-json",
        str(inputs["publication_handoff_json_path"]),
        "--publication-staging-manifest",
        str(inputs["staging_manifest_path"]),
        "--publication-staging-manifest-json",
        str(inputs["staging_manifest_json_path"]),
        "--smoke-log",
        str(inputs["smoke_log_path"]),
        "--security-scan-status",
        str(inputs["security_scan_status"]),
    ]


if __name__ == "__main__":
    unittest.main()
