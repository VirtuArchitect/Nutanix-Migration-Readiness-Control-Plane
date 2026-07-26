import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.app_map import read_app_map, write_dependency_csv
from nmrcp.cli import main
from nmrcp.dependencies import merge_dependencies


class AppMapImportTests(unittest.TestCase):
    def test_read_app_map_converts_applications_and_edges(self):
        records = read_app_map(Path("examples/sample_app_map.json"))

        self.assertEqual(len(records), 4)
        self.assertIn(
            {
                "source_id": "vm-1001",
                "source_name": "pilot-web-01",
                "dependency_name": "pilot-db-01",
                "dependency_id": "vm-1002",
                "dependency_type": "database",
                "owner": "Platform Team",
                "criticality": "medium",
                "protocol": "",
                "ports": "",
                "direction": "",
                "validation_method": "",
                "notes": "Imported from synthetic application map.",
            },
            records,
        )
        self.assertTrue(any(record["source_name"] == "erp-app-01" and record["dependency_name"] == "erp-db-01" for record in records))

    def test_read_app_map_fails_on_unknown_schema(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "app-map.json"
            path.write_text('{"schema_version":"wrong","applications":[]}', encoding="utf-8")

            with self.assertRaises(ValueError):
                read_app_map(path)

    def test_write_dependency_csv_round_trips_to_dependency_merge(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        records = read_app_map(Path("examples/sample_app_map.json"))

        with tempfile.TemporaryDirectory() as tmp:
            csv_path = write_dependency_csv(records, Path(tmp) / "dependencies.csv")
            with csv_path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))

            enriched = merge_dependencies(inventory, rows)

        self.assertEqual(len(rows), 4)
        pilot = next(workload for workload in enriched["workloads"] if workload["id"] == "vm-1001")
        self.assertEqual([dependency["name"] for dependency in pilot["dependencies"]], ["pilot-db-01", "directory-01"])
        payments = next(workload for workload in enriched["workloads"] if workload["id"] == "vm-3030")
        self.assertEqual(payments["dependencies"][0]["name"], "external-hsm")
        self.assertEqual(payments["dependencies"][0]["criticality"], "critical")

    def test_cli_import_app_map_writes_dependency_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "app-map-dependencies.csv"
            with patch("sys.stdout"):
                result = main(["import-app-map", "--map", "examples/sample_app_map.json", "--out", str(output)])

            self.assertEqual(result, 0)
            text = output.read_text(encoding="utf-8")
            self.assertIn("source_id,source_name,dependency_name", text)
            self.assertIn("pilot-db-01", text)


if __name__ == "__main__":
    unittest.main()
