from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.dependencies import merge_dependencies, read_dependency_csv
from nmrcp.dependency_review import read_rows, validate_dependency_review
from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class DependencyReviewTests(unittest.TestCase):
    def test_write_assessment_generates_dependency_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_dependency_review(out_dir / "dependency-review.csv", out_dir / "assessment.json")
            rows = read_rows(out_dir / "dependency-review.csv", [])

            self.assertTrue(result.ok, result.errors)
            self.assertEqual(result.rows, 4)
            by_key = {(row["row_type"], row["source_workload_id"], row["dependency_name"]): row for row in rows}
            external = by_key[("dependency", "vm-3030", "external-hsm")]
            self.assertEqual(external["dependency_owner"], "not assigned")
            self.assertEqual(external["stage_impact"], "blocks_staging")
            self.assertIn("dependency_owner_missing", external["blocking_findings"])
            unmatched = by_key[("unmatched_dependency", "vm-9999", "orphan-service")]
            self.assertEqual(unmatched["stage_impact"], "cleanup")
            self.assertIn("unmatched_dependency_source", unmatched["blocking_findings"])

    def test_dependency_review_validator_detects_tampering(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            path = out_dir / "dependency-review.csv"
            rows = read_rows(path, [])
            rows[0]["stage_impact"] = "ready"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)

            result = validate_dependency_review(path, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("stage_impact expected" in error for error in result.errors))

    def test_cli_validate_dependency_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-dependency-review",
                        "--review",
                        str(out_dir / "dependency-review.csv"),
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
    waves = plan_waves(assessments, inventory)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
