import json
import tempfile
import unittest
from pathlib import Path

from nmrcp.dependencies import (
    apply_dependency_readiness_gates,
    dependency_sequence,
    merge_dependencies,
    read_dependency_csv,
)
from nmrcp.scoring import assess_inventory


class DependencyTests(unittest.TestCase):
    def test_dependency_csv_merges_by_id_and_tracks_unmatched(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        dependencies = read_dependency_csv(Path("examples/sample_dependencies.csv"))

        enriched = merge_dependencies(inventory, dependencies)

        by_id = {workload["id"]: workload for workload in enriched["workloads"]}
        self.assertEqual(len(by_id["vm-1001"]["dependencies"]), 1)
        self.assertEqual(len(by_id["vm-2020"]["dependencies"]), 1)
        self.assertEqual(by_id["vm-2020"]["dependencies"][0]["id"], "vm-2021")
        self.assertEqual(by_id["vm-2020"]["dependencies"][0]["type"], "database")
        self.assertEqual(by_id["vm-2020"]["dependencies"][0]["criticality"], "high")
        self.assertEqual(len(by_id["vm-3030"]["dependencies"]), 1)
        self.assertEqual(by_id["vm-3030"]["dependencies"][0]["type"], "external-service")
        self.assertEqual(by_id["vm-3030"]["dependencies"][0]["criticality"], "critical")
        self.assertEqual(len(enriched["unmatched_dependencies"]), 1)
        self.assertEqual(enriched["source"]["dependency_records"], 4)

    def test_dependency_csv_requires_dependency_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text("source_id,owner\nvm-1,apps\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                read_dependency_csv(path)

    def test_dependency_sequence_orders_dependency_before_app(self):
        inventory = {
            "workloads": [
                {
                    "id": "app",
                    "name": "app",
                    "guest_os": "Ubuntu Linux 22.04",
                    "networking": {},
                    "tools": {"vmware_tools": True, "virtio_ready": True},
                    "backup": {"protected": True},
                    "vendor_support": ["ahv"],
                    "dependencies": [{"id": "db", "name": "db", "owner": "data"}],
                },
                {
                    "id": "db",
                    "name": "db",
                    "guest_os": "Ubuntu Linux 22.04",
                    "networking": {},
                    "tools": {"vmware_tools": True, "virtio_ready": True},
                    "backup": {"protected": True},
                    "vendor_support": ["ahv"],
                    "dependencies": [],
                },
            ]
        }
        assessments = assess_inventory(inventory)

        self.assertEqual(dependency_sequence(inventory, assessments), ["db", "app"])

    def test_dependency_gate_holds_app_when_internal_dependency_not_ready(self):
        inventory = {
            "workloads": [
                {
                    "id": "app",
                    "name": "app",
                    "guest_os": "Ubuntu Linux 22.04",
                    "networking": {},
                    "tools": {"vmware_tools": True, "virtio_ready": True},
                    "backup": {"protected": True},
                    "vendor_support": ["ahv"],
                    "dependencies": [{"id": "db", "name": "db", "owner": "data"}],
                },
                {
                    "id": "db",
                    "name": "db",
                    "guest_os": "Ubuntu Linux 22.04",
                    "networking": {},
                    "tools": {"vmware_tools": True, "virtio_ready": False},
                    "backup": {"protected": False},
                    "vendor_support": ["ahv"],
                    "dependencies": [],
                },
            ]
        }
        assessments = apply_dependency_readiness_gates(inventory, assess_inventory(inventory))
        by_id = {assessment.workload_id: assessment for assessment in assessments}

        self.assertEqual(by_id["db"].readiness, "blocked")
        self.assertEqual(by_id["app"].readiness, "prepare")
        self.assertIn("dependency_not_ready", [finding.code for finding in by_id["app"].findings])


if __name__ == "__main__":
    unittest.main()
