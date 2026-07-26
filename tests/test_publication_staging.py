import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.github_readiness import REQUIRED_PUBLICATION_PATHS
from nmrcp.publication_staging import build_publication_staging_manifest, validate_publication_staging_manifest

from tests.test_github_readiness import git, init_repo, write_required_paths


class PublicationStagingTests(unittest.TestCase):
    def test_required_publication_paths_include_staging_manifest(self):
        self.assertIn("docs/operations/publication-staging.md", REQUIRED_PUBLICATION_PATHS)
        self.assertIn("src/nmrcp/publication_staging.py", REQUIRED_PUBLICATION_PATHS)
        self.assertIn("tests/test_publication_staging.py", REQUIRED_PUBLICATION_PATHS)

    def test_publication_staging_manifest_hashes_required_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)

            result = build_publication_staging_manifest(root)

        self.assertEqual(result.status, "ready_for_operator_staging")
        self.assertIn("git add -- README.md", result.staging_command)
        readme = next(entry for entry in result.entries if entry.path == "README.md")
        self.assertEqual(readme.status, "present")
        self.assertFalse(readme.tracked)
        self.assertEqual(len(readme.sha256 or ""), 64)
        self.assertIn("# Publication Staging Manifest", result.to_markdown())
        self.assertIn("This manifest did not stage, commit, push", result.to_markdown())

    def test_publication_staging_manifest_includes_discovered_repo_surface(self):
        result = build_publication_staging_manifest(Path.cwd())
        paths = {entry.path for entry in result.entries}

        self.assertIn("src/nmrcp/connectors.py", paths)
        self.assertIn("tests/test_connectors.py", paths)
        self.assertIn("docs/operations/live-readiness.md", paths)
        self.assertIn("examples/sample_assessment_intake.csv", paths)
        self.assertIn("scripts/live_collector_smoke.py", paths)
        self.assertFalse(any("__pycache__" in path for path in paths))

    def test_publication_staging_manifest_blocks_missing_required_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            (root / "README.md").unlink()

            result = build_publication_staging_manifest(root)

        self.assertEqual(result.status, "blocked")
        readme = next(entry for entry in result.entries if entry.path == "README.md")
        self.assertEqual(readme.status, "missing")
        self.assertTrue(any("Restore missing required publication paths" in action for action in result.next_actions))

    def test_publication_staging_manifest_surfaces_forbidden_local_candidates_without_blocking(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            output = root / "outputs" / "local-review.json"
            output.parent.mkdir()
            output.write_text("{}", encoding="utf-8")

            result = build_publication_staging_manifest(root)

        self.assertEqual(result.status, "ready_for_operator_staging")
        self.assertIn("outputs/local-review.json", result.forbidden_candidates)
        self.assertTrue(any("forbidden local candidates" in action for action in result.next_actions))

    def test_publication_staging_manifest_passes_when_required_paths_tracked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            git(root, "add", *REQUIRED_PUBLICATION_PATHS)

            result = build_publication_staging_manifest(root)

        self.assertEqual(result.status, "ready_for_operator_staging")
        self.assertTrue(all(entry.tracked for entry in result.entries))
        self.assertTrue(any("already tracked" in action for action in result.next_actions))

    def test_validate_publication_staging_manifest_accepts_current_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            report = root / "outputs" / "publication-staging-manifest.md"
            report_json = root / "outputs" / "publication-staging-manifest.json"
            report.parent.mkdir()
            result = build_publication_staging_manifest(root)
            report.write_text(result.to_markdown(), encoding="utf-8")
            report_json.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

            validation = validate_publication_staging_manifest(root, report_json, markdown_report_path=report)

        self.assertTrue(validation.ok, validation.errors)

    def test_validate_publication_staging_manifest_rejects_stale_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            report_json = root / "outputs" / "publication-staging-manifest.json"
            report_json.parent.mkdir()
            payload = build_publication_staging_manifest(root).to_dict()
            payload["staging_command"] = "git add -- README.md"
            report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            validation = validate_publication_staging_manifest(root, report_json)

        self.assertFalse(validation.ok)
        self.assertTrue(any("field staging_command does not match current staging state" in error for error in validation.errors))

    def test_validate_publication_staging_manifest_rejects_tampered_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            report = root / "outputs" / "publication-staging-manifest.md"
            report_json = root / "outputs" / "publication-staging-manifest.json"
            report.parent.mkdir()
            result = build_publication_staging_manifest(root)
            report.write_text(result.to_markdown().replace("Review every hash before running the staging command.", "Looks fine."), encoding="utf-8")
            report_json.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

            validation = validate_publication_staging_manifest(root, report_json, markdown_report_path=report)

        self.assertFalse(validation.ok)
        self.assertTrue(any("Markdown missing required text" in error for error in validation.errors))

    def test_cli_publication_staging_manifest_writes_and_validates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            report = root / "outputs" / "publication-staging-manifest.md"
            report_json = root / "outputs" / "publication-staging-manifest.json"

            with patch("sys.stdout") as stdout:
                code = main(
                    [
                        "publication-staging-manifest",
                        "--repo-root",
                        str(root),
                        "--out",
                        str(report),
                        "--json-out",
                        str(report_json),
                    ]
                )
            output = "".join(call.args[0] for call in stdout.write.call_args_list)

            with patch("sys.stdout") as validate_stdout:
                validation_code = main(
                    [
                        "validate-publication-staging-manifest",
                        "--repo-root",
                        str(root),
                        "--report",
                        str(report),
                        "--json-report",
                        str(report_json),
                    ]
                )
            validation_output = "".join(call.args[0] for call in validate_stdout.write.call_args_list)

        self.assertEqual(code, 0)
        self.assertIn("Wrote publication staging manifest:", output)
        self.assertIn("STAGE: git add -- README.md", output)
        self.assertEqual(validation_code, 0)
        self.assertIn("PASS:", validation_output)

    def test_cli_publication_staging_manifest_ignores_prior_self_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            report = root / "outputs" / "publication-staging-manifest.md"
            report_json = root / "outputs" / "publication-staging-manifest.json"
            report.parent.mkdir(parents=True)
            report.write_text("# prior manifest\n", encoding="utf-8")
            report_json.write_text("{}\n", encoding="utf-8")

            with patch("sys.stdout"):
                code = main(
                    [
                        "publication-staging-manifest",
                        "--repo-root",
                        str(root),
                        "--out",
                        str(report),
                        "--json-out",
                        str(report_json),
                    ]
                )
                validation_code = main(
                    [
                        "validate-publication-staging-manifest",
                        "--repo-root",
                        str(root),
                        "--report",
                        str(report),
                        "--json-report",
                        str(report_json),
                    ]
                )

        self.assertEqual(code, 0)
        self.assertEqual(validation_code, 0)


if __name__ == "__main__":
    unittest.main()
