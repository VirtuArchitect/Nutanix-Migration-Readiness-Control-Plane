import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.move_lab_closure_checklist import REQUIRED_FRAGMENTS as CLOSURE_FRAGMENTS
from nmrcp.move_lab_closure_checklist import REQUIRED_SECTIONS as CLOSURE_SECTIONS
from nmrcp.move_lab_evidence_intake import validate_move_lab_evidence_preflight
from nmrcp.move_lab_evidence_request import REQUIRED_FRAGMENTS as REQUEST_FRAGMENTS
from nmrcp.move_lab_evidence_request import REQUIRED_SECTIONS as REQUEST_SECTIONS
from nmrcp.move_lab_readiness_packet import validate_move_lab_readiness_packet, write_move_lab_readiness_packet
from nmrcp.move_lab_runbook import write_move_lab_runbook
from nmrcp.move_submit_readiness import validate_move_submit_readiness

from tests.test_move_lab_evidence_intake import write_approved_evidence_set


class MoveLabReadinessPacketTests(unittest.TestCase):
    def test_write_and_validate_move_lab_readiness_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "os.environ",
            {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"},
        ):
            root = Path(tmp)
            paths = write_ready_packet_inputs(root)
            packet = root / "move-lab-readiness-packet.json"
            report = root / "move-lab-readiness-packet.md"

            result = write_move_lab_readiness_packet(
                payload_path=paths["payload_path"],
                review_path=paths["review_path"],
                move_submit_readiness_path=paths["move_submit_readiness_path"],
                capture_kit_dir=paths["capture_kit_dir"],
                capture_kit_validation_path=paths["capture_kit_validation_path"],
                evidence_preflight_path=paths["evidence_preflight_path"],
                evidence_preflight_report_path=paths["evidence_preflight_report_path"],
                runbook_path=paths["runbook_path"],
                evidence_request_path=paths["evidence_request_path"],
                closure_checklist_path=paths["closure_checklist_path"],
                out_path=packet,
                report_path=report,
            )
            validation = validate_move_lab_readiness_packet(packet, report_path=report)
            payload = json.loads(packet.read_text(encoding="utf-8"))
            report_text = report.read_text(encoding="utf-8")

        self.assertTrue(result.ok, result.errors)
        self.assertTrue(validation.ok, validation.errors)
        self.assertEqual(payload["schema_version"], "nmrcp_move_lab_readiness_packet_v1")
        self.assertTrue(payload["flags"]["not_external_proof"])
        self.assertIn("generate-approved-move-lab-proof", payload["required_closeout"])
        self.assertIn("not external proof", report_text)

    def test_cli_generates_and_validates_move_lab_readiness_packet(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "os.environ",
            {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"},
        ):
            root = Path(tmp)
            paths = write_ready_packet_inputs(root)
            packet = root / "move-lab-readiness-packet.json"
            report = root / "move-lab-readiness-packet.md"

            with patch("sys.stdout"):
                code = main(
                    [
                        "move-lab-readiness-packet",
                        "--payload",
                        str(paths["payload_path"]),
                        "--review",
                        str(paths["review_path"]),
                        "--move-submit-readiness",
                        str(paths["move_submit_readiness_path"]),
                        "--capture-kit",
                        str(paths["capture_kit_dir"]),
                        "--capture-kit-validation",
                        str(paths["capture_kit_validation_path"]),
                        "--evidence-preflight",
                        str(paths["evidence_preflight_path"]),
                        "--evidence-preflight-report",
                        str(paths["evidence_preflight_report_path"]),
                        "--runbook",
                        str(paths["runbook_path"]),
                        "--evidence-request",
                        str(paths["evidence_request_path"]),
                        "--closure-checklist",
                        str(paths["closure_checklist_path"]),
                        "--out",
                        str(packet),
                        "--report",
                        str(report),
                    ]
                )
                validation_code = main(["validate-move-lab-readiness-packet", "--packet", str(packet), "--report", str(report)])

        self.assertEqual(code, 0)
        self.assertEqual(validation_code, 0)

    def test_validate_rejects_packet_missing_proof_generator(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "os.environ",
            {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"},
        ):
            root = Path(tmp)
            paths = write_ready_packet_inputs(root)
            packet = root / "move-lab-readiness-packet.json"
            write_move_lab_readiness_packet(
                payload_path=paths["payload_path"],
                review_path=paths["review_path"],
                move_submit_readiness_path=paths["move_submit_readiness_path"],
                capture_kit_dir=paths["capture_kit_dir"],
                capture_kit_validation_path=paths["capture_kit_validation_path"],
                evidence_preflight_path=paths["evidence_preflight_path"],
                evidence_preflight_report_path=paths["evidence_preflight_report_path"],
                runbook_path=paths["runbook_path"],
                evidence_request_path=paths["evidence_request_path"],
                closure_checklist_path=paths["closure_checklist_path"],
                out_path=packet,
            )
            payload = json.loads(packet.read_text(encoding="utf-8"))
            payload["required_closeout"].remove("generate-approved-move-lab-proof")
            packet.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            result = validate_move_lab_readiness_packet(packet)

        self.assertFalse(result.ok)
        self.assertTrue(any("generate-approved-move-lab-proof" in error for error in result.errors))

    def test_validate_rejects_report_missing_required_closeout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "os.environ",
            {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"},
        ):
            root = Path(tmp)
            paths = write_ready_packet_inputs(root)
            packet = root / "move-lab-readiness-packet.json"
            report = root / "move-lab-readiness-packet.md"
            write_move_lab_readiness_packet(
                payload_path=paths["payload_path"],
                review_path=paths["review_path"],
                move_submit_readiness_path=paths["move_submit_readiness_path"],
                capture_kit_dir=paths["capture_kit_dir"],
                capture_kit_validation_path=paths["capture_kit_validation_path"],
                evidence_preflight_path=paths["evidence_preflight_path"],
                evidence_preflight_report_path=paths["evidence_preflight_report_path"],
                runbook_path=paths["runbook_path"],
                evidence_request_path=paths["evidence_request_path"],
                closure_checklist_path=paths["closure_checklist_path"],
                out_path=packet,
                report_path=report,
            )
            command = "validate-move-lab-transcript"
            report.write_text(report.read_text(encoding="utf-8").replace(f"- `{command}`\n", ""), encoding="utf-8")

            result = validate_move_lab_readiness_packet(packet, report_path=report)

        self.assertFalse(result.ok)
        self.assertTrue(any(f"missing closeout command: {command}" in error for error in result.errors))

    def test_validate_rejects_report_missing_artifact_role(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            "os.environ",
            {"NMRCP_MOVE_LAB_ACK": "I_UNDERSTAND_LAB_ONLY"},
        ):
            root = Path(tmp)
            paths = write_ready_packet_inputs(root)
            packet = root / "move-lab-readiness-packet.json"
            report = root / "move-lab-readiness-packet.md"
            write_move_lab_readiness_packet(
                payload_path=paths["payload_path"],
                review_path=paths["review_path"],
                move_submit_readiness_path=paths["move_submit_readiness_path"],
                capture_kit_dir=paths["capture_kit_dir"],
                capture_kit_validation_path=paths["capture_kit_validation_path"],
                evidence_preflight_path=paths["evidence_preflight_path"],
                evidence_preflight_report_path=paths["evidence_preflight_report_path"],
                runbook_path=paths["runbook_path"],
                evidence_request_path=paths["evidence_request_path"],
                closure_checklist_path=paths["closure_checklist_path"],
                out_path=packet,
                report_path=report,
            )
            role = "capture_kit_validation"
            report.write_text(report.read_text(encoding="utf-8").replace(f"`{role}`", "`removed_role`", 1), encoding="utf-8")

            result = validate_move_lab_readiness_packet(packet, report_path=report)

        self.assertFalse(result.ok)
        self.assertTrue(any(f"missing artifact role: {role}" in error for error in result.errors))


def write_ready_packet_inputs(root: Path) -> dict[str, Path]:
    paths = write_approved_evidence_set(root)
    move_submit_readiness_path = root / "move-submit-readiness.json"
    readiness = validate_move_submit_readiness(paths["payload_path"], paths["review_path"])
    move_submit_readiness_path.write_text(json.dumps(readiness.to_dict(), indent=2), encoding="utf-8")

    capture_kit_dir = root / "move-lab-capture-kit"
    capture_kit_dir.mkdir()
    (capture_kit_dir / "move-lab-transcript.template.json").write_text(
        json.dumps({"redacted": "[REDACTED_LAB_MOVE_APPLIANCE]"}, indent=2),
        encoding="utf-8",
    )
    (capture_kit_dir / "move-lab-capture-checklist.md").write_text("# Move Lab Capture Checklist\n\n[REDACTED_LAB_MOVE_APPLIANCE]\n", encoding="utf-8")

    runbook_path = root / "move-lab-execution-runbook.md"
    write_move_lab_runbook(paths["payload_path"], paths["review_path"], runbook_path)

    evidence_preflight_path = root / "move-lab-evidence-preflight.json"
    evidence_preflight_report_path = root / "move-lab-evidence-preflight.md"
    preflight = validate_move_lab_evidence_preflight(
        paths["payload_path"],
        paths["review_path"],
        paths["capture_kit_validation_path"],
        paths["transcript_path"],
        paths["transcript_validation_path"],
        paths["proof_path"],
        paths["proof_validation_path"],
        root / "move-lab-evidence-intake.json",
    )
    evidence_preflight_path.write_text(json.dumps(preflight.to_dict(), indent=2), encoding="utf-8")
    evidence_preflight_report_path.write_text(preflight.to_markdown(), encoding="utf-8")

    evidence_request_path = root / "move-lab-evidence-request.md"
    evidence_request_path.write_text(valid_markdown(REQUEST_SECTIONS, REQUEST_FRAGMENTS), encoding="utf-8")
    closure_checklist_path = root / "move-lab-closure-checklist.md"
    closure_checklist_path.write_text(valid_markdown(CLOSURE_SECTIONS, CLOSURE_FRAGMENTS), encoding="utf-8")

    return {
        **paths,
        "move_submit_readiness_path": move_submit_readiness_path,
        "capture_kit_dir": capture_kit_dir,
        "evidence_preflight_path": evidence_preflight_path,
        "evidence_preflight_report_path": evidence_preflight_report_path,
        "runbook_path": runbook_path,
        "evidence_request_path": evidence_request_path,
        "closure_checklist_path": closure_checklist_path,
    }


def valid_markdown(sections: tuple[str, ...], fragments: tuple[str, ...]) -> str:
    return "\n\n".join([*sections, *fragments, "production", "redacted"])


if __name__ == "__main__":
    unittest.main()
