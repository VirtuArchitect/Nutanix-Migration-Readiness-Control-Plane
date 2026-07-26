import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.metadata import import_cmdb_metadata_csv, merge_metadata, read_metadata_csv
from nmrcp.scoring import assess_inventory


class MetadataEnrichmentTests(unittest.TestCase):
    def test_metadata_csv_merges_by_id_and_tracks_unmatched(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        metadata = read_metadata_csv(Path("examples/sample_metadata.csv"))

        enriched = merge_metadata(inventory, metadata)

        by_id = {workload["id"]: workload for workload in enriched["workloads"]}
        self.assertEqual(by_id["vm-1001"]["owner"], "Platform Team")
        self.assertIn("cmdb-owned", by_id["vm-1001"]["tags"])
        self.assertTrue(by_id["vm-2020"]["backup"]["protected"])
        self.assertEqual(by_id["vm-2020"]["backup"]["last_success_hours"], 4)
        self.assertTrue(by_id["vm-2020"]["tools"]["virtio_ready"])
        self.assertEqual(by_id["vm-2020"]["vendor_support"], ["ahv"])
        self.assertTrue(by_id["vm-2020"]["governance"]["application_owner_approved"])
        self.assertEqual(by_id["vm-2020"]["governance"]["rollback_owner"], "Business Apps")
        self.assertFalse(by_id["vm-3030"]["governance"]["application_owner_approved"])
        self.assertEqual(len(enriched["unmatched_metadata"]), 1)
        self.assertEqual(enriched["source"]["metadata_records"], 4)

    def test_metadata_can_reduce_readiness_risk_for_remediated_fields(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        enriched = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))

        assessments = assess_inventory(enriched)
        by_id = {assessment.workload_id: assessment for assessment in assessments}
        erp_codes = [finding.code for finding in by_id["vm-2020"].findings]

        self.assertNotIn("virtio_not_ready", erp_codes)
        self.assertNotIn("vendor_support_unconfirmed", erp_codes)
        self.assertEqual(by_id["vm-2020"].readiness, "prepare")

    def test_metadata_csv_requires_match_column(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.csv"
            path.write_text("owner,tier\napps,critical\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                read_metadata_csv(path)

    def test_cmdb_export_imports_to_metadata_records(self):
        records = import_cmdb_metadata_csv(Path("examples/sample_cmdb_export.csv"))

        by_id = {record["source_id"]: record for record in records}
        self.assertEqual(len(records), 4)
        self.assertEqual(by_id["vm-1001"]["source_name"], "pilot-web-01")
        self.assertEqual(by_id["vm-1001"]["owner"], "Platform Team")
        self.assertEqual(by_id["vm-1001"]["tier"], "noncritical")
        self.assertIn("Pilot Portal", by_id["vm-1001"]["tags"])
        self.assertEqual(by_id["vm-1001"]["backup_protected"], "true")
        self.assertEqual(by_id["vm-2020"]["vendor_support"], "ahv")
        self.assertEqual(by_id["vm-2020"]["virtio_ready"], "true")
        self.assertEqual(by_id["vm-3030"]["application_owner_approved"], "false")

    def test_cmdb_export_rejects_endpoint_or_secret_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cmdb.csv"
            path.write_text(
                "VM UUID,VM Name,Service Owner,Comments\n"
                "vm-1,app-01,Apps,https://vcenter.example.invalid\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                import_cmdb_metadata_csv(path)

    def test_cli_enrich_metadata_writes_inventory(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "metadata-inventory.json"
            with patch("sys.stdout"):
                result = main(
                    [
                        "enrich-metadata",
                        "--inventory",
                        "examples/sample_inventory.json",
                        "--metadata",
                        "examples/sample_metadata.csv",
                        "--out",
                        str(out_path),
                    ]
                )

            payload = json.loads(out_path.read_text(encoding="utf-8"))
            self.assertEqual(result, 0)
            self.assertEqual(payload["source"]["metadata_unmatched_records"], 1)

    def test_cli_import_cmdb_metadata_writes_normalized_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_path = Path(tmp) / "cmdb-metadata.csv"
            with patch("sys.stdout"):
                result = main(
                    [
                        "import-cmdb-metadata",
                        "--export",
                        "examples/sample_cmdb_export.csv",
                        "--out",
                        str(out_path),
                    ]
                )

            imported = read_metadata_csv(out_path)
            self.assertEqual(result, 0)
            self.assertEqual(len(imported), 4)
            self.assertEqual(imported[0]["source_id"], "vm-1001")
            self.assertEqual(imported[0]["owner"], "Platform Team")

    def test_cli_assess_can_apply_metadata_before_scoring(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            with patch("sys.stdout"):
                result = main(
                    [
                        "assess",
                        "--inventory",
                        "examples/sample_inventory.json",
                        "--metadata",
                        "examples/sample_metadata.csv",
                        "--out",
                        str(out_dir),
                    ]
                )

            assessment = json.loads((out_dir / "assessment.json").read_text(encoding="utf-8"))
            erp = next(item for item in assessment["assessments"] if item["workload_id"] == "vm-2020")
            codes = [finding["code"] for finding in erp["findings"]]
            self.assertEqual(result, 0)
            self.assertNotIn("virtio_not_ready", codes)
            self.assertNotIn("vendor_support_unconfirmed", codes)


if __name__ == "__main__":
    unittest.main()
