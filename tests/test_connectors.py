import unittest
from unittest.mock import patch

from nmrcp.connectors import EndpointConfig, PrismCentralClient, ReadOnlyHttpClient, VCenterClient, endpoint_tls_mode


class ConnectorSafetyTests(unittest.TestCase):
    def test_endpoint_config_requires_https_except_loopback_http(self):
        EndpointConfig("https://vcenter.example.test", "user", "pass")
        EndpointConfig("http://127.0.0.1:8080", "user", "pass")
        EndpointConfig("http://localhost:8080", "user", "pass")

        with self.assertRaises(ValueError):
            EndpointConfig("http://vcenter.example.test", "user", "pass")

    def test_endpoint_config_rejects_nonpositive_timeout(self):
        with self.assertRaises(ValueError):
            EndpointConfig("https://vcenter.example.test", "user", "pass", timeout_seconds=0)

    def test_endpoint_tls_mode_is_redacted_and_reviewable(self):
        self.assertEqual(endpoint_tls_mode(None), "not_configured")
        self.assertEqual(endpoint_tls_mode(EndpointConfig("https://vcenter.example.test", "user", "pass")), "enabled")
        self.assertEqual(
            endpoint_tls_mode(EndpointConfig("https://vcenter.example.test", "user", "pass", verify_tls=False)),
            "disabled",
        )
        self.assertEqual(endpoint_tls_mode(EndpointConfig("http://127.0.0.1:8080", "user", "pass")), "loopback_http")

    def test_post_is_limited_to_read_only_session_and_list_paths(self):
        client = ReadOnlyHttpClient(EndpointConfig("https://example.test", "user", "pass"))

        with self.assertRaises(ValueError):
            client.post_json("/api/nutanix/v3/vms", {"spec": {"name": "mutating"}})

    def test_http_request_uses_expected_method_url_headers_and_payload(self):
        captured = {}

        def fake_urlopen(request, timeout, context):
            captured["method"] = request.get_method()
            captured["url"] = request.full_url
            captured["headers"] = dict(request.header_items())
            captured["data"] = request.data
            captured["timeout"] = timeout
            captured["context"] = context
            return FakeResponse(b'{"entities": []}')

        client = ReadOnlyHttpClient(
            EndpointConfig("https://pc.example.test:9440/", "admin", "secret", verify_tls=False, timeout_seconds=7)
        )

        with patch("nmrcp.connectors.urlopen", fake_urlopen):
            response = client.post_json("/api/nutanix/v3/vms/list", {"kind": "vm", "offset": 0, "length": 10})

        self.assertEqual(response, {"entities": []})
        self.assertEqual(captured["method"], "POST")
        self.assertEqual(captured["url"], "https://pc.example.test:9440/api/nutanix/v3/vms/list")
        self.assertEqual(captured["timeout"], 7)
        self.assertEqual(captured["data"], b'{"kind": "vm", "offset": 0, "length": 10}')
        self.assertEqual(captured["headers"]["Accept"], "application/json")
        self.assertEqual(captured["headers"]["Content-type"], "application/json")
        self.assertIn("Basic ", captured["headers"]["Authorization"])

    def test_vcenter_client_reuses_session_for_read_only_gets(self):
        http = RecordingHttp(
            post_responses=[{"value": "session-123"}],
            request_responses=[
                {"value": [{"vm": "vm-1"}]},
                {"value": {"name": "vm-one"}},
                {"value": [{"network": "network-1", "name": "VM Network"}]},
            ],
        )
        client = VCenterClient(EndpointConfig("https://vcsa.example.test", "admin", "secret"))
        client.http = http

        vms = client.list_vms()
        details = client.get_vm_details("vm-1")
        networks = client.list_networks()

        self.assertEqual(vms, [{"vm": "vm-1"}])
        self.assertEqual(details, {"name": "vm-one"})
        self.assertEqual(networks, [{"network": "network-1", "name": "VM Network"}])
        self.assertEqual(http.post_calls, [("/api/session", {})])
        self.assertEqual(
            http.request_calls,
            [
                ("GET", "/api/vcenter/vm", {"vmware-api-session-id": "session-123"}),
                ("GET", "/api/vcenter/vm/vm-1", {"vmware-api-session-id": "session-123"}),
                ("GET", "/api/vcenter/network", {"vmware-api-session-id": "session-123"}),
            ],
        )

    def test_prism_client_paginates_vm_list_with_read_only_payloads(self):
        http = RecordingHttp(
            post_responses=[
                {
                    "entities": [{"metadata": {"uuid": "vm-1"}}],
                    "metadata": {"total_matches": 3},
                },
                {
                    "entities": [{"metadata": {"uuid": "vm-2"}}, {"metadata": {"uuid": "vm-3"}}],
                    "metadata": {"total_matches": 3},
                },
            ],
        )
        client = PrismCentralClient(EndpointConfig("https://pc.example.test:9440", "admin", "secret"))
        client.http = http

        vms = client.list_vms(page_size=2, max_pages=3)

        self.assertEqual([vm["metadata"]["uuid"] for vm in vms], ["vm-1", "vm-2", "vm-3"])
        self.assertEqual(
            http.post_calls,
            [
                ("/api/nutanix/v3/vms/list", {"kind": "vm", "offset": 0, "length": 2}),
                ("/api/nutanix/v3/vms/list", {"kind": "vm", "offset": 2, "length": 2}),
            ],
        )


class FakeResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


class RecordingHttp:
    def __init__(
        self,
        post_responses: list[dict] | None = None,
        request_responses: list[dict] | None = None,
    ):
        self.post_responses = list(post_responses or [])
        self.request_responses = list(request_responses or [])
        self.post_calls = []
        self.request_calls = []

    def post_json(self, path, payload=None):
        self.post_calls.append((path, payload or {}))
        return self.post_responses.pop(0)

    def request_json(self, method, path, payload=None, headers=None):
        self.request_calls.append((method, path, headers or {}))
        return self.request_responses.pop(0)


if __name__ == "__main__":
    unittest.main()
