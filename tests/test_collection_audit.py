import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.collection_audit import validate_collection_audit
from nmrcp.inventory import normalize_prism_inventory, normalize_vcenter_inventory
from nmrcp.rvtools import import_rvtools_directory


class CollectionAuditValidationTests(unittest.TestCase):
    def test_validates_vcenter_audit_contract(self):
        inventory = _vcenter_inventory()

        result = validate_collection_audit(inventory)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.collector, "vcenter-rest")

    def test_validates_prism_audit_contract(self):
        inventory = normalize_prism_inventory(
            "https://pc.example.test:9440",
            [
                {
                    "metadata": {"uuid": "uuid-1"},
                    "spec": {"name": "ahv-vm-01", "resources": {"memory_size_mib": 4096}},
                }
            ],
            page_size=50,
            max_pages=1,
        )

        result = validate_collection_audit(inventory)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.collector, "prism-central-v3")

    def test_validates_rvtools_audit_contract(self):
        inventory = import_rvtools_directory(Path("examples/rvtools"), source_name="sample-rvtools")

        result = validate_collection_audit(inventory)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.collector, "rvtools-csv")

    def test_missing_audit_fails_closed(self):
        inventory = _vcenter_inventory()
        del inventory["source"]["collection_audit"]

        result = validate_collection_audit(inventory)

        self.assertFalse(result.ok)
        self.assertIn("source.collection_audit must be an object", result.errors)

    def test_mutating_calls_fail_closed(self):
        inventory = _vcenter_inventory()
        inventory["source"]["collection_audit"]["mutating_calls"] = 1

        result = validate_collection_audit(inventory)

        self.assertFalse(result.ok)
        self.assertIn("source.collection_audit.mutating_calls must be 0", result.errors)

    def test_endpoint_leakage_fails_closed(self):
        inventory = _vcenter_inventory()
        inventory["source"]["collection_audit"]["observed_host"] = "vcsa.example.test"

        result = validate_collection_audit(inventory)

        self.assertFalse(result.ok)
        self.assertIn("source.collection_audit must not duplicate the source endpoint hostname", result.errors)

    def test_sensitive_audit_keys_fail_closed(self):
        inventory = _vcenter_inventory()
        inventory["source"]["collection_audit"]["username"] = "administrator@example.test"

        result = validate_collection_audit(inventory)

        self.assertFalse(result.ok)
        self.assertIn("source.collection_audit.username: sensitive audit key 'username' is not allowed", result.errors)
        self.assertIn(
            "source.collection_audit.username: audit values must not contain email addresses or usernames",
            result.errors,
        )

    def test_vcenter_count_mismatch_fails_closed(self):
        inventory = _vcenter_inventory()
        inventory["source"]["collection_audit"]["details_count"] = 2

        result = validate_collection_audit(inventory)

        self.assertFalse(result.ok)
        self.assertIn("vCenter audit details_count cannot exceed summary_count", result.errors)

    def test_cli_validate_collection_audit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "inventory.json"
            path.write_text(json.dumps(_vcenter_inventory()), encoding="utf-8")

            with patch("sys.stdout"):
                result = main(["validate-collection-audit", "--inventory", str(path)])

        self.assertEqual(result, 0)

    def test_cli_validate_collection_audit_returns_failure(self):
        inventory = copy.deepcopy(_vcenter_inventory())
        inventory["source"]["collection_audit"]["endpoint"] = inventory["source"]["endpoint"]
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "inventory.json"
            path.write_text(json.dumps(inventory), encoding="utf-8")

            with patch("sys.stdout"):
                result = main(["validate-collection-audit", "--inventory", str(path)])

        self.assertEqual(result, 1)


def _vcenter_inventory():
    return normalize_vcenter_inventory(
        "https://vcsa.example.test",
        [{"vm": "vm-42", "name": "app-01", "cpu_count": 2, "memory_size_MiB": 4096}],
        {"vm-42": {"guest_OS": "WINDOWS_SERVER_2019", "disks": [{"capacity_MiB": 10240}]}},
        details_limit=10,
        network_count=1,
    )


if __name__ == "__main__":
    unittest.main()
