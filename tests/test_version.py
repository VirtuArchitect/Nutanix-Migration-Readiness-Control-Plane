import io
import json
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp import __version__
from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class VersionTests(unittest.TestCase):
    def test_package_version_matches_project_metadata(self):
        metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

        self.assertEqual(metadata["project"]["version"], __version__)

    def test_cli_version_command_prints_product_version(self):
        stdout = io.StringIO()

        with patch("sys.stdout", stdout):
            code = main(["version"])

        self.assertEqual(code, 0)
        self.assertEqual(stdout.getvalue().strip(), __version__)

    def test_operations_console_payload_and_html_include_version(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            write_assessment(inventory, assessments, waves, out_dir)
            console = (out_dir / "operations-console.html").read_text(encoding="utf-8")

        self.assertIn(f"Version {__version__}", console)
        self.assertIn(f"&quot;product_version&quot;:&quot;{__version__}&quot;", console)


if __name__ == "__main__":
    unittest.main()
