import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.source_networks import (
    validate_source_network_validation_csv,
    validate_source_networks,
    write_source_network_validation_csv,
)
from nmrcp.waves import plan_waves


class SourceNetworkValidationTests(unittest.TestCase):
    def test_validates_included_source_networks_against_vcenter_network_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_assessment(tmp_path)
            networks = write_networks(tmp_path, vlan="120")

            result = validate_source_networks(out_dir / "nutanix-move-plan.csv", networks)

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.checked_count, 1)
            self.assertEqual(result.matched_count, 1)
            self.assertEqual(result.rows[0]["source_network"], "120")

    def test_missing_source_network_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_assessment(tmp_path)
            networks = write_networks(tmp_path, vlan="999")

            result = validate_source_networks(out_dir / "nutanix-move-plan.csv", networks)

            self.assertFalse(result.ok)
            self.assertTrue(any("source network '120' was not found" in error for error in result.errors))

    def test_writes_and_validates_source_network_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_assessment(tmp_path)
            networks = write_networks(tmp_path, vlan="120")
            result = validate_source_networks(out_dir / "nutanix-move-plan.csv", networks)
            output = tmp_path / "source-network-validation.csv"

            write_source_network_validation_csv(result, output)
            csv_result = validate_source_network_validation_csv(output)

            self.assertTrue(csv_result.ok, csv_result.errors)
            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["schema_version"], "nmrcp_source_network_validation_v1")
            self.assertEqual(rows[0]["status"], "pass")

    def test_cli_validate_source_networks(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_assessment(tmp_path)
            networks = write_networks(tmp_path, vlan="120")
            output = tmp_path / "source-network-validation.csv"

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-source-networks",
                        "--plan",
                        str(out_dir / "nutanix-move-plan.csv"),
                        "--networks",
                        str(networks),
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


def write_networks(tmp_path: Path, vlan: str) -> Path:
    path = tmp_path / "vcenter-networks.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_vcenter_network_inventory_v1",
                "source": {
                    "system": "vcenter-rest",
                    "mode": "read-only",
                    "credential_storage": "not_persisted",
                    "api_paths": ["/api/session", "/api/vcenter/network"],
                    "mutating_calls": 0,
                },
                "networks": [
                    {
                        "network": "network-1",
                        "name": "Prod Distributed Portgroup",
                        "type": "DISTRIBUTED_PORTGROUP",
                        "vlan": vlan,
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
