from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


TESTER_REPORT_SCHEMA_VERSION = "nmrcp_tester_report_v1"


@dataclass(frozen=True)
class TesterArtifact:
    role: str
    path: Path
    exists: bool
    status: str
    detail: str


def build_tester_report(data_dir: Path) -> dict[str, Any]:
    data_dir = data_dir.resolve()
    live_readiness = _read_json(data_dir / "live-readiness.json")
    collection_summary = _read_json(data_dir / "source-collection" / "collection-summary.json")
    assessment = _read_json(data_dir / "assessment" / "assessment.json")
    evidence_manifest = _read_json(data_dir / "assessment" / "evidence-manifest.json")

    artifacts = [
        _artifact("live_readiness", data_dir / "live-readiness.json", live_readiness),
        _artifact("collection_summary", data_dir / "source-collection" / "collection-summary.json", collection_summary),
        _artifact("collection_proof_report", data_dir / "source-collection" / "collection-proof-report.md", None),
        _artifact("assessment", data_dir / "assessment" / "assessment.json", assessment),
        _artifact("evidence_manifest", data_dir / "assessment" / "evidence-manifest.json", evidence_manifest),
        _artifact("operations_console", data_dir / "assessment" / "operations-console.html", None),
    ]
    readiness = _readiness_summary(assessment)
    checks = _checks(live_readiness, collection_summary)
    missing = [item.role for item in artifacts if not item.exists]
    status = "ready_for_tester_feedback" if not missing and _required_checks_pass(checks) else "incomplete"

    return {
        "schema_version": TESTER_REPORT_SCHEMA_VERSION,
        "status": status,
        "data_dir": str(data_dir),
        "summary": readiness,
        "checks": checks,
        "artifacts": [
            {
                "role": item.role,
                "path": str(item.path),
                "exists": item.exists,
                "status": item.status,
                "detail": item.detail,
            }
            for item in artifacts
        ],
        "missing_artifacts": missing,
        "safe_to_share": {
            "attach_redacted_outputs_only": True,
            "never_attach_credentials": True,
            "never_attach_raw_inventory": True,
            "redact_endpoint_values": True,
            "redact_customer_identifiers": True,
        },
        "github_issue_template": "Tester Connection Report",
    }


def write_tester_report(data_dir: Path, report_path: Path, json_path: Path | None = None) -> dict[str, Any]:
    report = build_tester_report(data_dir)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_tester_report(report), encoding="utf-8")
    if json_path is not None:
        json_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def render_tester_report(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# NMRCP Tester Report",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Data directory: `{report.get('data_dir')}`",
        f"- GitHub issue template: `{report.get('github_issue_template')}`",
        "",
        "## Readiness Summary",
        "",
        f"- Workloads: `{summary.get('workloads', 0)}`",
        f"- Waves: `{summary.get('waves', 0)}`",
        f"- Ready: `{summary.get('ready', 0)}`",
        f"- Research: `{summary.get('research', 0)}`",
        f"- Prepare: `{summary.get('prepare', 0)}`",
        f"- Blocked: `{summary.get('blocked', 0)}`",
        "",
        "## Checks",
        "",
        "| Check | Status | Detail |",
        "| --- | --- | --- |",
    ]
    for check in report.get("checks", []):
        lines.append(f"| `{check.get('name')}` | `{check.get('status')}` | {check.get('detail')} |")
    lines.extend(
        [
            "",
            "## Redacted Artifact Candidates",
            "",
            "| Role | Present | Status | Path |",
            "| --- | --- | --- | --- |",
        ]
    )
    for artifact in report.get("artifacts", []):
        present = "yes" if artifact.get("exists") else "no"
        lines.append(
            f"| `{artifact.get('role')}` | `{present}` | `{artifact.get('status')}` | `{artifact.get('path')}` |"
        )
    lines.extend(
        [
            "",
            "## Sharing Rules",
            "",
            "- Attach redacted outputs only.",
            "- Do not attach credentials, raw inventory, endpoint values, FQDNs, IP addresses, VM names, or customer identifiers.",
            "- Use the GitHub Tester Connection Report template so results are consistent.",
            "",
        ]
    )
    return "\n".join(lines)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"status": "invalid_json"}
    return value if isinstance(value, dict) else {"status": "invalid_json"}


def _artifact(role: str, path: Path, payload: dict[str, Any] | None) -> TesterArtifact:
    exists = path.exists()
    if payload is not None:
        status = str(payload.get("status") or "present")
        detail = str(payload.get("schema_version") or "json")
    elif exists:
        status = "present"
        detail = "file"
    else:
        status = "missing"
        detail = "not generated yet"
    return TesterArtifact(role=role, path=path, exists=exists, status=status, detail=detail)


def _readiness_summary(assessment: dict[str, Any] | None) -> dict[str, int]:
    summary = assessment.get("summary") if isinstance(assessment, dict) else None
    if isinstance(summary, dict):
        return {
            "workloads": int(summary.get("total") or summary.get("workloads") or 0),
            "waves": _count_waves(assessment),
            "ready": int(summary.get("ready") or 0),
            "research": int(summary.get("research") or 0),
            "prepare": int(summary.get("prepare") or 0),
            "blocked": int(summary.get("blocked") or 0),
        }
    workloads = assessment.get("workloads") if isinstance(assessment, dict) else []
    waves = assessment.get("waves") if isinstance(assessment, dict) else []
    if not isinstance(workloads, list):
        workloads = []
    if not isinstance(waves, list):
        waves = []
    counts = {"workloads": len(workloads), "waves": len(waves), "ready": 0, "research": 0, "prepare": 0, "blocked": 0}
    for workload in workloads:
        if not isinstance(workload, dict):
            continue
        readiness = str(workload.get("readiness") or "").lower()
        if readiness in counts:
            counts[readiness] += 1
    return counts


def _count_waves(assessment: dict[str, Any] | None) -> int:
    waves = assessment.get("waves") if isinstance(assessment, dict) else []
    return len(waves) if isinstance(waves, list) else 0


def _checks(live_readiness: dict[str, Any] | None, collection_summary: dict[str, Any] | None) -> list[dict[str, str]]:
    return [
        _check("connection-proof", live_readiness),
        _check("source-collection", collection_summary),
    ]


def _check(name: str, payload: dict[str, Any] | None) -> dict[str, str]:
    if payload is None:
        return {"name": name, "status": "missing", "detail": "not generated yet"}
    status = str(payload.get("status") or "unknown")
    return {"name": name, "status": status, "detail": str(payload.get("schema_version") or "json")}


def _required_checks_pass(checks: list[dict[str, str]]) -> bool:
    return all(check.get("status") == "pass" for check in checks)
