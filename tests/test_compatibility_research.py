from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.compatibility_research import read_rows, validate_compatibility_research
from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class CompatibilityResearchTests(unittest.TestCase):
    def test_write_assessment_generates_compatibility_research(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_compatibility_research(out_dir / "compatibility-research.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "compatibility-research.csv", [])

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.rows, 3)
            by_id = {row["workload_id"]: row for row in rows}
            self.assertEqual(by_id["vm-1001"]["guest_os_status"], "known_good")
            self.assertEqual(by_id["vm-1001"]["target_support_status"], "confirmed")
            self.assertEqual(by_id["vm-1001"]["compatibility_status"], "ready")
            self.assertEqual(by_id["vm-3030"]["guest_os_status"], "research_required")
            self.assertEqual(by_id["vm-3030"]["target_support_status"], "unconfirmed")
            self.assertEqual(by_id["vm-3030"]["compatibility_status"], "research")

    def test_compatibility_research_validator_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "compatibility-research.csv"
            rows = read_rows(path, [])
            rows[0]["compatibility_status"] = "research"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_compatibility_research(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("compatibility_status expected 'ready'" in error for error in result.errors))

    def test_cli_validate_compatibility_research(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-compatibility-research",
                        "--research",
                        str(out_dir / "compatibility-research.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(code, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    inventory = merge_metadata(inventory, read_metadata_csv(Path("examples/sample_metadata.csv")))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
