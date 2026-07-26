import unittest
import tempfile
from pathlib import Path

from nmrcp.scoring import ReadinessPolicy, assess_inventory, assess_workload, load_readiness_policy


class ScoringTests(unittest.TestCase):
    def test_ready_workload_has_low_score(self):
        assessment = assess_workload(
            {
                "id": "vm-1",
                "name": "web",
                "guest_os": "Ubuntu Linux 22.04",
                "tools": {"vmware_tools": True, "virtio_ready": True},
                "backup": {"protected": True},
                "networking": {"uses_vds": False, "uses_nsx": False},
                "vendor_support": ["ahv"],
            }
        )

        self.assertEqual(assessment.readiness, "ready")
        self.assertEqual(assessment.risk_score, 0)

    def test_nsx_dependency_blocks_workload(self):
        assessment = assess_workload(
            {
                "id": "vm-2",
                "name": "edge",
                "guest_os": "Windows Server 2019",
                "tools": {"vmware_tools": True, "virtio_ready": True},
                "backup": {"protected": True},
                "networking": {"uses_nsx": True},
                "vendor_support": ["ahv"],
            }
        )

        self.assertEqual(assessment.readiness, "blocked")
        self.assertIn("nsx_dependency", [finding.code for finding in assessment.findings])

    def test_snapshot_age_backup_age_and_tools_status_add_findings(self):
        assessment = assess_workload(
            {
                "id": "vm-3",
                "name": "erp",
                "guest_os": "Windows Server 2019",
                "snapshots": {"count": 1, "oldest_days": 14},
                "tools": {"vmware_tools": True, "virtio_ready": True, "status": "toolsOld"},
                "backup": {"protected": True, "last_success_hours": 48},
                "networking": {"uses_vds": False, "uses_nsx": False},
                "vendor_support": ["ahv"],
            }
        )

        codes = [finding.code for finding in assessment.findings]
        self.assertIn("snapshots_present", codes)
        self.assertIn("snapshot_age_exceeds_policy", codes)
        self.assertIn("vmware_tools_outdated", codes)
        self.assertIn("backup_recovery_point_stale", codes)
        self.assertEqual(assessment.readiness, "blocked")

    def test_missing_vmware_tools_is_called_out(self):
        assessment = assess_workload(
            {
                "id": "vm-4",
                "name": "legacy",
                "guest_os": "Windows Server 2019",
                "snapshots": {"count": 0},
                "tools": {"vmware_tools": False, "virtio_ready": False},
                "backup": {"protected": True, "last_success_hours": 1},
                "networking": {"uses_vds": False, "uses_nsx": False},
                "vendor_support": ["ahv"],
            }
        )

        self.assertIn("vmware_tools_missing", [finding.code for finding in assessment.findings])

    def test_powered_off_workload_requires_live_validation_review(self):
        assessment = assess_workload(
            {
                "id": "vm-power",
                "name": "powered-off-app",
                "guest_os": "Windows Server 2019",
                "power_state": "poweredOff",
                "snapshots": {"count": 0},
                "tools": {"vmware_tools": True, "virtio_ready": True},
                "backup": {"protected": True, "last_success_hours": 1},
                "networking": {"uses_vds": False, "uses_nsx": False},
                "vendor_support": ["ahv"],
            }
        )

        self.assertEqual(assessment.readiness, "research")
        self.assertIn("power_state_not_on", [finding.code for finding in assessment.findings])

    def test_powered_on_workload_does_not_add_power_state_finding(self):
        assessment = assess_workload(
            {
                "id": "vm-on",
                "name": "powered-on-app",
                "guest_os": "Windows Server 2019",
                "power_state": "POWERED_ON",
                "snapshots": {"count": 0},
                "tools": {"vmware_tools": True, "virtio_ready": True},
                "backup": {"protected": True, "last_success_hours": 1},
                "networking": {"uses_vds": False, "uses_nsx": False},
                "guest_identity": {
                    "dns_name": "powered-on-app.example.test",
                    "valid_ip_addresses": ["10.10.120.15"],
                    "invalid_ip_addresses": [],
                },
                "vendor_support": ["ahv"],
            }
        )

        self.assertNotIn("power_state_not_on", [finding.code for finding in assessment.findings])

    def test_powered_on_workload_requires_guest_identity_evidence(self):
        assessment = assess_workload(
            {
                "id": "vm-guest-id",
                "name": "guest-identity-gap",
                "guest_os": "Windows Server 2019",
                "power_state": "POWERED_ON",
                "snapshots": {"count": 0},
                "tools": {"vmware_tools": True, "virtio_ready": True},
                "backup": {"protected": True, "last_success_hours": 1},
                "networking": {"uses_vds": False, "uses_nsx": False},
                "guest_identity": {
                    "dns_name": "",
                    "valid_ip_addresses": [],
                    "invalid_ip_addresses": ["999.10.10.10"],
                },
                "vendor_support": ["ahv"],
            }
        )

        codes = [finding.code for finding in assessment.findings]
        self.assertIn("guest_ip_invalid", codes)
        self.assertIn("guest_ip_missing", codes)
        self.assertIn("guest_dns_missing", codes)
        self.assertEqual(assessment.readiness, "prepare")

    def test_storage_posture_adds_move_readiness_findings(self):
        assessment = assess_workload(
            {
                "id": "vm-storage",
                "name": "clustered-db",
                "guest_os": "Windows Server 2019",
                "snapshots": {"count": 0},
                "tools": {"vmware_tools": True, "virtio_ready": True},
                "backup": {"protected": True, "last_success_hours": 1},
                "networking": {"uses_vds": False, "uses_nsx": False},
                "storage": {
                    "raw_device_mapping": True,
                    "shared_disk": True,
                    "independent_disk": True,
                    "encrypted": True,
                    "min_datastore_free_percent": 8,
                },
                "vendor_support": ["ahv"],
            }
        )

        codes = [finding.code for finding in assessment.findings]
        self.assertIn("storage_rdm_mapping_required", codes)
        self.assertIn("shared_disk_cluster_review", codes)
        self.assertIn("independent_disk_review", codes)
        self.assertIn("encrypted_disk_review", codes)
        self.assertIn("datastore_free_space_low", codes)
        self.assertEqual(assessment.readiness, "blocked")

    def test_governance_metadata_adds_owner_and_rollback_findings(self):
        assessment = assess_workload(
            {
                "id": "vm-governance",
                "name": "change-sensitive-app",
                "guest_os": "Windows Server 2019",
                "snapshots": {"count": 0},
                "tools": {"vmware_tools": True, "virtio_ready": True},
                "backup": {"protected": True, "last_success_hours": 1},
                "networking": {"uses_vds": False, "uses_nsx": False},
                "vendor_support": ["ahv"],
                "governance": {
                    "application_owner_approved": False,
                    "rollback_owner": "",
                },
            }
        )

        codes = [finding.code for finding in assessment.findings]
        self.assertIn("application_owner_approval_missing", codes)
        self.assertIn("rollback_owner_missing", codes)
        self.assertEqual(assessment.readiness, "prepare")

    def test_policy_can_tune_snapshot_backup_and_risk_thresholds(self):
        policy = ReadinessPolicy(snapshot_max_age_days=30, backup_max_age_hours=72, prepare_risk_threshold=40, blocked_risk_threshold=80)
        assessment = assess_workload(
            {
                "id": "vm-5",
                "name": "erp",
                "guest_os": "Windows Server 2019",
                "snapshots": {"count": 1, "oldest_days": 14},
                "tools": {"vmware_tools": True, "virtio_ready": True},
                "backup": {"protected": True, "last_success_hours": 48},
                "networking": {"uses_vds": False, "uses_nsx": False},
                "vendor_support": ["ahv"],
            },
            policy=policy,
        )

        codes = [finding.code for finding in assessment.findings]
        self.assertNotIn("snapshot_age_exceeds_policy", codes)
        self.assertNotIn("backup_recovery_point_stale", codes)
        self.assertEqual(assessment.readiness, "research")

    def test_load_readiness_policy_validates_thresholds(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "policy.json"
            path.write_text('{"prepare_risk_threshold": 50, "blocked_risk_threshold": 25}', encoding="utf-8")

            with self.assertRaises(ValueError):
                load_readiness_policy(path)

    def test_inventory_requires_workload_list(self):
        with self.assertRaises(ValueError):
            assess_inventory({"source": {}})


if __name__ == "__main__":
    unittest.main()
