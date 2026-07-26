from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .mvp_proof_bundle import MvpClosureReport, MvpProofSummary, build_mvp_closure_report, summarize_mvp_proof_package


LAUNCH_READINESS_SCHEMA_VERSION = "nmrcp_launch_readiness_report_v1"


@dataclass(frozen=True)
class LaunchReadinessReport:
    package_path: Path
    generated_at: str
    repo_url: str
    audience: str
    readiness: str
    recommendation: str
    mvp_status: str
    package_verification_status: str
    ready_for_external_handoff: bool
    external_handoff_decision: str
    external_handoff_blockers: tuple[str, ...]
    proof_roles: tuple[str, ...]
    requirements: tuple[dict[str, Any], ...]
    proof_status: dict[str, str]
    handoff_roles: tuple[str, ...]
    handoff_role_counts: dict[str, int]
    closure_summary: dict[str, Any]
    open_items: tuple[dict[str, Any], ...]
    closeout_commands: tuple[str, ...]
    residual_risks: tuple[str, ...]
    next_actions: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return self.package_verification_status == "pass" and self.readiness != "blocked"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": LAUNCH_READINESS_SCHEMA_VERSION,
            "package": str(self.package_path),
            "generated_at": self.generated_at,
            "repo_url": self.repo_url,
            "audience": self.audience,
            "readiness": self.readiness,
            "recommendation": self.recommendation,
            "mvp_status": self.mvp_status,
            "package_verification_status": self.package_verification_status,
            "ready_for_external_handoff": self.ready_for_external_handoff,
            "external_handoff_decision": self.external_handoff_decision,
            "external_handoff_blockers": list(self.external_handoff_blockers),
            "proof_roles": list(self.proof_roles),
            "requirements": list(self.requirements),
            "proof_status": self.proof_status,
            "handoff_roles": list(self.handoff_roles),
            "handoff_role_counts": dict(self.handoff_role_counts),
            "closure_summary": dict(self.closure_summary),
            "open_items": list(self.open_items),
            "closeout_commands": list(self.closeout_commands),
            "residual_risks": list(self.residual_risks),
            "next_actions": list(self.next_actions),
        }

    def to_markdown(self) -> str:
        lines = [
            "# Launch Readiness Report",
            "",
            "Know exactly what will break before you migrate from VMware to Nutanix.",
            "",
            f"- Audience: `{self.audience}`",
            f"- Repository: `{self.repo_url or 'not supplied'}`",
            f"- Readiness: `{self.readiness}`",
            f"- Recommendation: {self.recommendation}",
            f"- MVP status: `{self.mvp_status}`",
            f"- Package verification: `{self.package_verification_status}`",
            f"- Ready for external handoff: `{'yes' if self.ready_for_external_handoff else 'no'}`",
            f"- External handoff decision: `{self.external_handoff_decision}`",
            f"- Blocking open items: `{self.closure_summary.get('blocking_open_items', 0)}`",
            f"- Required evidence IDs: `{self.closure_summary.get('required_evidence_id_count', 0)}`",
            f"- Closeout command lines: `{self.closure_summary.get('closeout_command_lines', 0)}`",
            f"- Verified proof roles: `{len(self.proof_roles)}`",
            f"- Nested handoff roles: `{len(self.handoff_roles)}`",
            "",
            "## Required Evidence IDs",
            "",
        ]
        required_evidence_ids = tuple(str(item) for item in self.closure_summary.get("required_evidence_ids", ()))
        if required_evidence_ids:
            for evidence_id in required_evidence_ids:
                lines.append(f"- `{evidence_id}`")
        else:
            lines.append("- No required evidence schema IDs remain open.")
        lines.extend(
            [
                "",
                "## MVP Requirement Evidence",
                "",
                "| Requirement | Status | Notes |",
                "| --- | --- | --- |",
            ]
        )
        for requirement in self.requirements:
            notes = "; ".join(str(item) for item in requirement.get("warnings", []) or requirement.get("errors", [])) or "No open notes."
            lines.append(
                "| "
                + " | ".join(
                    [
                        f"`{requirement.get('id', 'unknown')}`",
                        f"`{requirement.get('status', 'unknown')}`",
                        escape_cell(notes),
                    ]
                )
                + " |"
            )
        lines.extend(["", "## Proof Status", "", "| Proof | Status |", "| --- | --- |"])
        for key in sorted(self.proof_status):
            lines.append(f"| `{key}` | `{self.proof_status[key]}` |")
        lines.extend(["", "## Handoff Package Roles", ""])
        if self.handoff_role_counts:
            lines.extend(["| Role | Count |", "| --- | ---: |"])
            for role, count in sorted(self.handoff_role_counts.items()):
                lines.append(f"| `{role}` | `{count}` |")
        else:
            lines.append("- No nested handoff roles were available.")
        lines.extend(["", "## Open Items", ""])
        if self.open_items:
            lines.extend(["| Area | Status | Blocking | Required Evidence | Action |", "| --- | --- | --- | --- | --- |"])
            for item in self.open_items:
                lines.append(
                    "| "
                    + " | ".join(
                        [
                            f"`{item.get('area', 'unknown')}`",
                            f"`{item.get('status', 'unknown')}`",
                            "`yes`" if item.get("blocking") else "`no`",
                            escape_cell(str(item.get("required_evidence") or "")),
                            escape_cell(str(item.get("action") or "")),
                        ]
                    )
                    + " |"
                )
        else:
            lines.append("- No open launch items were detected.")
        lines.extend(["", "## External Handoff Blockers", ""])
        if self.external_handoff_blockers:
            for blocker in self.external_handoff_blockers:
                lines.append(f"- {blocker}")
        else:
            lines.append("- No external handoff blockers detected by this launch report.")
        lines.extend(["", "## Closeout Commands", ""])
        if self.closeout_commands:
            lines.extend(["```powershell", *self.closeout_commands, "```"])
        else:
            lines.append("- No closeout commands are required by this launch report.")
        lines.extend(["", "## Next Actions", ""])
        for action in self.next_actions:
            lines.append(f"- {action}")
        lines.extend(["", "## Residual Risks", ""])
        if self.residual_risks:
            for risk in self.residual_risks:
                lines.append(f"- {risk}")
        else:
            lines.append("- No residual risks detected by the launch report.")
        lines.append("")
        return "\n".join(lines)


@dataclass(frozen=True)
class LaunchReadinessValidation:
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        status = "PASS" if self.ok else "FAIL"
        return f"{status}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def build_launch_readiness_report(
    package_path: Path,
    *,
    repo_url: str = "",
    audience: str = "partners, MSPs, migration operators, and change boards",
) -> LaunchReadinessReport:
    summary = summarize_mvp_proof_package(package_path)
    closure = build_mvp_closure_report(package_path)
    readiness = launch_readiness_status(summary, closure)
    return LaunchReadinessReport(
        package_path=package_path,
        generated_at=datetime.now(UTC).isoformat(),
        repo_url=repo_url,
        audience=audience,
        readiness=readiness,
        recommendation=launch_recommendation(readiness),
        mvp_status=summary.mvp_status,
        package_verification_status="pass" if summary.verification.ok else "fail",
        ready_for_external_handoff=closure.ready_for_external_handoff,
        external_handoff_decision=external_handoff_decision(closure),
        external_handoff_blockers=external_handoff_blockers(closure),
        proof_roles=summary.verification.roles if summary.verification.ok else (),
        requirements=tuple(summary.requirements),
        proof_status={str(key): str(value) for key, value in summary.to_dict()["proof_status"].items()},
        handoff_roles=tuple(str(role) for role in summary.to_dict().get("handoff_roles", [])),
        handoff_role_counts={str(key): int(value) for key, value in summary.to_dict().get("handoff_role_counts", {}).items()},
        closure_summary=json_compatible(closure.closure_summary),
        open_items=tuple(item.to_dict() for item in closure.open_items),
        closeout_commands=closure.closeout_commands,
        residual_risks=closure.residual_risks,
        next_actions=next_actions(summary, closure),
    )


def write_launch_readiness_report(
    package_path: Path,
    out_path: Path,
    *,
    json_out_path: Path | None = None,
    repo_url: str = "",
    audience: str = "partners, MSPs, migration operators, and change boards",
) -> LaunchReadinessReport:
    report = build_launch_readiness_report(package_path, repo_url=repo_url, audience=audience)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.to_markdown(), encoding="utf-8")
    if json_out_path:
        json_out_path.parent.mkdir(parents=True, exist_ok=True)
        json_out_path.write_text(json.dumps(report.to_dict(), indent=2), encoding="utf-8")
    return report


def validate_launch_readiness_report(
    package_path: Path,
    json_report_path: Path,
    *,
    markdown_report_path: Path | None = None,
) -> LaunchReadinessValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0

    try:
        payload = json.loads(json_report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return LaunchReadinessValidation(1, (f"Launch readiness JSON is unreadable: {exc}",), ())
    if not isinstance(payload, dict):
        return LaunchReadinessValidation(1, ("Launch readiness JSON must be an object",), ())

    checks += 1
    if payload.get("schema_version") != LAUNCH_READINESS_SCHEMA_VERSION:
        errors.append(f"Launch readiness schema_version must be {LAUNCH_READINESS_SCHEMA_VERSION}")

    repo_url = str(payload.get("repo_url") or "")
    audience = str(payload.get("audience") or "partners, MSPs, migration operators, and change boards")
    expected = build_launch_readiness_report(package_path, repo_url=repo_url, audience=audience).to_dict()
    comparable_keys = (
        "package",
        "repo_url",
        "audience",
        "readiness",
        "recommendation",
        "mvp_status",
        "package_verification_status",
        "ready_for_external_handoff",
        "external_handoff_decision",
        "external_handoff_blockers",
        "proof_roles",
        "requirements",
        "proof_status",
        "handoff_roles",
        "handoff_role_counts",
        "closure_summary",
        "open_items",
        "closeout_commands",
        "residual_risks",
        "next_actions",
    )
    for key in comparable_keys:
        checks += 1
        if key == "package":
            if not same_package_reference(payload.get(key), expected.get(key)):
                errors.append(f"Launch readiness JSON field {key} does not match current MVP proof package")
            continue
        if json_compatible(payload.get(key)) != json_compatible(expected.get(key)):
            errors.append(f"Launch readiness JSON field {key} does not match current MVP proof package")

    generated_at = str(payload.get("generated_at") or "")
    checks += 1
    if not generated_at:
        errors.append("Launch readiness JSON missing generated_at")

    if payload.get("readiness") == "ready_for_external_handoff" and payload.get("ready_for_external_handoff") is not True:
        errors.append("Launch readiness cannot be ready_for_external_handoff when ready_for_external_handoff is not true")
    if payload.get("ready_for_external_handoff") is True and payload.get("readiness") != "ready_for_external_handoff":
        errors.append("ready_for_external_handoff=true requires readiness ready_for_external_handoff")
    if payload.get("ready_for_external_handoff") is True and payload.get("external_handoff_decision") != "approved_for_external_handoff":
        errors.append("ready_for_external_handoff=true requires external_handoff_decision approved_for_external_handoff")
    if payload.get("ready_for_external_handoff") is not True and payload.get("external_handoff_decision") != "blocked_for_external_handoff":
        errors.append("ready_for_external_handoff=false requires external_handoff_decision blocked_for_external_handoff")
    blockers = payload.get("external_handoff_blockers")
    if payload.get("external_handoff_decision") == "blocked_for_external_handoff" and not blockers:
        errors.append("blocked_for_external_handoff requires external_handoff_blockers")
    if payload.get("external_handoff_decision") == "approved_for_external_handoff" and blockers:
        errors.append("approved_for_external_handoff cannot include external_handoff_blockers")
    if payload.get("readiness") == "ready_for_internal_or_partner_review":
        open_items = payload.get("open_items") if isinstance(payload.get("open_items"), list) else []
        if not any(isinstance(item, dict) and item.get("blocking") for item in open_items):
            warnings.append("Internal or partner review readiness should include at least one blocking open item")

    if markdown_report_path:
        try:
            text = markdown_report_path.read_text(encoding="utf-8")
        except OSError as exc:
            errors.append(f"Launch readiness Markdown is unreadable: {exc}")
            text = ""
        required_fragments = (
            "# Launch Readiness Report",
            "Know exactly what will break before you migrate from VMware to Nutanix.",
            "## Required Evidence IDs",
            "## MVP Requirement Evidence",
            "## Proof Status",
            "## Handoff Package Roles",
            "## Open Items",
            "## External Handoff Blockers",
            "## Closeout Commands",
            "## Next Actions",
            "## Residual Risks",
            f"- Readiness: `{payload.get('readiness')}`",
            f"- Package verification: `{payload.get('package_verification_status')}`",
            f"- Ready for external handoff: `{'yes' if payload.get('ready_for_external_handoff') else 'no'}`",
            f"- External handoff decision: `{payload.get('external_handoff_decision')}`",
            f"- Blocking open items: `{(payload.get('closure_summary') or {}).get('blocking_open_items', 0)}`",
            f"- Required evidence IDs: `{(payload.get('closure_summary') or {}).get('required_evidence_id_count', 0)}`",
            f"- Closeout command lines: `{(payload.get('closure_summary') or {}).get('closeout_command_lines', 0)}`",
            f"- Verified proof roles: `{len(payload.get('proof_roles') if isinstance(payload.get('proof_roles'), list) else [])}`",
            f"- Nested handoff roles: `{len(payload.get('handoff_roles') if isinstance(payload.get('handoff_roles'), list) else [])}`",
        )
        for fragment in required_fragments:
            checks += 1
            if fragment not in text:
                errors.append(f"Launch readiness Markdown missing required text: {fragment}")
        for evidence_id in required_evidence_ids_from_payload(payload):
            checks += 1
            fragment = f"- `{evidence_id}`"
            if fragment not in text:
                errors.append(f"Launch readiness Markdown missing required evidence ID: {evidence_id}")
        for blocker in external_handoff_blockers_from_payload(payload):
            checks += 1
            if blocker not in text:
                errors.append(f"Launch readiness Markdown missing external handoff blocker: {blocker}")
        for command in closeout_commands_from_payload(payload):
            checks += 1
            if command not in text:
                errors.append(f"Launch readiness Markdown missing closeout command line: {command}")

    return LaunchReadinessValidation(checks, tuple(errors), tuple(warnings))


def launch_readiness_status(summary: MvpProofSummary, closure: MvpClosureReport) -> str:
    if not summary.verification.ok:
        return "blocked"
    if closure.ready_for_external_handoff:
        return "ready_for_external_handoff"
    if any(item.blocking for item in closure.open_items):
        return "ready_for_internal_or_partner_review"
    return "review_ready_with_residual_risk"


def launch_recommendation(readiness: str) -> str:
    if readiness == "ready_for_external_handoff":
        return "Publish and share the verified proof package with external reviewers."
    if readiness == "ready_for_internal_or_partner_review":
        return "Share for internal or partner review, but do not claim final external handoff until approved lab Move proof is captured."
    if readiness == "review_ready_with_residual_risk":
        return "Review residual risks and confirm acceptance before external handoff."
    return "Do not publish for review until the MVP proof package verifies cleanly."


def external_handoff_decision(closure: MvpClosureReport) -> str:
    return "approved_for_external_handoff" if closure.ready_for_external_handoff else "blocked_for_external_handoff"


def external_handoff_blockers(closure: MvpClosureReport) -> tuple[str, ...]:
    blockers = [
        f"{item.area}: {item.required_evidence or item.action}"
        for item in closure.open_items
        if item.blocking
    ]
    if not blockers and not closure.ready_for_external_handoff:
        blockers.extend(str(risk) for risk in closure.residual_risks)
    return tuple(dict.fromkeys(blockers))


def next_actions(summary: MvpProofSummary, closure: MvpClosureReport) -> tuple[str, ...]:
    actions: list[str] = []
    if not summary.verification.ok:
        actions.append("Fix MVP proof package verification errors and rerun verify-mvp-proof.")
    actions.extend(str(item.action) for item in closure.open_items if item.blocking)
    if not actions and closure.residual_risks:
        actions.append("Review and formally accept residual risks before external handoff.")
    if not actions:
        actions.append("Proceed with external handoff using the verified package and closure report.")
    return tuple(dict.fromkeys(actions))


def required_evidence_ids_from_payload(payload: dict[str, Any]) -> tuple[str, ...]:
    closure_summary = payload.get("closure_summary") if isinstance(payload.get("closure_summary"), dict) else {}
    ids = closure_summary.get("required_evidence_ids")
    if not isinstance(ids, list):
        return ()
    return tuple(str(item) for item in ids)


def external_handoff_blockers_from_payload(payload: dict[str, Any]) -> tuple[str, ...]:
    blockers = payload.get("external_handoff_blockers")
    if not isinstance(blockers, list):
        return ()
    return tuple(str(item) for item in blockers)


def closeout_commands_from_payload(payload: dict[str, Any]) -> tuple[str, ...]:
    commands = payload.get("closeout_commands")
    if not isinstance(commands, list):
        return ()
    return tuple(str(item) for item in commands if str(item).strip())


def escape_cell(value: str) -> str:
    return value.replace("|", "\\|").replace("\n", " ")


def json_compatible(value: Any) -> Any:
    return json.loads(json.dumps(value))


def same_package_reference(actual: object, expected: object) -> bool:
    actual_text = str(actual or "")
    expected_text = str(expected or "")
    if actual_text == expected_text:
        return True
    try:
        return Path(actual_text).resolve() == Path(expected_text).resolve()
    except OSError:
        return False
