import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.operations_console import validate_operations_console
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class OperationsConsoleTests(unittest.TestCase):
    def test_generated_operations_console_passes_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_operations_console(out_dir / "operations-console.html", out_dir / "assessment.json")
            console = (out_dir / "operations-console.html").read_text(encoding="utf-8")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("PASS", result.summary())
            self.assertIn("Connect Environments", console)
            self.assertIn("vCenter", console)
            self.assertIn("Prism Central", console)
            self.assertIn("Nutanix Move", console)
            self.assertIn("Run Compatibility Analysis", console)
            self.assertIn("Build Move Plan", console)
            self.assertIn("Do not store credentials", console)

    def test_operations_console_rejects_missing_move_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            console = out_dir / "operations-console.html"
            console.write_text(console.read_text(encoding="utf-8").replace("Nutanix Move", "Move removed"), encoding="utf-8")

            result = validate_operations_console(console, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("Nutanix Move" in error for error in result.errors))

    def test_operations_console_rejects_tampered_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            console = out_dir / "operations-console.html"
            console.write_text(
                console.read_text(encoding="utf-8").replace(
                    '<div class="metric"><strong>3</strong><span>Workloads</span></div>',
                    '<div class="metric"><strong>1</strong><span>Workloads</span></div>',
                ),
                encoding="utf-8",
            )

            result = validate_operations_console(console, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("Workloads" in error or "summary total expected 3" in error for error in result.errors))

    def test_cli_validate_operations_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-operations-console",
                        "--console",
                        str(out_dir / "operations-console.html"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(code, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
