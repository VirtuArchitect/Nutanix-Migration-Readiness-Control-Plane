import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from nmrcp.cli import main
from nmrcp.inventory_validation import validate_inventory


class InventoryValidationTests(unittest.TestCase):
    def test_valid_inventory_can_pass_with_warnings(self):
        result = validate_inventory(
            {
                "workloads": [
                    {
                        "id": "vm-1",
                        "name": "app",
                        "owner": "Unassigned",
                        "guest_os": "",
                        "networking": {},
                        "snapshots": {},
                        "tools": {},
                        "backup": {},
                        "cpu": 2,
                        "memory_gib": 4,
                        "disk_gib": 40,
                        "dependencies": [],
                    }
                ]
            }
        )

        self.assertTrue(result.ok)
        self.assertGreater(len(result.warnings), 0)

    def test_duplicate_id_fails_validation(self):
        result = validate_inventory(
            {
                "workloads": [
                    {"id": "vm-1", "name": "one"},
                    {"id": "vm-1", "name": "two"},
                ]
            }
        )

        self.assertFalse(result.ok)
        self.assertTrue(any("duplicate workload id" in error for error in result.errors))

    def test_validate_inventory_cli_strict_fails_on_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "inventory.json"
            path.write_text(
                '{"workloads":[{"id":"vm-1","name":"app","networking":{},"snapshots":{},"tools":{},"backup":{}}]}',
                encoding="utf-8",
            )
            stream = io.StringIO()
            with redirect_stdout(stream):
                code = main(["validate-inventory", "--inventory", str(path), "--strict"])

            self.assertEqual(code, 1)
            self.assertIn("WARNING:", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
