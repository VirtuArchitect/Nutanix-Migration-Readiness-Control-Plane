import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.dependencies import merge_dependencies, read_dependency_csv
from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.migration_execution_queue import read_rows, validate_migration_execution_queue
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class MigrationExecutionQueueTests(unittest.TestCase):
    def test_execution_queue_rolls_up_operator_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_migration_execution_queue(out_dir / "migration-execution-queue.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "migration-execution-queue.csv", [])
            by_id = {row["workload_id"]: row for row in rows}

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.rows, 3)
            self.assertEqual(by_id["vm-1001"]["execution_order"], "1")
            self.assertEqual(by_id["vm-1001"]["compatibility_status"], "ready")
            self.assertEqual(by_id["vm-1001"]["execution_status"], "ready")
            self.assertEqual(by_id["vm-2020"]["execution_status"], "hold")
            self.assertIn("stage_hold", by_id["vm-2020"]["blocking_findings"])
            self.assertEqual(by_id["vm-3030"]["compatibility_status"], "research")
            self.assertEqual(by_id["vm-3030"]["connectivity_status"], "blocked")
            self.assertIn("compatibility_research", by_id["vm-3030"]["blocking_findings"])
            self.assertIn("rollback-plan.csv#vm-3030", by_id["vm-3030"]["evidence_refs"])

    def test_execution_queue_validator_rejects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "migration-execution-queue.csv"
            rows = read_rows(path, [])
            rows[0]["execution_status"] = "hold"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_migration_execution_queue(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("execution_status expected 'ready'" in error for error in result.errors))

    def test_execution_queue_rejects_stale_embedded_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["migration_execution_queue_context"]["workloads"][0]["owner"] = "Wrong Owner"
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_migration_execution_queue(out_dir / "migration-execution-queue.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("migration_execution_queue_context" in error and "owner expected" in error for error in result.errors))

    def test_execution_queue_rejects_unknown_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][0]["workload_ids"].append("vm-invented")
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_migration_execution_queue(out_dir / "migration-execution-queue.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("references unknown workload_id 'vm-invented'" in error for error in result.errors))

    def test_execution_queue_rejects_duplicate_wave_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["waves"][1]["workload_ids"].append(assessment["waves"][0]["workload_ids"][0])
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_migration_execution_queue(out_dir / "migration-execution-queue.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("appears in multiple waves" in error for error in result.errors))

    def test_cli_validates_execution_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-migration-execution-queue",
                        "--queue",
                        str(out_dir / "migration-execution-queue.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(code, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
    inventory = merge_dependencies(inventory, read_dependency_csv(Path("examples/sample_dependencies.csv")))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
