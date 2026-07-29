import unittest
from pathlib import Path


class ProviderModelDocsTests(unittest.TestCase):
    def test_docs_position_mrcp_parent_and_nmrcp_provider_edition(self):
        readme = Path("README.md").read_text(encoding="utf-8")
        provider_doc = Path("docs/architecture/provider-model.md").read_text(encoding="utf-8")

        self.assertIn("Migration Readiness Control Plane", readme)
        self.assertIn("Nutanix Provider Edition", readme)
        self.assertIn("provider-aware source/target model", readme)
        self.assertIn("MRCP", provider_doc)
        self.assertIn("NMRCP", provider_doc)
        self.assertIn("Do not present NMRCP as fully platform-agnostic", provider_doc)
        self.assertIn("Generalise the framework, not the scoring heuristics", provider_doc)


if __name__ == "__main__":
    unittest.main()
