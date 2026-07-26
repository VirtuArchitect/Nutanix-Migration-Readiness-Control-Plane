import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.assessment_intake import write_assessment_intake_template
from nmrcp.collection_workflow import collect_sources
from nmrcp.connectors import EndpointConfig


class CollectionWorkflowTests(unittest.TestCase):
    def test_collect_sources_writes_read_only_artifacts_and_redacted_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "sources"
            with patch("nmrcp.collection_workflow.VCenterClient", FakeVCenterClient), patch(
                "nmrcp.collection_workflow.PrismCentralClient", FakePrismClient
            ):
                result = collect_sources(
                    EndpointConfig("https://vcenter.private.example", "vc-user", "vc-secret"),
                    EndpointConfig("https://prism.private.example:9440", "pc-user", "pc-secret"),
                    out_dir,
                    vcenter_details_limit=1,
                    prism_page_size=1,
                    prism_max_pages=2,
                    prism_capacity_page_size=1,
                )

            self.assertEqual(result["schema_version"], "nmrcp_collection_summary_v1")
            self.assertEqual(result["status"], "pass")
            self.assertTrue((out_dir / "vcenter-inventory.json").exists())
            self.assertTrue((out_dir / "vcenter-networks.json").exists())
            self.assertTrue((out_dir / "prism-inventory.json").exists())
            self.assertTrue((out_dir / "prism-capacity.json").exists())
            self.assertTrue((out_dir / "collection-summary.json").exists())
            self.assertTrue((out_dir / "collection-proof-manifest.json").exists())
            self.assertTrue((out_dir / "collection-proof-report.md").exists())

            summary = json.loads((out_dir / "collection-summary.json").read_text(encoding="utf-8"))
            manifest = json.loads((out_dir / "collection-proof-manifest.json").read_text(encoding="utf-8"))
            networks = json.loads((out_dir / "vcenter-networks.json").read_text(encoding="utf-8"))
            report_text = (out_dir / "collection-proof-report.md").read_text(encoding="utf-8")
            serialized_summary = json.dumps(summary)
            serialized_manifest = json.dumps(manifest)
            self.assertNotIn("vcenter.private.example", serialized_summary)
            self.assertNotIn("prism.private.example", serialized_summary)
            self.assertNotIn("vc-secret", serialized_summary)
            self.assertNotIn("pc-secret", serialized_summary)
            self.assertNotIn("vcenter.private.example", serialized_manifest)
            self.assertNotIn("prism.private.example", serialized_manifest)
            self.assertNotIn("vc-secret", serialized_manifest)
            self.assertNotIn("pc-secret", serialized_manifest)
            self.assertTrue(summary["privacy"]["summary_redacted"])
            self.assertEqual(summary["artifacts"]["collection_proof_manifest"], "collection-proof-manifest.json")
            self.assertEqual(manifest["schema_version"], "nmrcp_collection_proof_manifest_v1")
            self.assertFalse(manifest["security"]["mutation_allowed"])
            self.assertIn("/api/vcenter/network", manifest["security"]["read_only_api_allowlist"])
            self.assertIn("collection-proof-report.md", report_text)
            self.assertIn("mutating_calls=0", report_text)
            self.assertNotIn("vcenter.private.example", report_text)
            self.assertEqual(
                sorted(artifact["name"] for artifact in manifest["artifacts"]),
                [
                    "collection-proof-report.md",
                    "collection-summary.json",
                    "prism-capacity.json",
                    "prism-inventory.json",
                    "vcenter-inventory.json",
                    "vcenter-networks.json",
                ],
            )
            self.assertEqual(summary["privacy"]["tls_verification"]["vcenter"], "enabled")
            self.assertEqual(summary["privacy"]["tls_verification"]["prism-central"], "enabled")
            self.assertTrue(all(check["mutating_calls"] == 0 for check in summary["checks"]))
            self.assertTrue(all(check["tls_verification"] == "enabled" for check in summary["checks"]))
            self.assertEqual(summary["artifacts"]["vcenter_networks"], "vcenter-networks.json")
            self.assertEqual(summary["checks"][0]["workloads"], 1)
            self.assertEqual(summary["checks"][1]["networks"], 1)
            self.assertEqual(summary["checks"][2]["workloads"], 1)
            self.assertEqual(summary["checks"][3]["targets"], 1)
            self.assertEqual(networks["schema_version"], "nmrcp_vcenter_network_inventory_v1")
            self.assertEqual(networks["networks"][0]["name"], "Prod Distributed Portgroup")

    def test_collect_sources_binds_validated_assessment_intake_without_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out_dir = root / "sources"
            intake = write_completed_intake(root / "assessment-intake.csv")
            with patch("nmrcp.collection_workflow.VCenterClient", FakeVCenterClient), patch(
                "nmrcp.collection_workflow.PrismCentralClient", FakePrismClient
            ):
                result = collect_sources(
                    EndpointConfig("https://vcenter.private.example", "vc-user", "vc-secret"),
                    EndpointConfig("https://prism.private.example:9440", "pc-user", "pc-secret"),
                    out_dir,
                    assessment_intake_path=intake,
                )

            summary = json.loads((out_dir / "collection-summary.json").read_text(encoding="utf-8"))
            manifest = json.loads((out_dir / "collection-proof-manifest.json").read_text(encoding="utf-8"))
            intake_proof = summary["governance"]["assessment_intake"]

            self.assertEqual(result["governance"]["assessment_intake"]["status"], "pass")
            self.assertEqual(intake_proof["schema_version"], "nmrcp_assessment_intake_validation_v1")
            self.assertEqual(len(intake_proof["source_sha256"]), 64)
            self.assertFalse(intake_proof["values_serialized"])
            self.assertEqual(manifest["security"]["assessment_intake"]["source_sha256"], intake_proof["source_sha256"])
            self.assertNotIn("sample customer_or_program", json.dumps(summary))
            self.assertNotIn("sample assessment_owner", json.dumps(manifest))

    def test_collect_sources_rejects_invalid_assessment_intake_before_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            intake = write_assessment_intake_template(root / "assessment-intake.csv")
            with self.assertRaises(ValueError) as failure:
                collect_sources(
                    EndpointConfig("https://vcenter.private.example", "vc-user", "vc-secret"),
                    EndpointConfig("https://prism.private.example:9440", "pc-user", "pc-secret"),
                    root / "sources",
                    assessment_intake_path=intake,
                )

            self.assertIn("Assessment intake validation failed", str(failure.exception))


def write_completed_intake(path: Path) -> Path:
    write_assessment_intake_template(path)
    rows = []
    import csv

    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        if row["field"] in {"secrets_stay_local_ack", "redacted_evidence_ack", "read_only_collection_ack", "no_production_mutation_ack"}:
            row["value"] = "true"
        elif row["field"] == "migration_target":
            row["value"] = "ahv"
        elif row["field"] == "rvtools_export_available":
            row["value"] = "true"
        elif row["field"] == "approved_move_lab_available":
            row["value"] = "false"
        elif row["required"] == "true":
            row["value"] = f"sample {row['field']}"
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return path


class FakeVCenterClient:
    def __init__(self, config):
        self.config = config

    def list_vms(self):
        return [
            {
                "vm": "vm-1",
                "name": "web-01",
                "cpu_count": 2,
                "memory_size_MiB": 4096,
                "tags": ["owner:platform", "backup:protected", "vendor_support:ahv,nc2", "virtio_ready:true"],
            }
        ]

    def get_vm_details(self, vm_id):
        return {
            "guest_OS": "UBUNTU_64",
            "disks": [{"capacity_MiB": 51200}],
            "nics": [{"network": "dvpg-prod", "vlan": 120}],
            "tools": {"run_state": "RUNNING"},
        }

    def list_networks(self):
        return [{"network": "network-1", "name": "Prod Distributed Portgroup", "type": "DISTRIBUTED_PORTGROUP"}]


class FakePrismClient:
    def __init__(self, config):
        self.config = config

    def list_vms(self, page_size=500, max_pages=20):
        return [
            {
                "metadata": {"uuid": "uuid-1", "categories": {"Owner": "platform", "Backup": "protected"}},
                "spec": {
                    "name": "ahv-01",
                    "resources": {
                        "num_sockets": 1,
                        "num_vcpus_per_socket": 2,
                        "memory_size_mib": 4096,
                        "disk_list": [{"disk_size_bytes": 53687091200}],
                        "nic_list": [{"subnet_reference": {"name": "vlan-120"}}],
                    },
                },
            }
        ]

    def list_clusters(self, page_size=100):
        return [
            {
                "metadata": {"uuid": "cluster-1"},
                "status": {
                    "name": "ahv-cluster-1",
                    "resources": {
                        "num_cpu_cores": 24,
                        "memory_capacity_mib": 196608,
                        "storage_capacity_bytes": 2199023255552,
                    },
                },
            }
        ]


if __name__ == "__main__":
    unittest.main()
