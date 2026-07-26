import unittest

from nmrcp.inventory import normalize_prism_inventory, normalize_vcenter_inventory


class InventoryNormalizationTests(unittest.TestCase):
    def test_vcenter_normalization_maps_vm_summary_and_details(self):
        inventory = normalize_vcenter_inventory(
            "https://vcsa.example.test",
            [
                {
                    "vm": "vm-42",
                    "name": "app-01",
                    "cpu_count": 4,
                    "memory_size_MiB": 8192,
                    "power_state": "POWERED_ON",
                    "tags": [
                        "owner:apps",
                        "tier:critical",
                        "backup:protected",
                        "backup_last_success_hours:3",
                        "vendor_support:ahv,nc2",
                        "dependencies:db-01|redis-01",
                    ],
                    "tools_status": "toolsOk",
                }
            ],
            {
                "vm-42": {
                    "guest_OS": "WINDOWS_SERVER_2019",
                    "identity": {
                        "host_name": "app-01",
                        "dns_name": "app-01.example.test",
                        "ip_addresses": ["10.10.120.15", "fe80::1"],
                    },
                    "disks": [
                        {
                            "capacity_MiB": 102400,
                            "datastore": "ds-prod-01",
                            "datastore_free_percent": 42,
                            "thin_provisioned": True,
                        }
                    ],
                    "nics": [{"network": "Prod Distributed Portgroup", "vlan": 120}],
                    "snapshot_count": 1,
                    "snapshots": [{"name": "before-maintenance", "create_time": "2026-07-01T20:00:00Z"}],
                    "tools": {"run_state": "RUNNING", "version_status": "guestToolsNeedUpgrade"},
                }
            },
            details_limit=10,
            network_count=1,
        )

        workload = inventory["workloads"][0]
        self.assertEqual(workload["id"], "vm-42")
        self.assertEqual(workload["owner"], "apps")
        self.assertTrue(workload["networking"]["uses_vds"])
        self.assertEqual(workload["disk_gib"], 100)
        self.assertEqual(workload["storage"]["disk_count"], 1)
        self.assertTrue(workload["storage"]["thin_provisioned"])
        self.assertEqual(workload["storage"]["datastores"], ["ds-prod-01"])
        self.assertEqual(workload["storage"]["min_datastore_free_percent"], 42.0)
        self.assertEqual(workload["snapshots"]["count"], 1)
        self.assertGreaterEqual(workload["snapshots"]["oldest_days"], 7)
        self.assertEqual(workload["snapshots"]["oldest_created_at"], "2026-07-01T20:00:00+00:00")
        self.assertTrue(workload["tools"]["vmware_tools"])
        self.assertIn("toolsOk", workload["tools"]["status"])
        self.assertIn("guestToolsNeedUpgrade", workload["tools"]["status"])
        self.assertEqual(workload["backup"]["last_success_hours"], 3)
        self.assertEqual(workload["guest_identity"]["hostname"], "app-01")
        self.assertEqual(workload["guest_identity"]["dns_name"], "app-01.example.test")
        self.assertEqual(workload["guest_identity"]["valid_ip_addresses"], ["10.10.120.15", "fe80::1"])
        self.assertTrue(workload["guest_identity"]["has_ipv4"])
        self.assertTrue(workload["guest_identity"]["has_ipv6"])
        self.assertEqual(
            workload["dependencies"],
            [
                {
                    "name": "db-01",
                    "id": "",
                    "type": "declared",
                    "owner": "",
                    "criticality": "",
                    "notes": "Declared in source metadata.",
                },
                {
                    "name": "redis-01",
                    "id": "",
                    "type": "declared",
                    "owner": "",
                    "criticality": "",
                    "notes": "Declared in source metadata.",
                },
            ],
        )
        audit = inventory["source"]["collection_audit"]
        self.assertEqual(audit["schema"], "nmrcp_collection_audit_v1")
        self.assertEqual(audit["mode"], "read-only")
        self.assertEqual(audit["summary_count"], 1)
        self.assertEqual(audit["details_limit"], 10)
        self.assertEqual(audit["details_count"], 1)
        self.assertEqual(audit["network_count"], 1)
        self.assertEqual(audit["mutating_calls"], 0)
        self.assertIn("/api/vcenter/vm/{vm}", audit["api_paths"])
        self.assertIn("/api/vcenter/network", audit["api_paths"])
        self.assertNotIn("https://vcsa.example.test", str(audit))
        self.assertNotIn("password", str(audit).lower())

    def test_vcenter_normalization_marks_tools_not_running_as_missing(self):
        inventory = normalize_vcenter_inventory(
            "https://vcsa.example.test",
            [{"vm": "vm-99", "name": "legacy-01", "guest_OS": "WINDOWS_SERVER_2019"}],
            {"vm-99": {"guest_OS": "WINDOWS_SERVER_2019", "tools": {"run_state": "guestToolsNotRunning"}}},
        )

        workload = inventory["workloads"][0]

        self.assertFalse(workload["tools"]["vmware_tools"])
        self.assertIn("guestToolsNotRunning", workload["tools"]["status"])

    def test_prism_normalization_maps_vm_entities(self):
        inventory = normalize_prism_inventory(
            "https://pc.example.test:9440",
            [
                {
                    "metadata": {
                        "uuid": "uuid-1",
                        "categories": {
                            "Owner": "platform",
                            "Backup": "protected",
                            "BackupLastSuccessHours": "2",
                            "Dependencies": "directory-01, dns-01",
                        },
                    },
                    "spec": {
                        "name": "ahv-vm-01",
                        "resources": {
                            "num_sockets": 2,
                            "num_vcpus_per_socket": 2,
                            "memory_size_mib": 16384,
                            "disk_list": [
                                {
                                    "disk_size_bytes": 107374182400,
                                    "storage_container_reference": {"name": "default-container"},
                                }
                            ],
                            "nic_list": [{"subnet_reference": {"name": "vlan-120"}}],
                        },
                    },
                    "status": {
                        "resources": {
                            "guest_tools": {
                                "host_name": "ahv-vm-01",
                                "dns_name": "ahv-vm-01.example.test",
                                "ip_addresses": ["10.10.120.20"],
                            }
                        }
                    },
                }
            ],
            page_size=100,
            max_pages=2,
        )

        workload = inventory["workloads"][0]
        self.assertEqual(workload["id"], "uuid-1")
        self.assertEqual(workload["cpu"], 4)
        self.assertEqual(workload["memory_gib"], 16)
        self.assertEqual(workload["disk_gib"], 100)
        self.assertEqual(workload["storage"]["disk_count"], 1)
        self.assertEqual(workload["storage"]["storage_containers"], ["default-container"])
        self.assertFalse(workload["storage"]["raw_device_mapping"])
        self.assertTrue(workload["backup"]["protected"])
        self.assertEqual(workload["backup"]["last_success_hours"], 2)
        self.assertEqual(workload["guest_identity"]["dns_name"], "ahv-vm-01.example.test")
        self.assertEqual(workload["guest_identity"]["valid_ip_addresses"], ["10.10.120.20"])
        self.assertEqual([item["name"] for item in workload["dependencies"]], ["directory-01", "dns-01"])
        audit = inventory["source"]["collection_audit"]
        self.assertEqual(audit["schema"], "nmrcp_collection_audit_v1")
        self.assertEqual(audit["mode"], "read-only")
        self.assertEqual(audit["api_paths"], ["/api/nutanix/v3/vms/list"])
        self.assertEqual(audit["page_size"], 100)
        self.assertEqual(audit["max_pages"], 2)
        self.assertEqual(audit["entities_count"], 1)
        self.assertTrue(audit["post_paths_allowlisted"])
        self.assertEqual(audit["mutating_calls"], 0)
        self.assertNotIn("https://pc.example.test:9440", str(audit))
        self.assertNotIn("password", str(audit).lower())


if __name__ == "__main__":
    unittest.main()
