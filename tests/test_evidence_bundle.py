import json
import zipfile
import tempfile
import unittest
from pathlib import Path

from nmrcp.evidence import write_assessment
from nmrcp.evidence_bundle import package_evidence, verify_evidence, verify_evidence_bundle
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class EvidenceBundleTests(unittest.TestCase):
    def test_verify_and_package_evidence_bundle(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            bundle = Path(tmp) / "evidence.zip"
            write_assessment(inventory, assessments, waves, out_dir)

            directory_result = verify_evidence(out_dir)
            package_evidence(out_dir, bundle)
            bundle_result = verify_evidence_bundle(bundle)

            self.assertTrue(directory_result.ok, directory_result.errors)
            self.assertTrue(bundle_result.ok, bundle_result.errors)
            self.assertEqual(directory_result.checked, bundle_result.checked)

    def test_verify_evidence_detects_tampering(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            write_assessment(inventory, assessments, waves, out_dir)
            (out_dir / "assessment.json").write_text("tampered", encoding="utf-8")

            result = verify_evidence(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("assessment.json" in error for error in result.errors))

    def test_verify_evidence_bundle_rejects_unmanifested_archive_entry(self):
        inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
        assessments = assess_inventory(inventory)
        waves = plan_waves(assessments)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "assessment"
            bundle = Path(tmp) / "evidence.zip"
            broken = Path(tmp) / "evidence-extra.zip"
            write_assessment(inventory, assessments, waves, out_dir)
            package_evidence(out_dir, bundle)

            with zipfile.ZipFile(bundle, "r") as source, zipfile.ZipFile(broken, "w", compression=zipfile.ZIP_DEFLATED) as target:
                for name in source.namelist():
                    target.writestr(name, source.read(name))
                target.writestr("untracked/customer-export.csv", "vm,password\napp-01,secret\n")

            result = verify_evidence_bundle(broken)

            self.assertFalse(result.ok)
            self.assertTrue(any("untracked/customer-export.csv: bundle entry is not listed in evidence manifest" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
