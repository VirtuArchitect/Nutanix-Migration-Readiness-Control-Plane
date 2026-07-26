import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.capacity import normalize_prism_capacity, validate_capacity_fit, write_capacity_fit_csv
from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class CapacityFitTests(unittest.TestCase):
    def test_normalize_prism_capacity_drafts_capacity_json(self):
        capacity = normalize_prism_capacity(
            [
                {
                    "metadata": {"uuid": "cluster-1"},
                    "status": {
                        "name": "prod-ahv",
                        "resources": {
                            "num_cpu_cores": 64,
                            "memory_capacity_mib": 524288,
                            "storage_capacity_bytes": 10995116277760,
                        },
                    },
                }
            ],
            target="ahv",
        )

        target = capacity["targets"][0]
        self.assertEqual(capacity["source"]["api_paths"], ["/api/nutanix/v3/clusters/list"])
        self.assertEqual(capacity["source"]["mutating_calls"], 0)
        self.assertEqual(target["cluster_name"], "prod-ahv")
        self.assertEqual(target["usable_cpu_cores"], 64)
        self.assertEqual(target["usable_memory_gib"], 512)
        self.assertEqual(target["usable_storage_gib"], 10240)

    def test_generated_move_plan_fits_sample_capacity(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_capacity_fit(
                Path("examples/sample_inventory.json"),
                out_dir / "nutanix-move-plan.csv",
                Path("examples/sample_target_capacity.json"),
            )

            self.assertTrue(result.ok, result.errors)
            ahv = next(row for row in result.rows if row["target"] == "ahv")
            self.assertEqual(ahv["included_workloads"], 1)
            self.assertEqual(ahv["required_cpu"], 4)
            self.assertEqual(ahv["required_memory_gib"], 16)
            self.assertEqual(ahv["required_storage_gib"], 120)
            self.assertEqual(ahv["status"], "pass")

    def test_capacity_fit_fails_when_storage_exceeds_headroom(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_assessment(tmp_path)
            capacity = json.loads(Path("examples/sample_target_capacity.json").read_text(encoding="utf-8"))
            capacity["targets"][0]["usable_storage_gib"] = 100
            capacity_path = tmp_path / "capacity.json"
            capacity_path.write_text(json.dumps(capacity), encoding="utf-8")

            result = validate_capacity_fit(
                Path("examples/sample_inventory.json"),
                out_dir / "nutanix-move-plan.csv",
                capacity_path,
            )

            self.assertFalse(result.ok)
            self.assertTrue(any("storage" in error for error in result.errors))

    def test_writes_capacity_fit_csv(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_assessment(tmp_path)
            result = validate_capacity_fit(
                Path("examples/sample_inventory.json"),
                out_dir / "nutanix-move-plan.csv",
                Path("examples/sample_target_capacity.json"),
            )
            output = tmp_path / "target-capacity-fit.csv"

            write_capacity_fit_csv(result, output)

            with output.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(rows[0]["schema_version"], "nmrcp_target_capacity_fit_v1")
            self.assertIn("available_storage_gib", rows[0])

    def test_cli_validate_capacity_writes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            out_dir = build_assessment(tmp_path)
            output = tmp_path / "target-capacity-fit.csv"

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-capacity",
                        "--inventory",
                        "examples/sample_inventory.json",
                        "--plan",
                        str(out_dir / "nutanix-move-plan.csv"),
                        "--capacity",
                        "examples/sample_target_capacity.json",
                        "--out",
                        str(output),
                    ]
                )

            self.assertEqual(code, 0)
            self.assertTrue(output.exists())

    def test_cli_collect_prism_capacity_writes_capacity_json(self):
        class FakePrism:
            def __init__(self, config):
                self.config = config

            def list_clusters(self, page_size=100):
                return [
                    {
                        "metadata": {"uuid": "cluster-1"},
                        "status": {
                            "name": "lab-ahv",
                            "resources": {
                                "num_cpu_cores": 16,
                                "memory_capacity_mib": 131072,
                                "storage_capacity_bytes": 1099511627776,
                            },
                        },
                    }
                ]

        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "capacity.json"
            with patch("nmrcp.cli.PrismCentralClient", FakePrism), patch.dict(
                "os.environ",
                {"NMRCP_PRISM_PASSWORD": "synthetic-password"},
            ), patch("sys.stdout"):
                code = main(
                    [
                        "collect-prism-capacity",
                        "--endpoint",
                        "https://pc.example.test:9440",
                        "--username",
                        "admin",
                        "--out",
                        str(output),
                    ]
                )

            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertEqual(payload["source"]["mutating_calls"], 0)
            self.assertEqual(payload["targets"][0]["usable_memory_gib"], 128)


def build_assessment(tmp_path: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    out_dir = tmp_path / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
