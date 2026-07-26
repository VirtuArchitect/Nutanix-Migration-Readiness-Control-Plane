from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.move_staging_readiness import read_rows, validate_move_staging_brief, validate_move_staging_readiness
from nmrcp.change_gate import run_change_gate
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


ROOT = Path(__file__).resolve().parents[1]


class MoveStagingReadinessTests(unittest.TestCase):
    def test_write_assessment_generates_move_staging_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            result = validate_move_staging_readiness(out_dir / "move-staging-readiness.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "move-staging-readiness.csv", [])

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(len(rows), 3)
            by_id = {row["workload_id"]: row for row in rows}
            self.assertEqual(by_id["vm-1001"]["stage_status"], "hold")
            self.assertIn("application_owner_approval_missing", by_id["vm-1001"]["blocking_findings"])
            self.assertEqual(by_id["vm-2020"]["stage_status"], "hold")
            self.assertIn("readiness_blocked", by_id["vm-2020"]["blocking_findings"])
            self.assertEqual(by_id["vm-3030"]["stage_status"], "hold")
            self.assertIn("recovery_blocked", by_id["vm-3030"]["blocking_findings"])

            brief_result = validate_move_staging_brief(out_dir / "move-staging-brief.md", out_dir / "assessment.json")
            brief = (out_dir / "move-staging-brief.md").read_text(encoding="utf-8")

            self.assertTrue(brief_result.ok, brief_result.errors)
            self.assertIn("# Move Staging Brief", brief)
            self.assertIn("nmrcp_move_staging_brief_v1", brief)
            self.assertIn("Decision signal: Hold blocked workloads out of Nutanix Move", brief)
            self.assertIn("No workloads are currently ready for Move staging precheck.", brief)
            self.assertIn("stage_status=hold", brief)
            self.assertIn("move-staging-readiness.csv", brief)
            self.assertNotIn("vcenter01.corp.local", brief)

    def test_move_staging_readiness_validator_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "move-staging-readiness.csv"
            rows = read_rows(path, [])
            rows[1]["stage_status"] = "ready"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_move_staging_readiness(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("stage_status expected 'hold'" in error for error in result.errors))

    def test_move_staging_brief_validator_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "move-staging-brief.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("Do not open Nutanix Move staging", "Open Nutanix Move staging", 1),
                encoding="utf-8",
            )

            result = validate_move_staging_brief(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("missing required text" in error or "does not match" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_move_staging_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "move-staging-brief.md"
            path.write_text(
                path.read_text(encoding="utf-8").replace("nmrcp_move_staging_brief_v1", "nmrcp_old_move_staging_brief_v1"),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "move-staging-brief" and check["status"] == "fail" for check in result.checks))

    def test_cli_validate_move_staging_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            code = main(
                [
                    "validate-move-staging-readiness",
                    "--readiness",
                    str(out_dir / "move-staging-readiness.csv"),
                    "--assessment",
                    str(out_dir / "assessment.json"),
                ]
            )

            self.assertEqual(code, 0)

    def test_cli_validate_move_staging_brief(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            code = main(
                [
                    "validate-move-staging-brief",
                    "--brief",
                    str(out_dir / "move-staging-brief.md"),
                    "--assessment",
                    str(out_dir / "assessment.json"),
                ]
            )

            self.assertEqual(code, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads((ROOT / "examples" / "sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
