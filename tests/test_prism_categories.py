import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.change_gate import run_change_gate
from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.prism_categories import validate_prism_category_mapping
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class PrismCategoryMappingTests(unittest.TestCase):
    def test_generated_prism_category_mapping_matches_assessment_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment = json.loads((out_dir / "assessment.json").read_text(encoding="utf-8"))

            context = assessment["prism_category_context"]
            result = validate_prism_category_mapping(out_dir / "prism-category-mapping.csv", out_dir / "assessment.json")

            self.assertEqual(context["schema_version"], "nmrcp_prism_category_mapping_v1")
            self.assertEqual(len(context["workloads"]), 3)
            self.assertTrue(result.ok, result.errors)
            mapping = (out_dir / "prism-category-mapping.csv").read_text(encoding="utf-8")
            self.assertIn("NMRCP:Owner=Platform_Team", mapping)
            self.assertIn("NMRCP:Readiness=blocked", mapping)
            self.assertIn("review_only_prism_category_plan", mapping)

    def test_prism_category_mapping_rejects_tampered_assignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            mapping = out_dir / "prism-category-mapping.csv"
            mapping.write_text(
                mapping.read_text(encoding="utf-8").replace("NMRCP:Readiness=ready", "NMRCP:Readiness=blocked", 1),
                encoding="utf-8",
            )

            result = validate_prism_category_mapping(mapping, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("category_assignments expected" in error for error in result.errors))

    def test_prism_category_mapping_rejects_stale_context_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["prism_category_context"]["workloads"][0]["owner"] = "Wrong Owner"
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_prism_category_mapping(out_dir / "prism-category-mapping.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("prism_category_context" in error and "owner expected" in error for error in result.errors))

    def test_prism_category_mapping_rejects_stale_context_assignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            assessment["prism_category_context"]["workloads"][0]["category_assignments"] = (
                assessment["prism_category_context"]["workloads"][0]["category_assignments"].replace(
                    "NMRCP:Readiness=ready",
                    "NMRCP:Readiness=blocked",
                )
            )
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_prism_category_mapping(out_dir / "prism-category-mapping.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("NMRCP:Readiness expected 'ready'" in error for error in result.errors))

    def test_prism_category_mapping_rejects_unknown_context_workload(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            assessment_path = out_dir / "assessment.json"
            assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
            ghost = dict(assessment["prism_category_context"]["workloads"][0])
            ghost["workload_id"] = "vm-ghost"
            assessment["prism_category_context"]["workloads"].append(ghost)
            assessment_path.write_text(json.dumps(assessment, indent=2), encoding="utf-8")

            result = validate_prism_category_mapping(out_dir / "prism-category-mapping.csv", assessment_path)

            self.assertFalse(result.ok)
            self.assertTrue(any("references unknown workload_id 'vm-ghost'" in error for error in result.errors))

    def test_change_gate_fails_on_tampered_prism_category_mapping(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            mapping = out_dir / "prism-category-mapping.csv"
            mapping.write_text(
                mapping.read_text(encoding="utf-8").replace("review_only_prism_category_plan", "apply_to_prism_now", 1),
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any(check["name"] == "prism-category-mapping" and check["status"] == "fail" for check in result.checks))

    def test_cli_validate_prism_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                result = main(
                    [
                        "validate-prism-categories",
                        "--mapping",
                        str(out_dir / "prism-category-mapping.csv"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(result, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
