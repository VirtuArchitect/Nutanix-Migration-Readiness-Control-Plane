import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.rvtools import import_rvtools_directory


class RVToolsImportTests(unittest.TestCase):
    def test_import_maps_common_rvtools_csv_exports(self):
        inventory = import_rvtools_directory(Path("examples/rvtools"), source_name="sample-rvtools")

        self.assertEqual(inventory["source"]["system"], "rvtools-csv")
        self.assertEqual(inventory["source"]["mode"], "offline-import")
        self.assertEqual(inventory["source"]["endpoint"], "sample-rvtools")
        self.assertEqual(len(inventory["workloads"]), 3)
        audit = inventory["source"]["collection_audit"]
        self.assertEqual(audit["schema"], "nmrcp_collection_audit_v1")
        self.assertEqual(audit["mode"], "offline-import")
        self.assertEqual(audit["credential_storage"], "not_used")
        self.assertFalse(audit["endpoint_configured"])
        self.assertEqual(audit["workloads_count"], 3)
        self.assertEqual(audit["mutating_calls"], 0)
        self.assertIn("vInfo.csv", audit["files_observed"])
        self.assertNotIn("sample-rvtools", str(audit))
        self.assertNotIn("password", str(audit).lower())

        app = inventory["workloads"][0]
        self.assertEqual(app["id"], "rvtools-app-01")
        self.assertEqual(app["name"], "app-01")
        self.assertEqual(app["owner"], "apps")
        self.assertEqual(app["cpu"], 4)
        self.assertEqual(app["memory_gib"], 8)
        self.assertEqual(app["disk_gib"], 50)
        self.assertEqual(app["storage"]["disk_count"], 1)
        self.assertTrue(app["networking"]["uses_vds"])
        self.assertEqual(app["snapshots"]["count"], 1)
        self.assertGreaterEqual(app["snapshots"]["oldest_days"], 7)
        self.assertEqual(app["snapshots"]["oldest_created_at"], "2026-07-01T20:00:00+00:00")
        self.assertTrue(app["backup"]["protected"])
        self.assertEqual(app["backup"]["last_success_hours"], 4)
        self.assertTrue(app["tools"]["virtio_ready"])
        self.assertEqual(app["vendor_support"], ["ahv", "nc2"])

        database = inventory["workloads"][1]
        self.assertEqual(database["disk_gib"], 200)
        self.assertEqual(database["storage"]["disk_count"], 2)
        self.assertTrue(database["networking"]["uses_nsx"])
        self.assertEqual(database["vendor_support"], ["nc2"])
        self.assertEqual(database["tools"]["status"], "toolsOld")
        self.assertEqual(database["backup"]["last_success_hours"], 36)

        legacy = inventory["workloads"][2]
        self.assertFalse(legacy["tools"]["vmware_tools"])
        self.assertEqual(legacy["snapshots"]["count"], 2)
        self.assertGreater(app["snapshots"]["oldest_days"], 0)
        self.assertGreater(legacy["snapshots"]["oldest_days"], app["snapshots"]["oldest_days"])

    def test_cli_import_rvtools_writes_normalized_inventory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "rvtools-inventory.json"
            with patch("sys.stdout"):
                result = main(
                    [
                        "import-rvtools",
                        "--dir",
                        "examples/rvtools",
                        "--source-name",
                        "unit-test-export",
                        "--out",
                        str(output),
                    ]
                )

            self.assertEqual(result, 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["source"]["endpoint"], "unit-test-export")
            self.assertEqual(len(payload["workloads"]), 3)

    def test_import_preserves_rvtools_tools_version_status(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            rvtools_dir = Path(temp_dir)
            (rvtools_dir / "vInfo.csv").write_text(
                "\n".join(
                    [
                        "VM,VM UUID,Powerstate,CPUs,Memory,Provisioned MiB,OS according to the VMware Tools,Tools,Tools Version Status,DNS Name,Primary IP Address,Annotation",
                        'app-01,vm-tools-1,poweredOn,2,4096,20480,Microsoft Windows Server 2019,toolsOk,guestToolsNeedUpgrade,app-01.example.test,10.10.120.15,"owner:apps;tier:standard;backup:protected;backup_last_success_hours:1;vendor_support:ahv;virtio_ready:true;depends_on:erp-db-01|directory-01"',
                    ]
                ),
                encoding="utf-8",
            )

            inventory = import_rvtools_directory(rvtools_dir)

            workload = inventory["workloads"][0]
            self.assertTrue(workload["tools"]["vmware_tools"])
            self.assertEqual(workload["tools"]["status"], "toolsOk; guestToolsNeedUpgrade")
            self.assertEqual(workload["guest_identity"]["dns_name"], "app-01.example.test")
            self.assertEqual(workload["guest_identity"]["valid_ip_addresses"], ["10.10.120.15"])
            self.assertEqual([item["name"] for item in workload["dependencies"]], ["erp-db-01", "directory-01"])


if __name__ == "__main__":
    unittest.main()
