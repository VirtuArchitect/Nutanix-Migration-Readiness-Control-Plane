from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .move_lab_capture_kit import validate_move_lab_capture_kit_validation_file
from .move_lab_closure_checklist import validate_move_lab_closure_checklist
from .move_lab_evidence_intake import MOVE_LAB_EVIDENCE_PREFLIGHT_SCHEMA_VERSION
from .move_lab_evidence_request import validate_move_lab_evidence_request
from .move_lab_runbook import validate_move_lab_runbook
from .move_submit_readiness import validate_move_submit_readiness
from .redaction_review import scan_text


MOVE_LAB_READINESS_PACKET_SCHEMA_VERSION = "nmrcp_move_lab_readiness_packet_v1"

REQUIRED_ARTIFACT_ROLES = (
    "payload",
    "review",
    "move_submit_readiness",
    "capture_kit_template",
    "capture_kit_checklist",
    "capture_kit_validation",
    "evidence_preflight",
    "evidence_preflight_report",
    "runbook",
    "evidence_request",
    "closure_checklist",
)

REQUIRED_PACKET_FLAGS = {
    "not_external_proof": True,
    "requires_approved_lab_capture": True,
    "lab_only": True,
    "redacted_evidence_only": True,
}


@dataclass(frozen=True)
class MoveLabReadinessPacketResult:
    status: str
    checks: tuple[dict[str, str], ...]
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={len(self.checks)}, errors={len(self.errors)}, warnings={len(self.warnings)}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": MOVE_LAB_READINESS_PACKET_SCHEMA_VERSION,
            "status": self.status,
            "checks": list(self.checks),
            "errors": list(self.errors),
            "warnings": list(self.warnings),
        }


def write_move_lab_readiness_packet(
    *,
    payload_path: Path,
    review_path: Path,
    move_submit_readiness_path: Path,
    capture_kit_dir: Path,
    capture_kit_validation_path: Path,
    evidence_preflight_path: Path,
    evidence_preflight_report_path: Path,
    runbook_path: Path,
    evidence_request_path: Path,
    closure_checklist_path: Path,
    out_path: Path,
    report_path: Path | None = None,
    lab_ack_env: str = "NMRCP_MOVE_LAB_ACK",
) -> MoveLabReadinessPacketResult:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    artifacts = [
        artifact("payload", payload_path),
        artifact("review", review_path),
        artifact("move_submit_readiness", move_submit_readiness_path),
        artifact("capture_kit_template", capture_kit_dir / "move-lab-transcript.template.json"),
        artifact("capture_kit_checklist", capture_kit_dir / "move-lab-capture-checklist.md"),
        artifact("capture_kit_validation", capture_kit_validation_path),
        artifact("evidence_preflight", evidence_preflight_path),
        artifact("evidence_preflight_report", evidence_preflight_report_path),
        artifact("runbook", runbook_path),
        artifact("evidence_request", evidence_request_path),
        artifact("closure_checklist", closure_checklist_path),
    ]

    for item in artifacts:
        exists = item["state"] == "present"
        add_check(checks, f"artifact-{item['role']}", exists, item["path"])
        if not exists:
            errors.append(f"Move lab readiness packet missing artifact: {item['role']} at {item['path']}")

    if all(Path(item["path"]).exists() for item in artifacts):
        append_validation("move-submit-readiness", validate_move_submit_readiness(payload_path, review_path, lab_ack_env=lab_ack_env), checks, errors, warnings)
        append_validation("capture-kit-validation", validate_move_lab_capture_kit_validation_file(capture_kit_validation_path), checks, errors, warnings)
        append_validation("runbook", validate_move_lab_runbook(runbook_path), checks, errors, warnings)
        append_validation("evidence-request", validate_move_lab_evidence_request(evidence_request_path), checks, errors, warnings)
        append_validation("closure-checklist", validate_move_lab_closure_checklist(closure_checklist_path), checks, errors, warnings)
        validate_stored_submit_readiness(move_submit_readiness_path, checks, errors, warnings)
        validate_evidence_preflight_file(evidence_preflight_path, checks, errors, warnings)
        validate_report_text(evidence_preflight_report_path, checks, errors)
        validate_redaction(artifacts, checks, errors)

    packet = {
        "schema_version": MOVE_LAB_READINESS_PACKET_SCHEMA_VERSION,
        "status": "fail" if errors else "warn" if warnings else "pass",
        "purpose": "Move lab operator readiness packet for the approved non-production evidence window.",
        "flags": dict(REQUIRED_PACKET_FLAGS),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "required_closeout": [
            "validate-move-lab-transcript",
            "generate-approved-move-lab-proof",
            "validate-move-lab-proof",
            "validate-move-lab-evidence-intake",
            "mvp-audit --move-proof --move-lab-evidence-intake",
        ],
        "remaining_external_gate": "Approved non-production Nutanix Move appliance capture is still required.",
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(packet, indent=2), encoding="utf-8")

    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(packet_to_markdown(packet), encoding="utf-8")

    return MoveLabReadinessPacketResult(packet["status"], tuple(checks), tuple(errors), tuple(warnings))


def validate_move_lab_readiness_packet(packet_path: Path, *, report_path: Path | None = None) -> MoveLabReadinessPacketResult:
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []
    try:
        packet = json.loads(packet_path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        return MoveLabReadinessPacketResult("fail", (), (f"could not read Move lab readiness packet: {exc}",), ())
    except json.JSONDecodeError as exc:
        return MoveLabReadinessPacketResult("fail", (), (f"invalid Move lab readiness packet JSON: {exc}",), ())

    schema_ok = packet.get("schema_version") == MOVE_LAB_READINESS_PACKET_SCHEMA_VERSION
    add_check(checks, "packet-schema", schema_ok, str(packet.get("schema_version") or "missing"))
    if not schema_ok:
        errors.append(f"schema_version must be {MOVE_LAB_READINESS_PACKET_SCHEMA_VERSION}")

    status_ok = packet.get("status") in {"pass", "warn"}
    add_check(checks, "packet-status", status_ok, str(packet.get("status") or "missing"))
    if not status_ok:
        errors.append("Move lab readiness packet status must be pass or warn")

    flags = packet.get("flags") if isinstance(packet.get("flags"), dict) else {}
    for name, expected in REQUIRED_PACKET_FLAGS.items():
        ok = flags.get(name) is expected
        add_check(checks, f"packet-flag-{name}", ok, str(flags.get(name)))
        if not ok:
            errors.append(f"Move lab readiness packet flag {name} must be {str(expected).lower()}")

    artifacts = packet.get("artifacts")
    if not isinstance(artifacts, list):
        errors.append("Move lab readiness packet artifacts must be a list")
        artifacts = []
    roles = {str(item.get("role")) for item in artifacts if isinstance(item, dict)}
    for role in REQUIRED_ARTIFACT_ROLES:
        ok = role in roles
        add_check(checks, f"packet-role-{role}", ok, "present" if ok else "missing")
        if not ok:
            errors.append(f"Move lab readiness packet missing artifact role: {role}")
    for item in artifacts:
        if isinstance(item, dict):
            validate_artifact_record(item, checks, errors)

    packet_errors = packet.get("errors")
    if isinstance(packet_errors, list):
        errors.extend(str(error) for error in packet_errors)
    else:
        errors.append("Move lab readiness packet errors must be a list")
    packet_warnings = packet.get("warnings")
    if isinstance(packet_warnings, list):
        warnings.extend(str(warning) for warning in packet_warnings)
    else:
        errors.append("Move lab readiness packet warnings must be a list")

    closeout = packet.get("required_closeout")
    if isinstance(closeout, list):
        for command in ("generate-approved-move-lab-proof", "validate-move-lab-evidence-intake"):
            ok = command in closeout
            add_check(checks, f"packet-closeout-{command}", ok, "present" if ok else "missing")
            if not ok:
                errors.append(f"Move lab readiness packet missing closeout command: {command}")
    else:
        errors.append("Move lab readiness packet required_closeout must be a list")

    if report_path:
        validate_packet_report(report_path, packet, checks, errors)

    status = "fail" if errors else "warn" if warnings else "pass"
    return MoveLabReadinessPacketResult(status, tuple(checks), tuple(errors), tuple(warnings))


def artifact(role: str, path: Path) -> dict[str, str]:
    if not path.exists():
        return {"role": role, "path": str(path), "state": "missing", "bytes": "0", "sha256": ""}
    return {
        "role": role,
        "path": str(path),
        "state": "present",
        "bytes": str(path.stat().st_size),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def append_validation(
    name: str,
    result: Any,
    checks: list[dict[str, str]],
    errors: list[str],
    warnings: list[str],
) -> None:
    ok = bool(getattr(result, "ok", False))
    summary = result.summary() if hasattr(result, "summary") else str(result)
    add_check(checks, name, ok, summary)
    errors.extend(f"{name}: {error}" for error in getattr(result, "errors", ()))
    warnings.extend(f"{name}: {warning}" for warning in getattr(result, "warnings", ()))


def validate_stored_submit_readiness(path: Path, checks: list[dict[str, str]], errors: list[str], warnings: list[str]) -> None:
    payload = read_json(path, errors, "Move submit readiness")
    if payload is None:
        return
    ok = payload.get("schema_version") == "nmrcp_move_submit_readiness_v1"
    add_check(checks, "stored-submit-readiness-schema", ok, str(payload.get("schema_version") or "missing"))
    if not ok:
        errors.append("Move submit readiness schema_version must be nmrcp_move_submit_readiness_v1")
    status_ok = payload.get("status") == "pass"
    add_check(checks, "stored-submit-readiness-status", status_ok, str(payload.get("status") or "missing"))
    if not status_ok:
        errors.append("Move submit readiness status must be pass")
    warnings.extend(str(warning) for warning in payload.get("warnings") or [])


def validate_evidence_preflight_file(path: Path, checks: list[dict[str, str]], errors: list[str], warnings: list[str]) -> None:
    payload = read_json(path, errors, "Move lab evidence preflight")
    if payload is None:
        return
    schema_ok = payload.get("schema_version") == MOVE_LAB_EVIDENCE_PREFLIGHT_SCHEMA_VERSION
    add_check(checks, "evidence-preflight-schema", schema_ok, str(payload.get("schema_version") or "missing"))
    if not schema_ok:
        errors.append(f"Move lab evidence preflight schema_version must be {MOVE_LAB_EVIDENCE_PREFLIGHT_SCHEMA_VERSION}")
    status = str(payload.get("status") or "")
    status_ok = status in {"pass", "warn"}
    add_check(checks, "evidence-preflight-status", status_ok, str(payload.get("status") or "missing"))
    if not status_ok:
        errors.append("Move lab evidence preflight status must be pass or warn")
    payload_errors = payload.get("errors")
    no_errors = isinstance(payload_errors, list) and not payload_errors
    add_check(checks, "evidence-preflight-errors", no_errors, f"errors={len(payload_errors) if isinstance(payload_errors, list) else 'invalid'}")
    if not no_errors:
        errors.append("Move lab evidence preflight must not contain errors")
    commands = payload.get("commands") if isinstance(payload.get("commands"), list) else []
    for command in ("validate-move-lab-transcript", "generate-approved-move-lab-proof", "validate-move-lab-proof", "validate-move-lab-evidence-intake"):
        ok = any(command in str(item) for item in commands)
        add_check(checks, f"evidence-preflight-command-{command}", ok, "present" if ok else "missing")
        if not ok:
            errors.append(f"Move lab evidence preflight missing command: {command}")
    warnings.extend(str(warning) for warning in payload.get("warnings") or [])


def validate_report_text(path: Path, checks: list[dict[str, str]], errors: list[str]) -> None:
    text = read_text(path, errors, "Move lab evidence preflight report")
    if not text:
        return
    for fragment in ("# Move Lab Evidence Preflight", "validate-move-lab-evidence-intake", "Required Artifacts"):
        ok = fragment in text
        add_check(checks, f"evidence-preflight-report-{fragment}", ok, "present" if ok else "missing")
        if not ok:
            errors.append(f"Move lab evidence preflight report missing fragment: {fragment}")


def validate_redaction(artifacts: list[dict[str, str]], checks: list[dict[str, str]], errors: list[str]) -> None:
    evidence_roles = {
        "move_submit_readiness",
        "capture_kit_template",
        "capture_kit_checklist",
        "capture_kit_validation",
        "evidence_preflight",
        "evidence_preflight_report",
        "runbook",
        "evidence_request",
        "closure_checklist",
    }
    for item in artifacts:
        if item["role"] not in evidence_roles:
            continue
        path = Path(item["path"])
        if path.suffix.lower() not in {".json", ".md", ".csv", ".txt", ".html"} or not path.exists():
            continue
        findings = scan_text(path.name, path.read_text(encoding="utf-8-sig"))
        ok = not findings
        add_check(checks, f"redaction-{item['role']}", ok, f"findings={len(findings)}")
        errors.extend(f"{item['role']} redaction finding: {finding}" for finding in findings)


def validate_artifact_record(item: dict[str, Any], checks: list[dict[str, str]], errors: list[str]) -> None:
    role = str(item.get("role") or "missing")
    state_ok = item.get("state") == "present"
    add_check(checks, f"packet-artifact-{role}-state", state_ok, str(item.get("state") or "missing"))
    if not state_ok:
        errors.append(f"Move lab readiness packet artifact {role} must be present")
    sha = str(item.get("sha256") or "")
    sha_ok = len(sha) == 64 and all(char in "0123456789abcdef" for char in sha)
    add_check(checks, f"packet-artifact-{role}-sha256", sha_ok, "valid" if sha_ok else "invalid")
    if not sha_ok:
        errors.append(f"Move lab readiness packet artifact {role} must include a valid sha256")
    size_text = str(item.get("bytes") or "")
    size_ok = size_text.isdigit() and int(size_text) > 0
    add_check(checks, f"packet-artifact-{role}-bytes", size_ok, size_text or "missing")
    if not size_ok:
        errors.append(f"Move lab readiness packet artifact {role} must include positive bytes")


def validate_packet_report(path: Path, packet: dict[str, Any], checks: list[dict[str, str]], errors: list[str]) -> None:
    text = read_text(path, errors, "Move lab readiness packet report")
    if not text:
        return
    for fragment in (
        "# Move Lab Readiness Packet",
        "not external proof",
        "approved non-production Nutanix Move appliance capture",
    ):
        ok = fragment in text
        add_check(checks, f"packet-report-{fragment}", ok, "present" if ok else "missing")
        if not ok:
            errors.append(f"Move lab readiness packet report missing fragment: {fragment}")
    closeout = packet.get("required_closeout")
    if isinstance(closeout, list):
        for command in closeout:
            command_text = str(command)
            ok = f"- `{command_text}`" in text
            add_check(checks, f"packet-report-closeout-{command_text}", ok, "present" if ok else "missing")
            if not ok:
                errors.append(f"Move lab readiness packet report missing closeout command: {command_text}")
    artifacts = packet.get("artifacts")
    if isinstance(artifacts, list):
        for item in artifacts:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "")
            if not role:
                continue
            fragment = f"`{role}`"
            ok = fragment in text
            add_check(checks, f"packet-report-artifact-{role}", ok, "present" if ok else "missing")
            if not ok:
                errors.append(f"Move lab readiness packet report missing artifact role: {role}")


def packet_to_markdown(packet: dict[str, Any]) -> str:
    lines = [
        "# Move Lab Readiness Packet",
        "",
        f"- Status: `{packet['status']}`",
        "- Scope: lab-only operator readiness; not external proof.",
        "- Remaining gate: approved non-production Nutanix Move appliance capture.",
        "- Evidence policy: redacted evidence only; secrets stay local.",
        "",
        "## Artifacts",
        "",
        "| Role | State | Bytes | SHA256 | Path |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for item in packet["artifacts"]:
        lines.append(
            f"| `{item['role']}` | `{item['state']}` | `{item['bytes']}` | `{item['sha256']}` | `{escape_cell(item['path'])}` |"
        )
    lines.extend(["", "## Required Closeout", ""])
    for command in packet["required_closeout"]:
        lines.append(f"- `{command}`")
    lines.extend(["", "## Checks", "", "| Check | Status | Detail |", "| --- | --- | --- |"])
    for check in packet["checks"]:
        lines.append(f"| `{check['name']}` | `{check['status']}` | {escape_cell(check['detail'])} |")
    if packet["warnings"]:
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in packet["warnings"])
    if packet["errors"]:
        lines.extend(["", "## Errors", ""])
        lines.extend(f"- {error}" for error in packet["errors"])
    return "\n".join(lines).rstrip() + "\n"


def read_json(path: Path, errors: list[str], label: str) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except OSError as exc:
        errors.append(f"{label} could not be read: {exc}")
        return None
    except json.JSONDecodeError as exc:
        errors.append(f"{label} is invalid JSON: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return None
    return payload


def read_text(path: Path, errors: list[str], label: str) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        errors.append(f"{label} could not be read: {exc}")
        return ""


def add_check(checks: list[dict[str, str]], name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})


def escape_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", "<br>")
