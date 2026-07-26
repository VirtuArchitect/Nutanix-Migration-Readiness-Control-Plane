import json
import tempfile
import unittest
from pathlib import Path

from nmrcp.change_gate import run_change_gate
from nmrcp.evidence import write_assessment
from nmrcp.redaction_review import review_evidence_dir, scan_text
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class RedactionReviewTests(unittest.TestCase):
    def test_review_passes_generated_redacted_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))

            result = review_evidence_dir(out_dir)

            self.assertTrue(result.ok, result.findings)
            self.assertGreaterEqual(result.checked, 10)

    def test_review_detects_unredacted_sensitive_patterns(self):
        findings = scan_text(
            "change-board-evidence.md",
            "endpoint=https://vcenter01.corp.local/sdk\noperator=owner@example.com\nip=10.20.30.40",
        )

        self.assertTrue(any("url" in finding for finding in findings))
        self.assertTrue(any("email" in finding for finding in findings))
        self.assertTrue(any("ip" in finding for finding in findings))

    def test_change_gate_fails_when_evidence_contains_unredacted_url(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_sample_assessment(Path(tmp))
            (out_dir / "change-board-evidence.md").write_text(
                "raw endpoint https://vcenter01.corp.local/sdk",
                encoding="utf-8",
            )

            result = run_change_gate(out_dir)

            self.assertFalse(result.ok)
            self.assertTrue(any("potential url leak" in error for error in result.errors))


def build_sample_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
