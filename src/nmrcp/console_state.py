from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from . import __version__
from .connectors import connector_capability_catalog


CONSOLE_STATE_SCHEMA_VERSION = "nmrcp_console_state_v1"
CONSOLE_STATE_FILE = "console-state.json"


def initial_console_state() -> dict[str, Any]:
    return {
        "schema_version": CONSOLE_STATE_SCHEMA_VERSION,
        "product_version": __version__,
        "generated_at": utc_now(),
        "updated_at": utc_now(),
        "credential_policy": {
            "credentials_persisted": False,
            "endpoint_values_persisted": False,
            "raw_inventory_persisted_in_state": False,
        },
        "connector_capabilities": connector_capability_catalog(),
        "environment_profiles": {},
        "run_history": [],
        "evidence_index": [],
    }


def load_console_state(data_dir: Path) -> dict[str, Any]:
    path = state_path(data_dir)
    if not path.exists():
        return initial_console_state()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return initial_console_state()
    if not isinstance(state, dict) or state.get("schema_version") != CONSOLE_STATE_SCHEMA_VERSION:
        return initial_console_state()
    state.setdefault("connector_capabilities", connector_capability_catalog())
    state.setdefault("environment_profiles", {})
    state.setdefault("run_history", [])
    state.setdefault("evidence_index", [])
    return state


def write_console_state(data_dir: Path, state: dict[str, Any]) -> Path:
    data_dir.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = utc_now()
    path = state_path(data_dir)
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return path


def ensure_console_state(data_dir: Path) -> Path:
    state = load_console_state(data_dir)
    return write_console_state(data_dir, state)


def record_console_event(
    data_dir: Path,
    action: str,
    status: str,
    *,
    request: dict[str, Any] | None = None,
    response: dict[str, Any] | None = None,
) -> dict[str, Any]:
    state = load_console_state(data_dir)
    event = {
        "at": utc_now(),
        "action": action,
        "status": status,
        "request": summarize_request(request or {}),
        "response": summarize_response(response or {}),
    }
    history = state.setdefault("run_history", [])
    if isinstance(history, list):
        history.append(event)
        del history[:-50]
    update_environment_profiles(state, action, request or {}, response or {})
    update_evidence_index(state, data_dir, response or {})
    write_console_state(data_dir, state)
    return event


def summarize_request(request: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {}
    for key, value in request.items():
        if key in {"vcenter", "prism"} and isinstance(value, dict):
            summary[key] = summarize_endpoint_request(value)
        elif key == "gates" and isinstance(value, dict):
            summary[key] = sorted(gate for gate, supplied in value.items() if bool(supplied))
        elif key.lower() in {"password", "credential", "token", "secret", "authorization"}:
            summary[key] = "[request-only]"
        else:
            summary[key] = value
    return summary


def summarize_endpoint_request(value: dict[str, Any]) -> dict[str, Any]:
    configured = bool(value.get("endpoint") or value.get("base_url") or value.get("username") or value.get("password") or value.get("credential"))
    return {
        "configured": configured,
        "endpoint_value_persisted": False,
        "username_persisted": False,
        "credential_persisted": False,
        "tls_verification": bool(value.get("verify_tls", True)),
        "timeout_seconds": int(value.get("timeout_seconds") or 20),
    }


def summarize_response(response: dict[str, Any]) -> dict[str, Any]:
    summary: dict[str, Any] = {
        "schema_version": response.get("schema_version"),
        "status": response.get("status"),
    }
    for key in ("proof", "source_dir", "assessment_dir", "report", "json_report", "console"):
        if key in response:
            summary[key] = response[key]
    if isinstance(response.get("summary"), dict):
        summary["summary"] = response["summary"]
    if isinstance(response.get("missing_gates"), list):
        summary["missing_gates"] = response["missing_gates"]
    return summary


def update_environment_profiles(state: dict[str, Any], action: str, request: dict[str, Any], response: dict[str, Any]) -> None:
    profiles = state.setdefault("environment_profiles", {})
    if not isinstance(profiles, dict):
        return
    if action == "environment-access":
        environment = str(response.get("environment") or request.get("environment") or "dev")
        target = str(response.get("target") or request.get("target") or "pc")
        key = f"{environment}:{target}"
        profiles[key] = {
            "environment": environment,
            "target": target,
            "target_label": response.get("target_label"),
            "last_mode": response.get("mode") or request.get("mode"),
            "last_status": response.get("status"),
            "missing_gates": response.get("missing_gates") or [],
            "updated_at": utc_now(),
        }
    for connector_id in ("vcenter", "prism"):
        endpoint = request.get(connector_id)
        if isinstance(endpoint, dict) and any(endpoint.values()):
            profiles[connector_id] = {
                "connector": connector_id,
                "configured": True,
                "endpoint_value_persisted": False,
                "username_persisted": False,
                "credential_persisted": False,
                "tls_verification": endpoint_tls_mode_from_request(endpoint),
                "timeout_seconds": int(endpoint.get("timeout_seconds") or 20),
                "last_action": action,
                "last_status": response.get("status"),
                "updated_at": utc_now(),
            }


def endpoint_tls_mode_from_request(value: dict[str, Any]) -> str:
    endpoint = str(value.get("endpoint") or value.get("base_url") or "")
    if endpoint.startswith("http://127.0.0.1") or endpoint.startswith("http://localhost"):
        return "loopback_http"
    if not endpoint:
        return "not_configured"
    return "enabled" if bool(value.get("verify_tls", True)) else "disabled"


def update_evidence_index(state: dict[str, Any], data_dir: Path, response: dict[str, Any]) -> None:
    index = state.setdefault("evidence_index", [])
    if not isinstance(index, list):
        return
    for key in ("proof", "source_dir", "assessment_dir", "report", "json_report"):
        value = response.get(key)
        if not value:
            continue
        path = Path(str(value))
        try:
            display_path = str(path.relative_to(data_dir)) if path.is_absolute() else str(path)
        except ValueError:
            display_path = str(path)
        entry = {
            "role": key,
            "path": display_path,
            "recorded_at": utc_now(),
        }
        if entry["path"] not in {item.get("path") for item in index if isinstance(item, dict)}:
            index.append(entry)
    del index[:-100]


def state_path(data_dir: Path) -> Path:
    return data_dir / CONSOLE_STATE_FILE


def utc_now() -> str:
    return datetime.now(UTC).isoformat()
