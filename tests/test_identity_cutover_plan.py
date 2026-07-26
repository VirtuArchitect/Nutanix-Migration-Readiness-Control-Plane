from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.identity_cutover_plan import read_rows, validate_identity_cutover_plan
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class IdentityCutoverPlanTests(unittest.TestCase):
    def test_write_assessment_generates_identity_cutover_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_identity_cutover_plan(out_dir / "identity-cutover-plan.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "identity-cutover-plan.csv", [])

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.rows, 3)
            by_id = {row["workload_id"]: row for row in rows}
            self.assertEqual(by_id["vm-1001"]["identity_status"], "ready")
            self.assertEqual(by_id["vm-1001"]["valid_ip_addresses"], "[REDACTED_IP]")
            self.assertEqual(by_id["vm-2020"]["identity_status"], "blocked")
            self.assertEqual(by_id["vm-2020"]["invalid_ip_addresses"], "[REDACTED_IP]")
            self.assertEqual(by_id["vm-3030"]["identity_status"], "hold")

    def test_identity_cutover_validator_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "identity-cutover-plan.csv"
            rows = read_rows(path, [])
            rows[0]["identity_status"] = "blocked"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_identity_cutover_plan(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("identity_status expected 'ready'" in error for error in result.errors))

    def test_cli_validate_identity_cutover_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-identity-cutover-plan",
                        "--plan",
                        str(out_dir / "identity-cutover-plan.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(code, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
