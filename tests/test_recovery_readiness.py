import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.recovery_readiness import RECOVERY_READINESS_SCHEMA_VERSION, validate_recovery_readiness
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class RecoveryReadinessTests(unittest.TestCase):
    def test_write_assessment_generates_recovery_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp), with_recovery_risk=True)

            result = validate_recovery_readiness(out_dir / "recovery-readiness.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "recovery-readiness.csv")

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.rows, 3)
        pilot = next(row for row in rows if row["workload_id"] == "vm-1001")
        self.assertEqual(pilot["schema_version"], RECOVERY_READINESS_SCHEMA_VERSION)
        self.assertEqual(pilot["recovery_status"], "remediate")
        self.assertEqual(pilot["backup_protected"], "true")
        self.assertEqual(pilot["snapshot_count"], "1")
        self.assertIn("backup_recovery_point_stale", pilot["blocking_findings"])
        self.assertIn("snapshot_age_exceeds_policy", pilot["blocking_findings"])
        self.assertIn("Run or verify a fresh successful backup", pilot["required_action"])

    def test_recovery_readiness_validator_detects_tampering(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp), with_recovery_risk=True)
            path = out_dir / "recovery-readiness.csv"
            rows = read_rows(path)
            for row in rows:
                if row["workload_id"] == "vm-1001":
                    row["recovery_status"] = "ready"
            write_rows(path, rows)

            result = validate_recovery_readiness(path, out_dir / "assessment.json")

        self.assertFalse(result.ok)
        self.assertTrue(any("vm-1001: recovery_status expected 'remediate'" in error for error in result.errors))

    def test_recovery_readiness_rejects_stale_context_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp), with_recovery_risk=True)
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["recovery_readiness_context"]["workloads"][0]["owner"] = "Wrong Owner"
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_recovery_readiness(out_dir / "recovery-readiness.csv", assessment_path)

        self.assertFalse(result.ok)
        self.assertTrue(any("recovery_readiness_context" in error and "owner expected" in error for error in result.errors))

    def test_recovery_readiness_rejects_stale_context_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp), with_recovery_risk=True)
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["recovery_readiness_context"]["workloads"][0]["recovery_status"] = "ready"
            assessment["recovery_readiness_context"]["workloads"][0]["blocking_findings"] = ""
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_recovery_readiness(out_dir / "recovery-readiness.csv", assessment_path)

        self.assertFalse(result.ok)
        self.assertTrue(any("recovery_status expected 'remediate'" in error for error in result.errors))
        self.assertTrue(any("blocking_findings expected" in error for error in result.errors))

    def test_recovery_readiness_rejects_unknown_context_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp), with_recovery_risk=True)
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            ghost = dict(assessment["recovery_readiness_context"]["workloads"][0])
            ghost["workload_id"] = "vm-ghost"
            assessment["recovery_readiness_context"]["workloads"].append(ghost)
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_recovery_readiness(out_dir / "recovery-readiness.csv", assessment_path)

        self.assertFalse(result.ok)
        self.assertTrue(any("references unknown workload_id 'vm-ghost'" in error for error in result.errors))

    def test_cli_validate_recovery_readiness(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp), with_recovery_risk=True)

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-recovery-readiness",
                        "--readiness",
                        str(out_dir / "recovery-readiness.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

        self.assertEqual(code, 0)


def build_assessment(tmp: Path, *, with_recovery_risk: bool = False) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    if with_recovery_risk:
        inventory["workloads"][0]["backup"]["last_success_hours"] = 72
        inventory["workloads"][0]["snapshots"] = {
            "count": 1,
            "oldest_days": 12,
            "oldest_created_at": "2026-07-01T20:00:00+00:00",
        }
        inventory["workloads"][0]["governance"] = {"rollback_owner": ""}
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return [dict(row) for row in csv.DictReader(handle)]


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    unittest.main()
