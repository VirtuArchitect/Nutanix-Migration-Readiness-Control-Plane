import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.github_readiness import REQUIRED_PUBLICATION_PATHS, check_github_readiness, required_publication_paths
from nmrcp.mvp_proof_bundle import package_mvp_proof
from nmrcp.product_readiness import check_product_readiness, validate_product_readiness_report
from nmrcp.publication_staging import build_publication_staging_manifest
from nmrcp.vault_readiness import REQUIRED_VAULT_NOTES, operation_note_name

from tests.test_github_readiness import git, init_repo


class ProductReadinessTests(unittest.TestCase):
    def test_product_readiness_reports_github_and_mvp_blockers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = check_product_readiness(root, vault_path=vault)

        self.assertEqual(result.status, "fail")
        gates = {gate.name: gate for gate in result.gates}
        self.assertEqual(gates["github-readiness"].status, "fail")
        self.assertEqual(gates["vault-readiness"].status, "pass")
        self.assertEqual(gates["mvp-audit"].status, "partial")
        self.assertTrue(any("git add -- README.md" in action for action in result.next_actions))
        self.assertTrue(any("commit and push" in action for action in result.next_actions))
        self.assertTrue(any("Generate and validate GitHub publication review artifacts" in action for action in result.next_actions))
        self.assertTrue(any("approved live endpoint and Nutanix Move proof" in action for action in result.next_actions))

    def test_product_readiness_accepts_current_publication_review_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            github = check_github_readiness(root)
            review = root / "outputs" / "github-publication-review.md"
            review_json = root / "outputs" / "github-publication-review.json"
            review.parent.mkdir(parents=True)
            review.write_text(github.to_markdown(), encoding="utf-8")
            review_json.write_text(json.dumps(github.to_dict(), indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = check_product_readiness(
                    root,
                    vault_path=vault,
                    github_publication_review_path=review,
                    github_publication_review_json_path=review_json,
                )

        gates = {gate.name: gate for gate in result.gates}
        self.assertEqual(gates["github-publication-review"].status, "pass")
        self.assertTrue(any("commit and push" in action for action in result.next_actions))
        self.assertFalse(any("Generate and validate GitHub publication review artifacts" in action for action in result.next_actions))

    def test_product_readiness_accepts_current_publication_staging_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            staging = build_publication_staging_manifest(root)
            staging_report = root / "outputs" / "publication-staging-manifest.md"
            staging_json = root / "outputs" / "publication-staging-manifest.json"
            staging_report.parent.mkdir(parents=True)
            staging_report.write_text(staging.to_markdown(), encoding="utf-8")
            staging_json.write_text(json.dumps(staging.to_dict(), indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = check_product_readiness(
                    root,
                    vault_path=vault,
                    publication_staging_manifest_path=staging_report,
                    publication_staging_manifest_json_path=staging_json,
                )

        gates = {gate.name: gate for gate in result.gates}
        self.assertEqual(gates["publication-staging-manifest"].status, "pass")

    def test_product_readiness_rejects_stale_publication_staging_manifest(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            payload = build_publication_staging_manifest(root).to_dict()
            payload["status"] = "blocked"
            staging_json = root / "outputs" / "publication-staging-manifest.json"
            staging_json.parent.mkdir(parents=True)
            staging_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = check_product_readiness(
                    root,
                    vault_path=vault,
                    publication_staging_manifest_json_path=staging_json,
                )

        gates = {gate.name: gate for gate in result.gates}
        self.assertEqual(gates["publication-staging-manifest"].status, "fail")
        self.assertTrue(any("field status does not match current staging state" in blocker for blocker in gates["publication-staging-manifest"].blockers))
        self.assertTrue(any("Regenerate and validate the publication staging manifest" in action for action in result.next_actions))

    def test_validate_product_readiness_report_ignores_own_outputs_for_staging_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            staging = build_publication_staging_manifest(root)
            staging_report = root / "outputs" / "publication-staging-manifest.md"
            staging_json = root / "outputs" / "publication-staging-manifest.json"
            product_report = root / "outputs" / "product-readiness-report.md"
            product_json = root / "outputs" / "product-readiness-report.json"
            staging_report.parent.mkdir(parents=True)
            staging_report.write_text(staging.to_markdown(), encoding="utf-8")
            staging_json.write_text(json.dumps(staging.to_dict(), indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                readiness = check_product_readiness(
                    root,
                    vault_path=vault,
                    publication_staging_manifest_path=staging_report,
                    publication_staging_manifest_json_path=staging_json,
                    publication_staging_ignored_paths=(product_report, product_json),
                )
                product_report.write_text(readiness.to_markdown(), encoding="utf-8")
                product_json.write_text(json.dumps(readiness.to_dict(), indent=2), encoding="utf-8")
                validation = validate_product_readiness_report(
                    root,
                    product_json,
                    markdown_report_path=product_report,
                    vault_path=vault,
                    publication_staging_manifest_path=staging_report,
                    publication_staging_manifest_json_path=staging_json,
                )

        self.assertTrue(validation.ok, validation.errors)

    def test_product_readiness_markdown_carries_boundary_and_review_gate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            github = check_github_readiness(root)
            review = root / "outputs" / "github-publication-review.md"
            review_json = root / "outputs" / "github-publication-review.json"
            review.parent.mkdir(parents=True)
            review.write_text(github.to_markdown(), encoding="utf-8")
            review_json.write_text(json.dumps(github.to_dict(), indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                markdown = check_product_readiness(
                    root,
                    vault_path=vault,
                    github_publication_review_path=review,
                    github_publication_review_json_path=review_json,
                ).to_markdown()

        self.assertIn("# Product Readiness Report", markdown)
        self.assertIn("github-publication-review", markdown)
        self.assertIn("Do not claim external handoff readiness", markdown)

    def test_product_readiness_rejects_stale_publication_review_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            github = check_github_readiness(root).to_dict()
            github["status"] = "pass"
            review_json = root / "outputs" / "github-publication-review.json"
            review_json.parent.mkdir(parents=True)
            review_json.write_text(json.dumps(github, indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = check_product_readiness(root, vault_path=vault, github_publication_review_json_path=review_json)

        gates = {gate.name: gate for gate in result.gates}
        self.assertEqual(gates["github-publication-review"].status, "fail")
        self.assertTrue(any("field status does not match current github-readiness" in blocker for blocker in gates["github-publication-review"].blockers))
        self.assertTrue(any("Regenerate GitHub publication review artifacts" in action for action in result.next_actions))

    def test_validate_product_readiness_report_accepts_current_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            github = check_github_readiness(root)
            review = root / "outputs" / "github-publication-review.md"
            review_json = root / "outputs" / "github-publication-review.json"
            product_report = root / "outputs" / "product-readiness-report.md"
            product_json = root / "outputs" / "product-readiness-report.json"
            review.parent.mkdir(parents=True)
            review.write_text(github.to_markdown(), encoding="utf-8")
            review_json.write_text(json.dumps(github.to_dict(), indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                readiness = check_product_readiness(
                    root,
                    vault_path=vault,
                    github_publication_review_path=review,
                    github_publication_review_json_path=review_json,
                )
                product_report.write_text(readiness.to_markdown(), encoding="utf-8")
                product_json.write_text(json.dumps(readiness.to_dict(), indent=2), encoding="utf-8")
                validation = validate_product_readiness_report(
                    root,
                    product_json,
                    markdown_report_path=product_report,
                    vault_path=vault,
                    github_publication_review_path=review,
                    github_publication_review_json_path=review_json,
                )

        self.assertTrue(validation.ok, validation.errors)

    def test_validate_product_readiness_report_rejects_stale_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            product_json = root / "outputs" / "product-readiness-report.json"
            product_json.parent.mkdir(parents=True)

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                payload = check_product_readiness(root, vault_path=vault).to_dict()
            payload["status"] = "pass"
            product_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                validation = validate_product_readiness_report(root, product_json, vault_path=vault)

        self.assertFalse(validation.ok)
        self.assertTrue(any("field status does not match current product-readiness" in error for error in validation.errors))

    def test_validate_product_readiness_report_rejects_tampered_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            product_report = root / "outputs" / "product-readiness-report.md"
            product_json = root / "outputs" / "product-readiness-report.json"
            product_report.parent.mkdir(parents=True)

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                readiness = check_product_readiness(root, vault_path=vault)
                product_report.write_text(
                    readiness.to_markdown().replace("This report did not contact vCenter, Prism Central, or Nutanix Move.", "External systems checked."),
                    encoding="utf-8",
                )
                product_json.write_text(json.dumps(readiness.to_dict(), indent=2), encoding="utf-8")
                validation = validate_product_readiness_report(
                    root,
                    product_json,
                    markdown_report_path=product_report,
                    vault_path=vault,
                )

        self.assertFalse(validation.ok)
        self.assertTrue(any("Markdown missing required text" in error for error in validation.errors))

    def test_product_readiness_passes_publication_and_vault_when_paths_are_tracked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            git(root, "add", *required_publication_paths(root))
            vault = build_matching_vault(Path(tmp) / "vault", root)

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = check_product_readiness(root, vault_path=vault)

        self.assertEqual(result.status, "partial")
        gates = {gate.name: gate for gate in result.gates}
        self.assertEqual(gates["github-readiness"].status, "pass")
        self.assertEqual(gates["vault-readiness"].status, "pass")
        self.assertEqual(gates["mvp-audit"].status, "partial")

    def test_product_readiness_forwards_mvp_evidence_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            git(root, "add", *required_publication_paths(root))
            vault = build_matching_vault(Path(tmp) / "vault", root)
            assessment_dir = root / "outputs" / "assessment"
            intake = root / "outputs" / "assessment-intake.csv"
            live = root / "outputs" / "live-proof.json"
            move = root / "outputs" / "move-proof.json"

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit(status="pass")) as audit:
                result = check_product_readiness(
                    root,
                    vault_path=vault,
                    assessment_dir=assessment_dir,
                    assessment_intake_path=intake,
                    live_proof_path=live,
                    move_proof_path=move,
                )

        self.assertEqual(result.status, "pass")
        audit.assert_called_once()
        _, kwargs = audit.call_args
        self.assertEqual(kwargs["assessment_dir"], assessment_dir)
        self.assertEqual(kwargs["assessment_intake_path"], intake)
        self.assertEqual(kwargs["live_proof_path"], live)
        self.assertEqual(kwargs["move_proof_path"], move)

    def test_product_readiness_accepts_verified_mvp_proof_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            package = write_minimal_mvp_proof_package(root)

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = check_product_readiness(root, vault_path=vault, mvp_proof_package_path=package)

        gates = {gate.name: gate for gate in result.gates}
        self.assertEqual(gates["mvp-proof-package"].status, "pass")
        self.assertIn("roles=1", gates["mvp-proof-package"].summary)

    def test_product_readiness_rejects_invalid_mvp_proof_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            package = root / "outputs" / "missing-proof.zip"

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                result = check_product_readiness(root, vault_path=vault, mvp_proof_package_path=package)

        gates = {gate.name: gate for gate in result.gates}
        self.assertEqual(gates["mvp-proof-package"].status, "fail")
        self.assertTrue(any("Regenerate and verify the MVP proof package" in action for action in result.next_actions))

    def test_cli_product_readiness_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()), patch("sys.stdout") as stdout:
                code = main(["product-readiness", "--repo-root", str(root), "--vault", str(vault), "--json"])

            payload = json.loads("".join(call.args[0] for call in stdout.write.call_args_list))

        self.assertEqual(code, 1)
        self.assertEqual(payload["schema_version"], "nmrcp_product_readiness_v1")
        self.assertEqual(payload["status"], "fail")

    def test_cli_product_readiness_accepts_publication_review_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            github = check_github_readiness(root)
            review = root / "outputs" / "github-publication-review.md"
            review_json = root / "outputs" / "github-publication-review.json"
            review.parent.mkdir(parents=True)
            review.write_text(github.to_markdown(), encoding="utf-8")
            review_json.write_text(json.dumps(github.to_dict(), indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()), patch("sys.stdout") as stdout:
                code = main(
                    [
                        "product-readiness",
                        "--repo-root",
                        str(root),
                        "--vault",
                        str(vault),
                        "--github-publication-review",
                        str(review),
                        "--github-publication-review-json",
                        str(review_json),
                        "--json",
                    ]
                )

            payload = json.loads("".join(call.args[0] for call in stdout.write.call_args_list))

        self.assertEqual(code, 1)
        gates = {gate["name"]: gate for gate in payload["gates"]}
        self.assertEqual(gates["github-publication-review"]["status"], "pass")

    def test_cli_product_readiness_accepts_publication_staging_manifest_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            staging = build_publication_staging_manifest(root)
            staging_report = root / "outputs" / "publication-staging-manifest.md"
            staging_json = root / "outputs" / "publication-staging-manifest.json"
            staging_report.parent.mkdir(parents=True)
            staging_report.write_text(staging.to_markdown(), encoding="utf-8")
            staging_json.write_text(json.dumps(staging.to_dict(), indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()), patch("sys.stdout") as stdout:
                code = main(
                    [
                        "product-readiness",
                        "--repo-root",
                        str(root),
                        "--vault",
                        str(vault),
                        "--publication-staging-manifest",
                        str(staging_report),
                        "--publication-staging-manifest-json",
                        str(staging_json),
                        "--json",
                    ]
                )

            payload = json.loads("".join(call.args[0] for call in stdout.write.call_args_list))

        self.assertEqual(code, 1)
        gates = {gate["name"]: gate for gate in payload["gates"]}
        self.assertEqual(gates["publication-staging-manifest"]["status"], "pass")

    def test_cli_product_readiness_accepts_mvp_proof_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            package = write_minimal_mvp_proof_package(root)

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()), patch("sys.stdout") as stdout:
                code = main(
                    [
                        "product-readiness",
                        "--repo-root",
                        str(root),
                        "--vault",
                        str(vault),
                        "--mvp-proof-package",
                        str(package),
                        "--json",
                    ]
                )

            payload = json.loads("".join(call.args[0] for call in stdout.write.call_args_list))

        self.assertEqual(code, 1)
        gates = {gate["name"]: gate for gate in payload["gates"]}
        self.assertEqual(gates["mvp-proof-package"]["status"], "pass")

    def test_cli_product_readiness_writes_report_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            github = check_github_readiness(root)
            review = root / "outputs" / "github-publication-review.md"
            review_json = root / "outputs" / "github-publication-review.json"
            product_report = root / "outputs" / "product-readiness-report.md"
            product_json = root / "outputs" / "product-readiness-report.json"
            review.parent.mkdir(parents=True)
            review.write_text(github.to_markdown(), encoding="utf-8")
            review_json.write_text(json.dumps(github.to_dict(), indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()), patch("sys.stdout") as stdout:
                code = main(
                    [
                        "product-readiness",
                        "--repo-root",
                        str(root),
                        "--vault",
                        str(vault),
                        "--github-publication-review",
                        str(review),
                        "--github-publication-review-json",
                        str(review_json),
                        "--out",
                        str(product_report),
                        "--json-out",
                        str(product_json),
                    ]
                )

            output = "".join(call.args[0] for call in stdout.write.call_args_list)
            report_exists = product_report.exists()
            json_exists = product_json.exists()

        self.assertEqual(code, 1)
        self.assertTrue(report_exists)
        self.assertTrue(json_exists)
        self.assertIn("Wrote product readiness report:", output)
        self.assertIn("Wrote product readiness report JSON:", output)

    def test_cli_validate_product_readiness_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_product_repo(Path(tmp) / "repo")
            build_minimal_product_repo(root)
            vault = build_matching_vault(Path(tmp) / "vault", root)
            github = check_github_readiness(root)
            review = root / "outputs" / "github-publication-review.md"
            review_json = root / "outputs" / "github-publication-review.json"
            product_report = root / "outputs" / "product-readiness-report.md"
            product_json = root / "outputs" / "product-readiness-report.json"
            review.parent.mkdir(parents=True)
            review.write_text(github.to_markdown(), encoding="utf-8")
            review_json.write_text(json.dumps(github.to_dict(), indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()):
                readiness = check_product_readiness(
                    root,
                    vault_path=vault,
                    github_publication_review_path=review,
                    github_publication_review_json_path=review_json,
                )
                product_report.write_text(readiness.to_markdown(), encoding="utf-8")
                product_json.write_text(json.dumps(readiness.to_dict(), indent=2), encoding="utf-8")

            with patch("nmrcp.product_readiness.audit_mvp", return_value=fake_mvp_audit()), patch("sys.stdout") as stdout:
                code = main(
                    [
                        "validate-product-readiness-report",
                        "--repo-root",
                        str(root),
                        "--vault",
                        str(vault),
                        "--github-publication-review",
                        str(review),
                        "--github-publication-review-json",
                        str(review_json),
                        "--report",
                        str(product_report),
                        "--json-report",
                        str(product_json),
                    ]
                )

            output = "".join(call.args[0] for call in stdout.write.call_args_list)

        self.assertEqual(code, 0)
        self.assertIn("PASS:", output)


def build_minimal_product_repo(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    for relative in REQUIRED_PUBLICATION_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"sample {relative}\n", encoding="utf-8")
    for relative in (
        "src/nmrcp/connectors.py",
        "src/nmrcp/collection_workflow.py",
        "src/nmrcp/live_readiness.py",
        "src/nmrcp/assessment_intake.py",
        "tests/test_connectors.py",
        "tests/test_collection_workflow.py",
        "tests/test_live_readiness.py",
        "tests/test_assessment_intake.py",
        "scripts/live_collector_smoke.py",
        "docs/operations/source-collection-workflow.md",
        "docs/operations/live-readiness.md",
        "docs/operations/assessment-intake.md",
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"sample {relative}\n", encoding="utf-8")


def init_product_repo(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    return init_repo(root)


def build_matching_vault(vault: Path, repo: Path) -> Path:
    vault.mkdir()
    operations = repo / "docs" / "operations"
    notes = set(REQUIRED_VAULT_NOTES)
    notes.update(operation_note_name(path) for path in operations.glob("*.md") if path.stem.lower() != "readme")
    notes.update({"GitHub Readiness.md", "Live Readiness.md", "Assessment Intake.md", "Source Collection Workflow.md"})
    for note in notes:
        (vault / note).write_text(f"# {note.removesuffix('.md')}\n", encoding="utf-8")
    links = [f"- [[{note.removesuffix('.md')}]]" for note in sorted(notes) if note != "README.md"]
    (vault / "README.md").write_text("# Vault\n" + "\n".join(links) + "\n", encoding="utf-8")
    return vault


def write_minimal_mvp_proof_package(root: Path) -> Path:
    audit = root / "outputs" / "mvp-audit.json"
    package = root / "outputs" / "mvp-proof.zip"
    audit.parent.mkdir(parents=True, exist_ok=True)
    audit.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_mvp_readiness_audit_v1",
                "status": "partial",
                "summary": {"pass": 5, "partial": 2, "fail": 0, "requirements": 7},
                "requirements": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    package_mvp_proof(package, mvp_audit_path=audit)
    return package


def fake_mvp_audit(status: str = "partial"):
    requirements = (
        SimpleNamespace(
            id="read_only_collection",
            errors=(),
            warnings=() if status == "pass" else ("Real vCenter and Prism Central endpoints still need approved lab/customer validation.",),
        ),
        SimpleNamespace(
            id="move_ready_plan",
            errors=(),
            warnings=() if status == "pass" else ("Real Nutanix Move appliance API behavior is not validated; current payload remains dry-run review evidence.",),
        ),
    )
    return SimpleNamespace(
        status=status,
        requirements=requirements,
        summary=lambda: f"{status.upper()}: pass={7 if status == 'pass' else 5}, partial={0 if status == 'pass' else 2}, fail=0, requirements=7",
    )


if __name__ == "__main__":
    unittest.main()
