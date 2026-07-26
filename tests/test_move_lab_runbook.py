import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.move_lab_proof import write_move_lab_proof_template
from nmrcp.move_lab_runbook import validate_move_lab_runbook, write_move_lab_runbook
from nmrcp.redaction_review import scan_text


class MoveLabRunbookTests(unittest.TestCase):
    def test_write_move_lab_runbook_redacts_lab_identifiers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root)
            proof_template = root / "move-lab-proof.template.json"
            runbook = root / "move-lab-runbook.md"
            write_move_lab_proof_template(
                payload,
                Path("examples/sample_move_submit_review.json"),
                proof_template,
                proof_scope="approved_lab_move_appliance",
            )

            write_move_lab_runbook(
                payload,
                Path("examples/sample_move_submit_review.json"),
                runbook,
                proof_template_path=proof_template,
            )

            text = runbook.read_text(encoding="utf-8")
        self.assertIn("# Move Lab Execution Runbook", text)
        self.assertIn("NMRCP_MOVE_LAB_ACK", text)
        self.assertIn("approved_lab_move_appliance", text)
        self.assertIn("validate-move-lab-transcript", text)
        self.assertIn("generate-approved-move-lab-proof", text)
        self.assertIn("--transcript-validation", text)
        self.assertIn("validate-move-lab-evidence-intake", text)
        self.assertIn("--capture-kit-validation outputs\\move-lab-capture-kit-validation.json", text)
        self.assertIn("Move lab evidence intake JSON with `status=pass`", text)
        self.assertIn("mvp-audit --move-proof --move-lab-evidence-intake", text)
        self.assertIn("Stop Conditions", text)
        self.assertNotIn("move-lab-01.example.test", text)
        self.assertFalse(scan_text("move-lab-runbook.md", text))

    def test_cli_generate_move_lab_runbook_writes_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root)
            runbook = root / "move-lab-runbook.md"

            with patch("sys.stdout"):
                code = main(
                    [
                        "generate-move-lab-runbook",
                        "--payload",
                        str(payload),
                        "--review",
                        "examples/sample_move_submit_review.json",
                        "--out",
                        str(runbook),
                    ]
                )

            text = runbook.read_text(encoding="utf-8")
        self.assertEqual(code, 0)
        self.assertIn("Validation Commands", text)
        self.assertIn("generate-approved-move-lab-proof", text)
        self.assertIn("validate-move-lab-proof", text)
        self.assertIn("validate-move-lab-evidence-intake", text)

    def test_validate_move_lab_runbook_accepts_generated_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root)
            runbook = root / "move-lab-runbook.md"
            write_move_lab_runbook(
                payload,
                Path("examples/sample_move_submit_review.json"),
                runbook,
            )

            result = validate_move_lab_runbook(runbook)

        self.assertTrue(result.ok, result.errors)
        self.assertEqual(result.status, "pass")
        self.assertGreaterEqual(result.checks, 20)

    def test_validate_move_lab_runbook_rejects_stale_closeout_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root)
            runbook = root / "move-lab-runbook.md"
            write_move_lab_runbook(
                payload,
                Path("examples/sample_move_submit_review.json"),
                runbook,
            )
            text = runbook.read_text(encoding="utf-8").replace("validate-move-lab-evidence-intake", "validate-move-lab-proof")
            runbook.write_text(text, encoding="utf-8")

            result = validate_move_lab_runbook(runbook)

        self.assertFalse(result.ok)
        self.assertTrue(any("validate-move-lab-evidence-intake" in error for error in result.errors))

    def test_validate_move_lab_runbook_rejects_missing_proof_generator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root)
            runbook = root / "move-lab-runbook.md"
            write_move_lab_runbook(
                payload,
                Path("examples/sample_move_submit_review.json"),
                runbook,
            )
            text = runbook.read_text(encoding="utf-8").replace("generate-approved-move-lab-proof", "validate-move-lab-proof")
            runbook.write_text(text, encoding="utf-8")

            result = validate_move_lab_runbook(runbook)

        self.assertFalse(result.ok)
        self.assertTrue(any("generate-approved-move-lab-proof" in error for error in result.errors))

    def test_cli_validate_move_lab_runbook_reports_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = write_payload(root)
            runbook = root / "move-lab-runbook.md"
            write_move_lab_runbook(
                payload,
                Path("examples/sample_move_submit_review.json"),
                runbook,
            )

            with patch("sys.stdout"):
                code = main(["validate-move-lab-runbook", "--runbook", str(runbook)])

        self.assertEqual(code, 0)

    def test_cli_rejects_invalid_payload_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            payload = root / "payload.json"
            payload.write_text(json.dumps([]), encoding="utf-8")

            with patch("sys.stdout"):
                with self.assertRaises(ValueError):
                    main(
                        [
                            "generate-move-lab-runbook",
                            "--payload",
                            str(payload),
                            "--review",
                            "examples/sample_move_submit_review.json",
                            "--out",
                            str(root / "runbook.md"),
                        ]
                    )

def write_payload(root: Path) -> Path:
    path = root / "move-api-payload.lab.dry-run.json"
    path.write_text(
        json.dumps(
            {
                "contract": "nmrcp_move_api_payload_dry_run_v1",
                "dry_run_only": True,
                "mutation_allowed": False,
                "source_provider": {"uuid": "source-provider-lab"},
                "target_provider": {"uuid": "target-provider-lab"},
                "target_cluster": {"uuid": "cluster-lab"},
                "target_container": {"uuid": "container-lab"},
                "network_mappings": [{"source": "vlan-120", "target": "ahv-vlan-120"}],
                "schedule": {"mode": "manual", "start_immediately": False},
                "workloads": [
                    {
                        "source_vm_id": "vm-1",
                        "source_vm_name": "web-01",
                        "wave": "0",
                        "target": "ahv",
                        "readiness": "ready",
                        "risk_score": 18,
                        "dependency_count": 0,
                    }
                ],
                "validation": {"network_mapping": "PASS: checked=1, mapped=1, errors=0, warnings=0"},
                "operator_notes": ["test fixture"],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
