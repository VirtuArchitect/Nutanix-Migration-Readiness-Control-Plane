import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.environment_access import evaluate_environment_access, required_gates


class EnvironmentAccessTests(unittest.TestCase):
    def test_dev_read_requires_base_gates(self):
        result = evaluate_environment_access(
            "dev",
            "pc",
            "read",
            {"source_scope_approved": True, "credential_source_approved": True},
        )

        self.assertEqual(result.status, "pass")
        self.assertEqual(result.missing_gates, ())

    def test_production_write_requires_environment_and_target_gates(self):
        gates = required_gates("production", "move", "write")

        self.assertIn("cab_approval", gates)
        self.assertIn("backup_verified", gates)
        self.assertIn("production_write_break_glass", gates)
        self.assertIn("move_lab_or_approved_appliance", gates)

    def test_production_write_blocks_until_all_gates_are_satisfied(self):
        result = evaluate_environment_access(
            "production",
            "move",
            "write",
            {
                "source_scope_approved": True,
                "credential_source_approved": True,
                "change_reference": "CHG-0001",
                "rollback_plan": True,
                "write_scope_approved": True,
            },
        )

        self.assertEqual(result.status, "blocked")
        self.assertIn("cab_approval", result.missing_gates)
        self.assertIn("move_lab_or_approved_appliance", result.missing_gates)

    def test_cli_environment_access_writes_json_and_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "access.json"
            with patch("sys.stdout"):
                code = main(
                    [
                        "environment-access",
                        "--environment",
                        "production",
                        "--target",
                        "esxi",
                        "--mode",
                        "write",
                        "--gate",
                        "source_scope_approved",
                        "--json-out",
                        str(out),
                    ]
                )

            self.assertEqual(code, 1)
            self.assertTrue(out.exists())

    def test_cli_environment_access_passes_when_dev_read_gates_are_satisfied(self):
        with patch("sys.stdout"):
            code = main(
                [
                    "environment-access",
                    "--environment",
                    "dev",
                    "--target",
                    "vcenter",
                    "--mode",
                    "read",
                    "--gate",
                    "source_scope_approved",
                    "--gate",
                    "credential_source_approved",
                ]
            )

        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
