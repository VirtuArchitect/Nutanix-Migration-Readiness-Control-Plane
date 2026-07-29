import io
import json
import unittest
from contextlib import redirect_stdout

from nmrcp.cli import main
from nmrcp.providers import provider_catalog, resolve_provider_pair, target_to_assessment_id
from nmrcp.scoring import assess_inventory


class ProviderTests(unittest.TestCase):
    def test_current_vmware_to_nutanix_pairs_are_registered(self):
        catalog = provider_catalog()
        pair_ids = {pair["id"] for pair in catalog["pairs"]}

        self.assertIn("vmware_vcenter->nutanix_ahv", pair_ids)
        self.assertIn("vmware_vcenter->nutanix_nc2", pair_ids)
        self.assertIn("rvtools_import->nutanix_ahv", pair_ids)
        self.assertIn("rvtools_import->nutanix_nc2", pair_ids)

    def test_resolve_provider_pair_accepts_legacy_target_aliases(self):
        pair = resolve_provider_pair("vmware_vcenter", "ahv")

        self.assertEqual(pair.id, "vmware_vcenter->nutanix_ahv")
        self.assertEqual(target_to_assessment_id("nutanix_nc2"), "nc2")

    def test_invalid_provider_pair_fails_closed(self):
        with self.assertRaises(ValueError):
            resolve_provider_pair("vmware_vcenter", "hyper_v")

    def test_assessment_uses_provider_pair_and_preserves_target_output(self):
        inventory = {
            "workloads": [
                {
                    "id": "vm-1",
                    "name": "web",
                    "guest_os": "Ubuntu Linux 22.04",
                    "tools": {"vmware_tools": True, "virtio_ready": True},
                    "backup": {"protected": True},
                    "networking": {"uses_vds": False, "uses_nsx": False},
                    "vendor_support": ["ahv"],
                }
            ]
        }

        assessment = assess_inventory(inventory, source="vmware_vcenter", target="nutanix_ahv")[0]

        self.assertEqual(assessment.target, "ahv")
        self.assertEqual(assessment.readiness, "ready")

    def test_cli_providers_outputs_catalog(self):
        stream = io.StringIO()

        with redirect_stdout(stream):
            code = main(["providers"])

        payload = json.loads(stream.getvalue())
        self.assertEqual(code, 0)
        self.assertIn("sources", payload)
        self.assertIn("targets", payload)
        self.assertIn("pairs", payload)


if __name__ == "__main__":
    unittest.main()
