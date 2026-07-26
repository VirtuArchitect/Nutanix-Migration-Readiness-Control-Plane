import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nmrcp.cli import main
from nmrcp.connectors import EndpointConfig
from nmrcp.live_readiness import run_live_readiness


class LiveReadinessTests(unittest.TestCase):
    def test_missing_optional_endpoints_warn_without_secrets(self):
        result = run_live_readiness()

        self.assertEqual(result["status"], "warn")
        self.assertFalse(result["security"]["credentials_serialized"])
        self.assertTrue(all(check["configured"] is False for check in result["checks"]))

    def test_required_missing_endpoint_fails_closed(self):
        result = run_live_readiness(require_vcenter=True)

        self.assertEqual(result["status"], "fail")
        vcenter = next(check for check in result["checks"] if check["name"] == "vcenter")
        self.assertEqual(vcenter["status"], "fail")

    def test_configured_endpoints_report_read_only_counts(self):
        class FakeVCenter:
            def __init__(self, config):
                self.config = config

            def login(self):
                return "session-id"

            def list_vms(self):
                return [{"vm": "vm-1"}, {"vm": "vm-2"}]

        class FakePrism:
            def __init__(self, config):
                self.config = config

            def list_clusters(self, page_size=100):
                return [{"metadata": {"uuid": "cluster-1"}}]

            def list_vms(self, page_size=100, max_pages=1):
                return [{"metadata": {"uuid": "vm-1"}}]

        with patch("nmrcp.live_readiness.VCenterClient", FakeVCenter), patch(
            "nmrcp.live_readiness.PrismCentralClient", FakePrism
        ):
            result = run_live_readiness(
                vcenter_config=EndpointConfig("https://vcenter.example.test", "admin", "super-secret"),
                prism_config=EndpointConfig("https://prism.example.test:9440", "admin", "super-secret"),
            )

        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["security"]["tls_verification"]["vcenter"], "enabled")
        self.assertEqual(result["security"]["tls_verification"]["prism-central"], "enabled")
        self.assertTrue(all(check["tls_verification"] == "enabled" for check in result["checks"]))
        serialized = json.dumps(result)
        self.assertNotIn("super-secret", serialized)
        self.assertNotIn("vcenter.example.test", serialized)
        self.assertNotIn("prism.example.test", serialized)
        self.assertIn("/api/vcenter/vm", serialized)

    def test_configured_insecure_endpoint_reports_disabled_tls_without_endpoint(self):
        class FakeVCenter:
            def __init__(self, config):
                self.config = config

            def login(self):
                return "session-id"

            def list_vms(self):
                return [{"vm": "vm-1"}]

        with patch("nmrcp.live_readiness.VCenterClient", FakeVCenter):
            result = run_live_readiness(
                vcenter_config=EndpointConfig("https://vcenter.example.test", "admin", "super-secret", verify_tls=False)
            )

        vcenter = next(check for check in result["checks"] if check["name"] == "vcenter")
        serialized = json.dumps(result)
        self.assertEqual(vcenter["tls_verification"], "disabled")
        self.assertEqual(result["security"]["tls_verification"]["vcenter"], "disabled")
        self.assertNotIn("vcenter.example.test", serialized)

    def test_cli_live_readiness_writes_redacted_json(self):
        class FakeVCenter:
            def __init__(self, config):
                self.config = config

            def login(self):
                return "session-id"

            def list_vms(self):
                return [{"vm": "vm-1"}]

        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "live-readiness.json"
            with patch("nmrcp.live_readiness.VCenterClient", FakeVCenter), patch.dict(
                "os.environ",
                {
                    "NMRCP_VCENTER_URL": "https://vcenter.example.test",
                    "NMRCP_VCENTER_USERNAME": "administrator",
                    "NMRCP_VCENTER_PASSWORD": "super-secret",
                    "NMRCP_PRISM_URL": "",
                    "NMRCP_PRISM_USERNAME": "",
                    "NMRCP_PRISM_PASSWORD": "",
                },
                clear=False,
            ):
                code = main(["live-readiness", "--out", str(out)])

            payload = out.read_text(encoding="utf-8")
            self.assertEqual(code, 0)
            self.assertIn("nmrcp_live_readiness_v1", payload)
            self.assertNotIn("super-secret", payload)
            self.assertNotIn("administrator", payload)
            self.assertNotIn("vcenter.example.test", payload)

    def test_cli_live_readiness_rejects_cleartext_remote_endpoint_without_traceback(self):
        with patch.dict(
            "os.environ",
            {
                "NMRCP_VCENTER_URL": "http://vcenter.example.test",
                "NMRCP_VCENTER_USERNAME": "administrator",
                "NMRCP_VCENTER_PASSWORD": "super-secret",
            },
            clear=False,
        ):
            with self.assertRaises(SystemExit) as raised:
                main(["live-readiness"])

        self.assertIn("HTTPS", str(raised.exception))
        self.assertNotIn("super-secret", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
