import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.github_readiness import DEFAULT_REPO_URL, REQUIRED_PUBLICATION_PATHS, check_github_readiness, required_publication_paths, validate_github_publication_review


class GitHubReadinessTests(unittest.TestCase):
    def test_required_publication_paths_include_readiness_gates(self):
        for expected in (
            "docs/operations/README.md",
            "docs/operations/github-readiness.md",
            "docs/operations/vault-readiness.md",
            "docs/operations/product-readiness.md",
            "src/nmrcp/github_readiness.py",
            "src/nmrcp/vault_readiness.py",
            "src/nmrcp/product_readiness.py",
            "docs/operations/collection-proof-report.md",
            "src/nmrcp/collection_proof_report.py",
            "tests/test_collection_proof_report.py",
            "docs/operations/move-plan-brief.md",
            "src/nmrcp/move_plan_brief.py",
            "tests/test_move_plan_brief.py",
            "tests/test_github_readiness.py",
            "tests/test_vault_readiness.py",
            "tests/test_product_readiness.py",
        ):
            self.assertIn(expected, REQUIRED_PUBLICATION_PATHS)

    def test_required_publication_paths_discovers_current_repo_surface(self):
        root = Path.cwd()

        paths = required_publication_paths(root)

        self.assertIn("src/nmrcp/connectors.py", paths)
        self.assertIn("tests/test_connectors.py", paths)
        self.assertIn("docs/operations/live-readiness.md", paths)
        self.assertIn("examples/sample_assessment_intake.csv", paths)
        self.assertIn("scripts/live_collector_smoke.py", paths)
        self.assertIn("PENTEST_SCOPE_TEMPLATE.md", paths)
        self.assertNotIn("src/nmrcp/__pycache__/cli.cpython-314.pyc", paths)
        self.assertFalse(any(path.startswith("outputs/") for path in paths))

    def test_github_readiness_passes_when_required_paths_are_tracked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            git(root, "add", *REQUIRED_PUBLICATION_PATHS)

            result = check_github_readiness(root)

        self.assertEqual(result.status, "pass", result.to_dict())
        self.assertTrue(any(check.name == "git:required-paths-tracked" and check.status == "pass" for check in result.checks))

    def test_github_readiness_fails_when_required_paths_are_untracked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)

            result = check_github_readiness(root)

        self.assertEqual(result.status, "fail")
        tracked = next(check for check in result.checks if check.name == "git:required-paths-tracked")
        self.assertIn("README.md", tracked.detail)
        self.assertTrue(any("git add -- README.md" in action for action in result.next_actions))
        self.assertTrue(any("commit and push" in action for action in result.next_actions))

    def test_github_readiness_fails_on_wrong_remote(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp), remote="https://github.com/example/wrong")
            write_required_paths(root)
            git(root, "add", *REQUIRED_PUBLICATION_PATHS)

            result = check_github_readiness(root)

        self.assertEqual(result.status, "fail")
        remote = next(check for check in result.checks if check.name == "git:remote-origin")
        self.assertIn(DEFAULT_REPO_URL, remote.detail)

    def test_cli_github_readiness_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            git(root, "add", *REQUIRED_PUBLICATION_PATHS)

            with patch("sys.stdout") as stdout:
                code = main(["github-readiness", "--repo-root", str(root), "--json"])

            payload = json.loads("".join(call.args[0] for call in stdout.write.call_args_list))

        self.assertEqual(code, 0)
        self.assertEqual(payload["schema_version"], "nmrcp_github_readiness_v1")
        self.assertEqual(payload["status"], "pass")
        self.assertIn("README.md", payload["required_publication_paths"])
        self.assertTrue(any("Publication gate passed locally" in action for action in payload["next_actions"]))

    def test_github_readiness_markdown_review_includes_actions_and_boundaries(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)

            result = check_github_readiness(root)
            markdown = result.to_markdown()

        self.assertIn("# GitHub Publication Review", markdown)
        self.assertIn("git add -- README.md", markdown)
        self.assertIn("This review did not stage, commit, push, remove, or publish files.", markdown)
        self.assertIn("Do not publish generated `outputs/`", markdown)

    def test_cli_github_readiness_prints_next_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)

            with patch("sys.stdout") as stdout:
                code = main(["github-readiness", "--repo-root", str(root)])

            output = "".join(call.args[0] for call in stdout.write.call_args_list)

        self.assertEqual(code, 1)
        self.assertIn("NEXT: After operator review, stage required publication paths: git add -- README.md", output)

    def test_cli_github_readiness_writes_publication_review_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            review = root / "outputs" / "github-publication-review.md"
            review_json = root / "outputs" / "github-publication-review.json"

            with patch("sys.stdout") as stdout:
                code = main(
                    [
                        "github-readiness",
                        "--repo-root",
                        str(root),
                        "--out",
                        str(review),
                        "--json-out",
                        str(review_json),
                    ]
                )

            output = "".join(call.args[0] for call in stdout.write.call_args_list)
            payload = json.loads(review_json.read_text(encoding="utf-8"))

            self.assertEqual(code, 1)
            self.assertTrue(review.exists())
            self.assertIn("Wrote GitHub publication review:", output)
            self.assertIn("git add -- README.md", review.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], "nmrcp_github_readiness_v1")
            self.assertIn("README.md", payload["required_publication_paths"])

    def test_validate_github_publication_review_accepts_current_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            result = check_github_readiness(root)
            review = root / "outputs" / "github-publication-review.md"
            review_json = root / "outputs" / "github-publication-review.json"
            review.parent.mkdir(parents=True)
            review.write_text(result.to_markdown(), encoding="utf-8")
            review_json.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

            validation = validate_github_publication_review(root, review_json, markdown_report_path=review)

        self.assertTrue(validation.ok, validation.errors)

    def test_validate_github_publication_review_rejects_stale_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            result = check_github_readiness(root).to_dict()
            result["status"] = "pass"
            review_json = root / "outputs" / "github-publication-review.json"
            review_json.parent.mkdir(parents=True)
            review_json.write_text(json.dumps(result, indent=2), encoding="utf-8")

            validation = validate_github_publication_review(root, review_json)

        self.assertFalse(validation.ok)
        self.assertTrue(any("field status does not match current github-readiness" in error for error in validation.errors))

    def test_validate_github_publication_review_rejects_tampered_markdown(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            result = check_github_readiness(root)
            review = root / "outputs" / "github-publication-review.md"
            review_json = root / "outputs" / "github-publication-review.json"
            review.parent.mkdir(parents=True)
            review.write_text(result.to_markdown().replace("This review did not stage, commit, push, remove, or publish files.", "Review complete."), encoding="utf-8")
            review_json.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

            validation = validate_github_publication_review(root, review_json, markdown_report_path=review)

        self.assertFalse(validation.ok)
        self.assertTrue(any("Markdown missing required text" in error for error in validation.errors))

    def test_cli_validate_github_publication_review_reports_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = init_repo(Path(tmp))
            write_required_paths(root)
            result = check_github_readiness(root)
            review = root / "outputs" / "github-publication-review.md"
            review_json = root / "outputs" / "github-publication-review.json"
            review.parent.mkdir(parents=True)
            review.write_text(result.to_markdown(), encoding="utf-8")
            review_json.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")

            with patch("sys.stdout") as stdout:
                code = main(
                    [
                        "validate-github-publication-review",
                        "--repo-root",
                        str(root),
                        "--report",
                        str(review),
                        "--json-report",
                        str(review_json),
                    ]
                )

            output = "".join(call.args[0] for call in stdout.write.call_args_list)

        self.assertEqual(code, 0)
        self.assertIn("PASS: checks=", output)


def init_repo(root: Path, remote: str = DEFAULT_REPO_URL) -> Path:
    git(root, "init")
    git(root, "remote", "add", "origin", remote)
    return root


def write_required_paths(root: Path) -> None:
    for relative in REQUIRED_PUBLICATION_PATHS:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"sample {relative}\n", encoding="utf-8")


def git(root: Path, *args: str) -> None:
    result = subprocess.run(
        ("git", *args),
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(f"git {' '.join(args)} failed: {result.stderr}")


if __name__ == "__main__":
    unittest.main()
