import unittest
from pathlib import Path


class TesterAlphaDocsTests(unittest.TestCase):
    def test_readme_describes_product_and_served_console_connectivity(self):
        readme = Path("README.md").read_text(encoding="utf-8")
        normalized = " ".join(readme.split())

        for expected in (
            "local-first operations console and evidence engine",
            "connect approved environments",
            "score workload readiness",
            "run the local served console through Docker or Python",
            "vCenter, Prism Central, Nutanix Move, AHV, NC2, ESXi",
            "docs/operations/tester-alpha-release.md",
        ):
            self.assertIn(expected, readme)
        self.assertIn("The GitHub Pages demo is generated from sample inventory and cannot contact infrastructure", normalized)

    def test_tester_alpha_docs_define_release_and_feedback_contract(self):
        release_doc = Path("docs/operations/tester-alpha-release.md").read_text(encoding="utf-8")
        issue_template = Path(".github/ISSUE_TEMPLATE/tester_connection_report.md").read_text(encoding="utf-8")

        for expected in (
            "Tester Alpha Release",
            "GHCR image",
            "Connectivity Boundary",
            "run_metadata",
            "product_version",
            "mutation policy",
        ):
            self.assertIn(expected, release_doc)
        self.assertIn("NMRCP run ID", issue_template)
        self.assertIn("Environment gates validated", issue_template)


if __name__ == "__main__":
    unittest.main()
