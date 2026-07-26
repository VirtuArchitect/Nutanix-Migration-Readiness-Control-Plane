from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .connectors import EndpointConfig, PrismCentralClient, VCenterClient, endpoint_tls_mode


def run_live_readiness(
    vcenter_config: EndpointConfig | None = None,
    prism_config: EndpointConfig | None = None,
    require_vcenter: bool = False,
    require_prism: bool = False,
    prism_page_size: int = 100,
    prism_max_pages: int = 1,
) -> dict[str, Any]:
    checks = [
        check_vcenter(vcenter_config, require=require_vcenter),
        check_prism(
            prism_config,
            require=require_prism,
            page_size=prism_page_size,
            max_pages=prism_max_pages,
        ),
    ]
    status = "pass"
    if any(check["status"] == "fail" for check in checks):
        status = "fail"
    elif any(check["status"] == "warn" for check in checks):
        status = "warn"
    return {
        "schema_version": "nmrcp_live_readiness_v1",
        "generated_at": datetime.now(UTC).isoformat(),
        "status": status,
        "checks": checks,
        "security": {
            "mode": "read-only",
            "credentials_serialized": False,
            "endpoint_values_serialized": False,
            "mutation_allowed": False,
            "tls_verification": {
                "vcenter": endpoint_tls_mode(vcenter_config),
                "prism-central": endpoint_tls_mode(prism_config),
            },
        },
    }


def check_vcenter(config: EndpointConfig | None, require: bool = False) -> dict[str, Any]:
    if config is None:
        return missing_check("vcenter", require)
    try:
        client = VCenterClient(config)
        session_id = client.login()
        vms = client.list_vms()
        return {
            "name": "vcenter",
            "status": "pass",
            "configured": True,
            "authenticated": bool(session_id),
            "tls_verification": endpoint_tls_mode(config),
            "read_only_calls": ["/api/session", "/api/vcenter/vm"],
            "counts": {"vms": len(vms)},
        }
    except Exception as exc:  # noqa: BLE001 - intentionally sanitized for operator evidence
        return failed_check("vcenter", exc, config)


def check_prism(
    config: EndpointConfig | None,
    require: bool = False,
    page_size: int = 100,
    max_pages: int = 1,
) -> dict[str, Any]:
    if config is None:
        return missing_check("prism-central", require)
    try:
        client = PrismCentralClient(config)
        clusters = client.list_clusters(page_size=page_size)
        vms = client.list_vms(page_size=page_size, max_pages=max_pages)
        return {
            "name": "prism-central",
            "status": "pass",
            "configured": True,
            "authenticated": True,
            "tls_verification": endpoint_tls_mode(config),
            "read_only_calls": [
                "/api/nutanix/v3/clusters/list",
                "/api/nutanix/v3/vms/list",
            ],
            "counts": {"clusters": len(clusters), "vms": len(vms)},
        }
    except Exception as exc:  # noqa: BLE001 - intentionally sanitized for operator evidence
        return failed_check("prism-central", exc, config)


def missing_check(name: str, require: bool) -> dict[str, Any]:
    return {
        "name": name,
        "status": "fail" if require else "warn",
        "configured": False,
        "authenticated": False,
        "tls_verification": "not_configured",
        "read_only_calls": [],
        "counts": {},
        "detail": "required environment variables missing" if require else "environment variables not configured",
    }


def failed_check(name: str, exc: Exception, config: EndpointConfig | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "status": "fail",
        "configured": True,
        "authenticated": False,
        "tls_verification": endpoint_tls_mode(config),
        "read_only_calls": [],
        "counts": {},
        "detail": sanitized_error(exc),
    }


def sanitized_error(exc: Exception) -> str:
    message = str(exc)
    if not message:
        return exc.__class__.__name__
    blocked_tokens = ("Authorization", "Basic ", "password", "secret", "token")
    if any(token.lower() in message.lower() for token in blocked_tokens):
        return exc.__class__.__name__
    return message
