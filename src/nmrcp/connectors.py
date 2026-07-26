from __future__ import annotations

import base64
import json
import ssl
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen


READ_ONLY_POST_PATHS = {
    "/api/session",
    "/rest/com/vmware/cis/session",
    "/api/nutanix/v3/vms/list",
    "/api/nutanix/v3/clusters/list",
}


@dataclass(frozen=True)
class EndpointConfig:
    base_url: str
    username: str
    password: str
    verify_tls: bool = True
    timeout_seconds: int = 20

    def __post_init__(self) -> None:
        validate_endpoint_base_url(self.base_url)
        if self.timeout_seconds <= 0:
            raise ValueError("Endpoint timeout must be greater than zero seconds")


class ReadOnlyHttpClient:
    """Small stdlib client for explicit read-only Prism/vCenter API calls."""

    def __init__(self, config: EndpointConfig):
        self.config = config

    def get_json(self, path: str) -> dict[str, Any]:
        return self.request_json("GET", path)

    def post_json(self, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        return self.request_json("POST", path, payload=payload or {})

    def request_json(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        if method not in {"GET", "POST"}:
            raise ValueError("Read-only client only permits GET and POST list/session calls")
        normalized_path = f"/{path.lstrip('/')}"
        if method == "POST" and normalized_path not in READ_ONLY_POST_PATHS:
            raise ValueError(f"POST is not allowed for read-only path: {normalized_path}")
        url = f"{self.config.base_url.rstrip('/')}/{path.lstrip('/')}"
        token = base64.b64encode(f"{self.config.username}:{self.config.password}".encode("utf-8")).decode("ascii")
        request_headers = {
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
        }
        data = None
        if payload is not None:
            request_headers["Content-Type"] = "application/json"
            data = json.dumps(payload).encode("utf-8")
        if headers:
            request_headers.update(headers)
        request = Request(url, method=method, headers=request_headers, data=data)
        context = ssl.create_default_context() if self.config.verify_tls else ssl._create_unverified_context()
        try:
            with urlopen(request, timeout=self.config.timeout_seconds, context=context) as response:
                body = response.read().decode("utf-8")
                parsed = json.loads(body)
                return {"value": parsed} if not isinstance(parsed, dict) else parsed
        except HTTPError as exc:
            raise RuntimeError(f"Read-only API request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"Read-only API request failed: {exc.reason}") from exc


def prism_cluster_probe(config: EndpointConfig) -> dict[str, Any]:
    return ReadOnlyHttpClient(config).post_json("/api/nutanix/v3/clusters/list", {"kind": "cluster"})


def vcenter_session_probe(config: EndpointConfig) -> dict[str, Any]:
    return ReadOnlyHttpClient(config).post_json("/api/session")


def validate_endpoint_base_url(base_url: str) -> None:
    parsed = urlparse(base_url)
    if parsed.scheme == "https" and parsed.netloc:
        return
    if parsed.scheme == "http" and is_loopback_host(parsed.hostname or "") and parsed.netloc:
        return
    raise ValueError("Endpoint URL must use HTTPS; HTTP is allowed only for loopback simulator URLs")


def is_loopback_host(hostname: str) -> bool:
    return hostname.lower() in {"localhost", "127.0.0.1", "::1"}


def endpoint_tls_mode(config: EndpointConfig | None) -> str:
    if config is None:
        return "not_configured"
    parsed = urlparse(config.base_url)
    if parsed.scheme == "http" and is_loopback_host(parsed.hostname or ""):
        return "loopback_http"
    return "enabled" if config.verify_tls else "disabled"


class VCenterClient:
    def __init__(self, config: EndpointConfig):
        self.http = ReadOnlyHttpClient(config)
        self._session_id: str | None = None

    def login(self) -> str:
        response = self.http.post_json("/api/session")
        session_id = response.get("value")
        if not isinstance(session_id, str) or not session_id:
            raise RuntimeError("vCenter session response did not contain a session id")
        self._session_id = session_id
        return session_id

    def get_json(self, path: str) -> dict[str, Any]:
        if self._session_id is None:
            self.login()
        return self.http.request_json(
            "GET",
            path,
            headers={"vmware-api-session-id": self._session_id or ""},
        )

    def list_vms(self) -> list[dict[str, Any]]:
        response = self.get_json("/api/vcenter/vm")
        value = response.get("value", [])
        if not isinstance(value, list):
            raise RuntimeError("vCenter VM list response did not contain a list value")
        return [item for item in value if isinstance(item, dict)]

    def list_networks(self) -> list[dict[str, Any]]:
        response = self.get_json("/api/vcenter/network")
        value = response.get("value", [])
        if not isinstance(value, list):
            raise RuntimeError("vCenter network list response did not contain a list value")
        return [item for item in value if isinstance(item, dict)]

    def get_vm_details(self, vm_id: str) -> dict[str, Any]:
        response = self.get_json(f"/api/vcenter/vm/{vm_id}")
        value = response.get("value", {})
        return value if isinstance(value, dict) else {}


class PrismCentralClient:
    def __init__(self, config: EndpointConfig):
        self.http = ReadOnlyHttpClient(config)

    def list_clusters(self, page_size: int = 100) -> list[dict[str, Any]]:
        response = self.http.post_json(
            "/api/nutanix/v3/clusters/list",
            {"kind": "cluster", "offset": 0, "length": page_size},
        )
        entities = response.get("entities", [])
        if not isinstance(entities, list):
            raise RuntimeError("Prism Central cluster list response did not contain entities")
        return [item for item in entities if isinstance(item, dict)]

    def list_vms(self, page_size: int = 500, max_pages: int = 20) -> list[dict[str, Any]]:
        entities: list[dict[str, Any]] = []
        offset = 0
        for _page in range(max_pages):
            response = self.http.post_json(
                "/api/nutanix/v3/vms/list",
                {"kind": "vm", "offset": offset, "length": page_size},
            )
            page_entities = response.get("entities", [])
            if not isinstance(page_entities, list):
                raise RuntimeError("Prism Central VM list response did not contain entities")
            entities.extend(item for item in page_entities if isinstance(item, dict))
            metadata = response.get("metadata", {})
            total = metadata.get("total_matches") if isinstance(metadata, dict) else None
            offset += page_size
            if not page_entities or (isinstance(total, int) and offset >= total):
                break
        return entities
