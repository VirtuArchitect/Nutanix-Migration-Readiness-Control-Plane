import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.change_gate import run_change_gate
from nmrcp.cli import main
from nmrcp.dependency_sequence import validate_dependency_sequence
from nmrcp.evidence import write_assessment
from nmrcp.metadata import merge_metadata, read_metadata_csv
from nmrcp.dependencies import merge_dependencies, read_dependency_csv
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class DependencySequenceContractTests(unittest.TestCase):
    def test_assessment_contains_redacted_dependency_sequence_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment = json.loads((out_dir / "assessment.json").read_text(encoding="utf-8"))

            context = assessment["dependency_sequence_context"]

            self.assertEqual(context["schema_version"], "nmrcp_dependency_sequence_context_v1")
            self.assertGreaterEqual(len(context["workloads"]), 1)
            self.assertNotIn("password", json.dumps(context).lower())

    def test_validate_dependency_sequence_matches_assessment(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_dependency_sequence(out_dir / "dependency-sequence.csv", out_dir / "assessment.json")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("rows=", result.summary())

    def test_validate_dependency_sequence_rejects_tampered_order_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            sequence = out_dir / "dependency-sequence.csv"
            sequence.write_text(
                sequence.read_text(encoding="utf-8").replace("1,vm-1001", "99,vm-1001"),
                encoding="utf-8",
            )

            result = validate_dependency_sequence(sequence, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("vm-1001: sequence expected '1'" in error for error in result.errors))

    def test_validate_dependency_sequence_rejects_tampered_embedded_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["dependency_sequence_context"]["workloads"][0]["readiness"] = "blocked"
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_dependency_sequence(out_dir / "dependency-sequence.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("readiness does not match assessment row" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_dependency_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            sequence = out_dir / "dependency-sequence.csv"
            sequence.write_text(
                sequence.read_text(encoding="utf-8").replace("dependency-aware included workload order", "manual override", 1),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "dependency-sequence" and check["status"] == "fail" for check in result.checks))

    def test_cli_validate_dependency_sequence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                result = main(
                    [
                        "validate-dependency-sequence",
                        "--sequence",
                        str(out_dir / "dependency-sequence.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(result, 0)


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
