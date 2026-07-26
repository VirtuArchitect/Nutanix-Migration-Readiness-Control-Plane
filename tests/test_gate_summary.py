import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.capacity import validate_capacity_fit, write_capacity_fit_csv
from nmrcp.cli import main
from nmrcp.evidence import write_assessment, write_evidence_manifest
from nmrcp.gate_summary import validate_operator_gate_summary, write_operator_gate_summary
from nmrcp.scoring import assess_inventory
from nmrcp.source_networks import validate_source_networks, write_source_network_validation_csv
from nmrcp.target_reconciliation import reconcile_target_inventory, write_target_reconciliation_csv
from nmrcp.waves import plan_waves


class GateSummaryTests(unittest.TestCase):
    def test_operator_gate_summary_surfaces_optional_gate_statuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            capacity = validate_capacity_fit(
                Path("examples/sample_inventory.json"),
                out_dir / "nutanix-move-plan.csv",
                Path("examples/sample_target_capacity.json"),
            )
            write_capacity_fit_csv(capacity, out_dir / "target-capacity-fit.csv")
            reconciliation = reconcile_target_inventory(
                Path("examples/sample_inventory.json"),
                Path("examples/sample_prism_inventory.json"),
                out_dir / "nutanix-move-plan.csv",
            )
            write_target_reconciliation_csv(reconciliation, out_dir / "target-reconciliation.csv")
            source_networks = validate_source_networks(
                out_dir / "nutanix-move-plan.csv",
                write_vcenter_network_inventory(Path(tmp), ["120"]),
            )
            write_source_network_validation_csv(source_networks, out_dir / "source-network-validation.csv")
            write_evidence_manifest(out_dir / "evidence-manifest.json", out_dir)

            output = write_operator_gate_summary(
                out_dir,
                validation_results_path=Path("examples/sample_validation_results.csv"),
                remediation_tracker_path=Path("examples/sample_remediation_tracker_closed.csv"),
                signoffs_path=Path("examples/sample_owner_signoffs_approved.csv"),
                move_lab_capture_validation_path=write_capture_validation(Path(tmp), status="pass"),
                move_lab_proof_path=write_move_lab_validation(Path(tmp), scope="approved_lab_move_appliance", status="pass"),
                move_lab_evidence_intake_path=write_move_lab_evidence_intake(Path(tmp), status="pass"),
            )

            summary = output.read_text(encoding="utf-8")
            self.assertIn("| Source endpoint evidence request | pass |", summary)
            self.assertIn("| Move lab evidence request | pass |", summary)
            self.assertIn("| Target capacity fit | pass |", summary)
            self.assertIn("| Target reconciliation | warn |", summary)
            self.assertIn("| Source network validation | pass |", summary)
            self.assertIn("held source workload name already exists", summary)
            self.assertIn("| Final remediation closure | pass |", summary)
            self.assertIn("| Move lab capture kit | pass |", summary)
            self.assertIn("| Move lab closure checklist | pass |", summary)
            self.assertIn("| Approved Move lab proof | pass |", summary)
            self.assertIn("| Move lab evidence intake | pass |", summary)

            result = validate_operator_gate_summary(output)

            self.assertTrue(result.ok, result.errors)

    def test_operator_gate_summary_rejects_tampered_move_lab_closure_checklist(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            checklist_path = out_dir / "move-lab-closure-checklist.md"
            checklist_path.write_text(
                checklist_path.read_text(encoding="utf-8").replace("## Stop Conditions", "## Closeout Notes"),
                encoding="utf-8",
            )

            output = write_operator_gate_summary(out_dir)

            summary = output.read_text(encoding="utf-8")
            self.assertIn("| Move lab closure checklist | fail |", summary)
            self.assertIn("Move lab closure checklist missing required section: ## Stop Conditions", summary)

    def test_operator_gate_summary_rejects_tampered_source_endpoint_request(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            request_path = out_dir / "source-endpoint-evidence-request.md"
            request_path.write_text(
                request_path.read_text(encoding="utf-8").replace("mutating_calls=0", "mutating_calls=unknown"),
                encoding="utf-8",
            )

            output = write_operator_gate_summary(out_dir)

            summary = output.read_text(encoding="utf-8")
            self.assertIn("| Source endpoint evidence request | fail |", summary)
            self.assertIn("Source endpoint evidence request missing required proof request reference: mutating_calls=0", summary)

    def test_validate_operator_gate_summary_rejects_missing_request_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            output = write_operator_gate_summary(out_dir)
            text = "\n".join(
                line
                for line in output.read_text(encoding="utf-8").splitlines()
                if not line.startswith("| Move lab evidence request |")
            )
            output.write_text(text, encoding="utf-8")

            result = validate_operator_gate_summary(output)

        self.assertFalse(result.ok)
        self.assertTrue(any("Move lab evidence request" in error for error in result.errors))

    def test_cli_summarize_gates_writes_manifested_artifact(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            with patch("sys.stdout"):
                code = main(["summarize-gates", "--dir", str(out_dir)])

            manifest = json.loads((out_dir / "evidence-manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(code, 0)
            self.assertTrue((out_dir / "operator-gate-summary.md").exists())
            self.assertTrue(any(artifact["name"] == "operator-gate-summary.md" for artifact in manifest["artifacts"]))

    def test_cli_validate_operator_gate_summary_reports_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            summary = write_operator_gate_summary(out_dir)

            with patch("sys.stdout"):
                code = main(["validate-operator-gate-summary", "--summary", str(summary)])

        self.assertEqual(code, 0)


def build_assessment(tmp_path: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments, inventory)
    out_dir = tmp_path / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


def write_move_lab_validation(tmp: Path, scope: str, status: str) -> Path:
    path = tmp / f"move-lab-proof-{scope}.json"
    checks = [{"name": "move-lab-proof-scope", "status": "pass", "detail": scope}]
    if scope == "approved_lab_move_appliance":
        checks.append({"name": "move-lab-transcript-validation-link", "status": "pass", "detail": "sha256 matched"})
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_proof_validation_v1",
                "status": status,
                "checks": checks,
                "errors": [],
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_move_lab_evidence_intake(tmp: Path, status: str) -> Path:
    path = tmp / f"move-lab-evidence-intake-{status}.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_evidence_intake_v1",
                "status": status,
                "checks": [],
                "errors": [] if status == "pass" else ["evidence intake failed"],
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_capture_validation(tmp: Path, status: str) -> Path:
    path = tmp / "move-lab-capture-kit-validation.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_move_lab_capture_kit_validation_v1",
                "status": status,
                "checks": [],
                "errors": [] if status == "pass" else ["capture kit failed"],
                "warnings": [],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


def write_vcenter_network_inventory(tmp: Path, vlans: list[str]) -> Path:
    path = tmp / "vcenter-networks.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": "nmrcp_vcenter_network_inventory_v1",
                "source": {"system": "test-vcenter", "mutating_calls": 0},
                "networks": [{"network": f"VLAN{vlan}", "name": f"VLAN{vlan}", "vlan": vlan} for vlan in vlans],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return path


if __name__ == "__main__":
    unittest.main()
