import json
import tempfile
import unittest
from pathlib import Path

from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.move_payload import build_move_payload, load_move_config
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class MovePayloadTests(unittest.TestCase):
    def test_build_move_payload_includes_only_staged_workloads(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            write_assessment(inventory, assessments, waves, out_dir)

            payload = build_move_payload(
                out_dir / "nutanix-move-plan.csv",
                Path("examples/sample_move_payload_config.json"),
            )

            self.assertTrue(payload["dry_run_only"])
            self.assertFalse(payload["mutation_allowed"])
            self.assertEqual(payload["contract"], "nmrcp_move_api_payload_dry_run_v1")
            self.assertEqual(len(payload["workloads"]), 1)
            self.assertEqual(payload["workloads"][0]["source_vm_id"], "vm-1001")
            self.assertEqual(payload["workloads"][0]["application_owner_approval"], "confirmed")
            self.assertEqual(payload["workloads"][0]["rollback_owner"], "Platform Team")

    def test_build_move_payload_refuses_invalid_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "invalid.csv"
            path.write_text("source_vm_id\nvm-1\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                build_move_payload(path, Path("examples/sample_move_payload_config.json"))

    def test_config_requires_network_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad-config.json"
            config = json.loads(Path("examples/sample_move_payload_config.json").read_text(encoding="utf-8"))
            config["network_mappings"] = []
            path.write_text(json.dumps(config), encoding="utf-8")

            with self.assertRaises(ValueError):
                load_move_config(path)

    def test_build_move_payload_refuses_unmapped_included_network(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            config_path = Path(tmp) / "bad-config.json"
            write_assessment(inventory, assessments, waves, out_dir)
            config = json.loads(Path("examples/sample_move_payload_config.json").read_text(encoding="utf-8"))
            config["network_mappings"] = [{"source_network": "999", "target_network": "unused"}]
            config_path.write_text(json.dumps(config), encoding="utf-8")

            with self.assertRaises(ValueError):
                build_move_payload(out_dir / "nutanix-move-plan.csv", config_path)


if __name__ == "__main__":
    unittest.main()
