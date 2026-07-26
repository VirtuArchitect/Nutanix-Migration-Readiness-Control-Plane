import tempfile
import unittest
from pathlib import Path

from nmrcp.move_lab_closure_checklist import validate_move_lab_closure_checklist, write_move_lab_closure_checklist


class MoveLabClosureChecklistTests(unittest.TestCase):
    def test_generated_checklist_validates_required_proof_chain(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "move-lab-closure-checklist.md"

            write_move_lab_closure_checklist(path)
            result = validate_move_lab_closure_checklist(path)

            self.assertTrue(result.ok, result.errors)
            text = path.read_text(encoding="utf-8")
            self.assertIn("nmrcp_move_lab_evidence_intake_v1", text)
            self.assertIn("proof_scope=approved_lab_move_appliance", text)
            self.assertIn("--move-lab-evidence-intake", text)
            self.assertIn("summarize-gates `\n  --dir outputs\\sample-assessment", text)
            self.assertIn("change-gate `\n  --dir outputs\\sample-assessment", text)
            self.assertIn("package-handoff `\n  --dir outputs\\sample-assessment", text)
            self.assertIn("mvp-audit `\n  --repo-root . `\n  --assessment-dir outputs\\sample-assessment", text)
            self.assertIn("--out outputs\\mvp-audit.json", text)
            self.assertNotIn("--json-out outputs\\mvp-audit.json", text)

    def test_validator_rejects_missing_evidence_intake_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "move-lab-closure-checklist.md"
            write_move_lab_closure_checklist(path)
            text = path.read_text(encoding="utf-8").replace("`nmrcp_move_lab_evidence_intake_v1`", "`missing_schema`")
            path.write_text(text, encoding="utf-8")

            result = validate_move_lab_closure_checklist(path)

            self.assertFalse(result.ok)
            self.assertTrue(any("nmrcp_move_lab_evidence_intake_v1" in error for error in result.errors))

    def test_validator_rejects_stale_cli_flags(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "move-lab-closure-checklist.md"
            write_move_lab_closure_checklist(path)
            text = path.read_text(encoding="utf-8")
            text = text.replace("summarize-gates `\n  --dir", "summarize-gates `\n  --assessment-dir")
            text = text.replace("--out outputs\\mvp-audit.json", "--json-out outputs\\mvp-audit.json")
            path.write_text(text, encoding="utf-8")

            result = validate_move_lab_closure_checklist(path)

            self.assertFalse(result.ok)
            self.assertTrue(any("stale CLI flag" in error and "summarize-gates" in error for error in result.errors))
            self.assertTrue(any("stale CLI flag" in error and "--json-out" in error for error in result.errors))


if __name__ == "__main__":
    unittest.main()
