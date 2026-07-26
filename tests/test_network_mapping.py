import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.network_mapping import validate_network_mappings, write_network_mapping_csv
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class NetworkMappingTests(unittest.TestCase):
    def test_validates_included_workload_networks(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_network_mappings(
                out_dir / "nutanix-move-plan.csv",
                Path("examples/sample_move_payload_config.json"),
            )

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.checked_count, 1)
            self.assertEqual(result.mapped_count, 1)
            self.assertEqual(result.rows[0]["source_network"], "120")
            self.assertEqual(result.rows[0]["target_network"], "vlan-120-ahv")

    def test_missing_mapping_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_assessment(tmp_path)
            config = json.loads(Path("examples/sample_move_payload_config.json").read_text(encoding="utf-8"))
            config["network_mappings"] = [{"source_network": "999", "target_network": "unused"}]
            config_path = tmp_path / "config.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            result = validate_network_mappings(out_dir / "nutanix-move-plan.csv", config_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("source network '120' is not mapped" in error for error in result.errors))

    def test_writes_network_mapping_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_assessment(tmp_path)
            result = validate_network_mappings(
                out_dir / "nutanix-move-plan.csv",
                Path("examples/sample_move_payload_config.json"),
            )
            output = tmp_path / "target-network-mapping.csv"

            write_network_mapping_csv(result, output)

            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["schema_version"], "nmrcp_target_network_mapping_v1")
            self.assertEqual(rows[0]["status"], "pass")

    def test_cli_validate_network_mappings(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_assessment(tmp_path)
            output = tmp_path / "target-network-mapping.csv"

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-network-mappings",
                        "--plan",
                        str(out_dir / "nutanix-move-plan.csv"),
                        "--config",
                        "examples/sample_move_payload_config.json",
                        "--out",
                        str(output),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertTrue(output.exists())


def build_assessment(tmp_path: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    out_dir = tmp_path / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
