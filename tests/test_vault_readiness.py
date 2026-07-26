import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.vault_readiness import REQUIRED_VAULT_NOTES, check_vault_readiness


class VaultReadinessTests(unittest.TestCase):
    def test_vault_readiness_passes_when_notes_and_links_exist(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, vault = build_repo_and_vault(Path(tmp))

            result = check_vault_readiness(root, vault)

        self.assertEqual(result.status, "pass", result.to_dict())
        self.assertTrue(any(check.name == "vault:readme-links" and check.status == "pass" for check in result.checks))

    def test_vault_readiness_fails_when_operation_note_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, vault = build_repo_and_vault(Path(tmp))
            (vault / "Source Network Validation.md").unlink()

            result = check_vault_readiness(root, vault)

        self.assertEqual(result.status, "fail")
        required = next(check for check in result.checks if check.name == "vault:required-notes")
        self.assertIn("Source Network Validation.md", required.detail)

    def test_vault_readiness_fails_when_readme_link_is_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, vault = build_repo_and_vault(Path(tmp))
            readme = vault / "README.md"
            readme.write_text(readme.read_text(encoding="utf-8").replace("- [[GitHub Readiness]]\n", ""), encoding="utf-8")

            result = check_vault_readiness(root, vault)

        self.assertEqual(result.status, "fail")
        links = next(check for check in result.checks if check.name == "vault:readme-links")
        self.assertIn("GitHub Readiness.md", links.detail)

    def test_cli_vault_readiness_writes_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, vault = build_repo_and_vault(Path(tmp))

            with patch("sys.stdout") as stdout:
                code = main(["vault-readiness", "--repo-root", str(root), "--vault", str(vault), "--json"])

            payload = json.loads("".join(call.args[0] for call in stdout.write.call_args_list))

        self.assertEqual(code, 0)
        self.assertEqual(payload["schema_version"], "nmrcp_vault_readiness_v1")
        self.assertEqual(payload["status"], "pass")


def build_repo_and_vault(root: Path) -> tuple[Path, Path]:
    repo = root / "repo"
    vault = root / "vault"
    operations = repo / "docs" / "operations"
    operations.mkdir(parents=True)
    vault.mkdir()
    for name in ("github-readiness.md", "source-network-validation.md", "metadata-enrichment.md"):
        (operations / name).write_text(f"# {name}\n", encoding="utf-8")
    notes = [
        *REQUIRED_VAULT_NOTES,
        "GitHub Readiness.md",
        "Source Network Validation.md",
        "Workload Metadata Enrichment.md",
    ]
    for note in set(notes):
        (vault / note).write_text(f"# {note.removesuffix('.md')}\n", encoding="utf-8")
    (vault / "README.md").write_text(
        "\n".join(
            [
                "# Vault",
                "- [[Implementation Log]]",
                "- [[Architecture]]",
                "- [[Security Model]]",
                "- [[GitHub Readiness]]",
                "- [[Source Network Validation]]",
                "- [[Workload Metadata Enrichment]]",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return repo, vault


if __name__ == "__main__":
    unittest.main()
