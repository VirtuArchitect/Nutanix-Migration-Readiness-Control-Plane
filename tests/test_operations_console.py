import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp import __version__
from nmrcp.cli import main
from nmrcp.evidence import write_assessment
from nmrcp.operations_console import validate_operations_console
from nmrcp.scoring import assess_inventory
from nmrcp.waves import plan_waves


class OperationsConsoleTests(unittest.TestCase):
    def test_generated_operations_console_passes_contract(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            result = validate_operations_console(out_dir / "operations-console.html", out_dir / "assessment.json")
            console = (out_dir / "operations-console.html").read_text(encoding="utf-8")

            self.assertTrue(result.ok, result.errors)
            self.assertIn("PASS", result.summary())
            self.assertIn("NMRCP", console)
            self.assertIn("MRCP", console)
            self.assertIn(f"Version {__version__}", console)
            self.assertIn("Migration Readiness Control Plane", console)
            self.assertIn("Nutanix Provider Edition", console)
            self.assertIn("Provider Pair", console)
            self.assertIn("VMware vCenter -&gt; Nutanix AHV", console)
            self.assertIn("Independent migration readiness console", console)
            self.assertIn("Write intent is gated, not executed", console)
            self.assertIn("brand-mark", console)
            self.assertIn('rel="icon"', console)
            self.assertIn("NMRCP logo favicon", console)
            self.assertIn("data:image/svg+xml", console)
            self.assertIn("ops-ribbon", console)
            self.assertIn("provider-band", console)
            self.assertIn('data-page-link="dashboard"', console)
            self.assertIn('aria-label="Open Operations Dashboard"', console)
            self.assertIn('id="page-connect"', console)
            self.assertIn('id="page-settings"', console)
            self.assertIn("function showPage", console)
            self.assertIn("function embeddedJson", console)
            self.assertIn("Add Connector", console)
            self.assertIn("Edit Connector", console)
            self.assertIn("Delete Connector", console)
            self.assertIn("Test Connectivity", console)
            self.assertIn("Test Selected Connector", console)
            self.assertIn("Connectivity test result", console)
            self.assertIn("result-badge", console)
            self.assertIn("PASS", console)
            self.assertIn("FAILED", console)
            self.assertIn("Operator Summary", console)
            self.assertIn("Next step", console)
            self.assertIn("No infrastructure changes were made.", console)
            self.assertIn("function renderOperatorSummary", console)
            self.assertIn("function showProofSummary", console)
            self.assertIn("function showErrorSummary", console)
            self.assertIn("Action failed", console)
            self.assertIn("Dry Run Ready For Review", console)
            self.assertIn("function setStatusBadge", console)
            self.assertIn("Browser-only preflight", console)
            self.assertIn("Add User", console)
            self.assertIn("Edit User", console)
            self.assertIn("Delete User", console)
            self.assertIn("Add Role", console)
            self.assertIn("Create Migration Plan", console)
            self.assertIn("Edit Plan", console)
            self.assertIn("Delete Plan", console)
            self.assertIn("Run Dry Run", console)
            self.assertIn("managedConnectors", console)
            self.assertIn("testConnectionId", console)
            self.assertIn("connectionTestRequest", console)
            self.assertIn("skip_unconfigured_optional", console)
            self.assertIn("nmrcp_connector_preflight_v1", console)
            self.assertIn("managedUsers", console)
            self.assertIn("managedRoles", console)
            self.assertIn("managedPlans", console)
            self.assertIn("nmrcp_console_dry_run_v1", console)
            self.assertIn("Connect Environments", console)
            self.assertIn("vCenter", console)
            self.assertIn("Prism Central", console)
            self.assertIn("Prism Element", console)
            self.assertIn("ESXi", console)
            self.assertIn("Nutanix Move", console)
            self.assertIn("Environment Gates", console)
            self.assertIn("Validate Environment Gates", console)
            self.assertIn("/api/environment-access", console)
            self.assertIn("Prepare Tester Report", console)
            self.assertIn("/api/tester-report", console)
            self.assertIn("Refresh Local State", console)
            self.assertIn("/api/state", console)
            self.assertIn("Local state summary", console)
            self.assertIn("require_prism_element", console)
            self.assertIn("Run Compatibility Analysis", console)
            self.assertIn("Build Move Plan", console)
            self.assertIn("Configure", console)
            self.assertIn("Expected output", console)
            self.assertIn("Open Environment Gates", console)
            self.assertIn("Open Connectors", console)
            self.assertIn("Open Migration Plans", console)
            self.assertIn("Operations Dashboard", console)
            self.assertIn("Environment Profiles", console)
            self.assertIn("Connector Policies", console)
            self.assertIn("Settings", console)
            self.assertIn("Users &amp; RBAC", console)
            self.assertIn("Audit &amp; State", console)
            self.assertIn("Local Operator", console)
            self.assertIn("Migration Operator", console)
            self.assertIn("Security Reviewer", console)
            self.assertIn("Credential Policy", console)
            self.assertIn("Retention", console)
            self.assertIn("console-state.json", console)
            self.assertIn("Do not store credentials", console)
            self.assertIn("body {\n      margin: 0;\n      font-family: Arial, Helvetica, sans-serif;\n      font-size: 14px;", console)
            self.assertIn("#run-command", console)
            self.assertIn('font-family: Consolas, "Liberation Mono", monospace;', console)
            self.assertIn(".steps strong", console)
            self.assertIn("font-size: 12.5px;", console)

    def test_operations_console_rejects_missing_move_connection(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            console = out_dir / "operations-console.html"
            console.write_text(console.read_text(encoding="utf-8").replace("Nutanix Move", "Move removed"), encoding="utf-8")

            result = validate_operations_console(console, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("Nutanix Move" in error for error in result.errors))

    def test_operations_console_rejects_tampered_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))
            console = out_dir / "operations-console.html"
            console.write_text(
                console.read_text(encoding="utf-8").replace(
                    '<div class="metric"><strong>3</strong><span>Workloads</span></div>',
                    '<div class="metric"><strong>1</strong><span>Workloads</span></div>',
                ),
                encoding="utf-8",
            )

            result = validate_operations_console(console, out_dir / "assessment.json")

            self.assertFalse(result.ok)
            self.assertTrue(any("Workloads" in error or "summary total expected 3" in error for error in result.errors))

    def test_cli_validate_operations_console(self):
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = build_assessment(Path(tmp))

            with patch("sys.stdout"):
                code = main(
                    [
                        "validate-operations-console",
                        "--console",
                        str(out_dir / "operations-console.html"),
                        "--assessment",
                        str(out_dir / "assessment.json"),
                    ]
                )

            self.assertEqual(code, 0)


def build_assessment(tmp: Path) -> Path:
    inventory = json.loads(Path("examples/sample_inventory.json").read_text(encoding="utf-8"))
    assessments = assess_inventory(inventory)
    waves = plan_waves(assessments)
    out_dir = tmp / "assessment"
    write_assessment(inventory, assessments, waves, out_dir)
    return out_dir


if __name__ == "__main__":
    unittest.main()
