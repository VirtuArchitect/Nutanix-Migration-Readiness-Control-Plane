import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.github_readiness import REQUIRED_PUBLICATION_PATHS, check_github_readiness
from nmrcp.product_readiness import check_product_readiness
from nmrcp.publication_handoff import build_publication_handoff, validate_publication_handoff

from tests.test_product_readiness import build_matching_vault, build_minimal_product_repo, fake_mvp_audit, init_product_repo


class PublicationHandoffTests(unittest.TestCase):
    def test_required_publication_paths_include_publication_handoff(self):
        self.assertIn("src/nmrcp/publication_handoff.py", REQUIRED_PUBLICATION_PATHS)
        self.assertIn("tests/test_publication_handoff.py", REQUIRED_PUBLICATION_PATHS)

    def test_publication_handoff_accepts_current_inputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, vault, github_report, github_json, product_report, product_json, smoke_log = build_current_inputs(Path(tmp))

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
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

        self.assertEqual(handoff.status, "ready_for_branch_owner")
        checks = {check.name: check for check in handoff.checks}
        self.assertEqual(checks["github-publication-review"].status, "pass")
        self.assertEqual(checks["product-readiness-report"].status, "pass")
        self.assertEqual(checks["smoke-log"].status, "pass")
        self.assertTrue(any("stage required publication paths" in action for action in handoff.next_actions))
        self.assertIn("This handoff did not stage, commit, push", handoff.to_markdown())

    def test_validate_publication_handoff_accepts_current_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, vault, github_report, github_json, product_report, product_json, smoke_log = build_current_inputs(Path(tmp))
            handoff_report = root / "outputs" / "publication-handoff.md"
            handoff_json = root / "outputs" / "publication-handoff.json"

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
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
                validation = validate_publication_handoff(
                    root,
                    handoff_json,
                    markdown_report_path=handoff_report,
                    github_report_path=github_report,
                    github_json_path=github_json,
                    product_report_path=product_report,
                    product_json_path=product_json,
                    smoke_log_path=smoke_log,
                    security_scan_status="pass",
                    vault_path=vault,
                )

        self.assertTrue(validation.ok, validation.errors)

    def test_validate_publication_handoff_rejects_stale_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, vault, github_report, github_json, product_report, product_json, smoke_log = build_current_inputs(Path(tmp))
            handoff_json = root / "outputs" / "publication-handoff.json"

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                payload = build_publication_handoff(
                    root,
                    github_report_path=github_report,
                    github_json_path=github_json,
                    product_report_path=product_report,
                    product_json_path=product_json,
                    smoke_log_path=smoke_log,
                    security_scan_status="pass",
                    vault_path=vault,
                ).to_dict()
            payload["status"] = "blocked"
            handoff_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                validation = validate_publication_handoff(
                    root,
                    handoff_json,
                    github_report_path=github_report,
                    github_json_path=github_json,
                    product_report_path=product_report,
                    product_json_path=product_json,
                    smoke_log_path=smoke_log,
                    security_scan_status="pass",
                    vault_path=vault,
                )

        self.assertFalse(validation.ok)
        self.assertTrue(any("field status does not match current handoff inputs" in error for error in validation.errors))

    def test_publication_handoff_blocks_on_missing_smoke_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, vault, github_report, github_json, product_report, product_json, smoke_log = build_current_inputs(Path(tmp))
            smoke_log.write_text("Smoke test passed: path\n", encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
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

        self.assertEqual(handoff.status, "blocked")
        self.assertTrue(any(check.name == "smoke-log" and check.status == "fail" for check in handoff.checks))

    def test_publication_handoff_accepts_utf16_powershell_smoke_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, vault, github_report, github_json, product_report, product_json, smoke_log = build_current_inputs(Path(tmp))
            smoke_log.write_text(smoke_log.read_text(encoding="utf-8"), encoding="utf-16")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
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

        self.assertEqual(handoff.status, "ready_for_branch_owner")
        self.assertTrue(any(check.name == "smoke-log" and check.status == "pass" for check in handoff.checks))

    def test_cli_publication_handoff_writes_outputs_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, vault, github_report, github_json, product_report, product_json, smoke_log = build_current_inputs(Path(tmp))
            handoff_report = root / "outputs" / "publication-handoff.md"
            handoff_json = root / "outputs" / "publication-handoff.json"

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()), patch("sys.stdout") as stdout:
                code = main(
                    [
                        "publication-handoff",
                        "--repo-root",
                        str(root),
                        "--vault",
                        str(vault),
                        "--github-publication-review",
                        str(github_report),
                        "--github-publication-review-json",
                        str(github_json),
                        "--product-readiness-report",
                        str(product_report),
                        "--product-readiness-report-json",
                        str(product_json),
                        "--smoke-log",
                        str(smoke_log),
                        "--security-scan-status",
                        "pass",
                        "--out",
                        str(handoff_report),
                        "--json-out",
                        str(handoff_json),
                    ]
                )
            output = "".join(call.args[0] for call in stdout.write.call_args_list)

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()), patch("sys.stdout") as validate_stdout:
                validation_code = main(
                    [
                        "validate-publication-handoff",
                        "--repo-root",
                        str(root),
                        "--vault",
                        str(vault),
                        "--github-publication-review",
                        str(github_report),
                        "--github-publication-review-json",
                        str(github_json),
                        "--product-readiness-report",
                        str(product_report),
                        "--product-readiness-report-json",
                        str(product_json),
                        "--smoke-log",
                        str(smoke_log),
                        "--security-scan-status",
                        "pass",
                        "--report",
                        str(handoff_report),
                        "--json-report",
                        str(handoff_json),
                    ]
                )
            validation_output = "".join(call.args[0] for call in validate_stdout.write.call_args_list)

        self.assertEqual(code, 0)
        self.assertIn("Wrote publication handoff:", output)
        self.assertEqual(validation_code, 0)
        self.assertIn("PASS:", validation_output)


def build_current_inputs(tmp: Path):
    root = init_product_repo(tmp / "repo")
    build_minimal_product_repo(root)
    vault = build_matching_vault(tmp / "vault", root)
    github = check_github_readiness(root)
    github_report = root / "outputs" / "github-publication-review.md"
    github_json = root / "outputs" / "github-publication-review.json"
    product_report = root / "outputs" / "product-readiness-report.md"
    product_json = root / "outputs" / "product-readiness-report.json"
    smoke_log = root / "outputs" / "smoke.log"
    github_report.parent.mkdir(parents=True)
    github_report.write_text(github.to_markdown(), encoding="utf-8")
    github_json.write_text(json.dumps(github.to_dict(), indent=2), encoding="utf-8")
    with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
        product = check_product_readiness(
            root,
            vault_path=vault,
            github_publication_review_path=github_report,
            github_publication_review_json_path=github_json,
        )
    product_report.write_text(product.to_markdown(), encoding="utf-8")
    product_json.write_text(json.dumps(product.to_dict(), indent=2), encoding="utf-8")
    smoke_log.write_text(
        "\n".join(
            (
                "MVP status: partial",
                "External handoff decision: blocked_for_external_handoff",
                "Required evidence ID list: nmrcp_move_lab_evidence_intake_v1, nmrcp_move_lab_proof_validation_v1",
                "Smoke test passed: outputs\\smoke",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    return root, vault, github_report, github_json, product_report, product_json, smoke_log


if __name__ == "__main__":
    unittest.main()
