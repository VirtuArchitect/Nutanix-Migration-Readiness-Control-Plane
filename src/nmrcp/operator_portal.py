from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PORTAL_SCHEMA_VERSION = "nmrcp_operator_portal_v1"
PORTAL_ARTIFACTS = (
    ("operations-console.html", "Operations console", "Move-style guided UI for connection setup, compatibility analysis, and Move planning."),
    ("operator-dashboard.html", "Operator dashboard", "Interactive workload queue and filters."),
    ("operator-report.html", "Operator report", "Detailed assessment report for operators and change boards."),
    ("executive-readiness-brief.md", "Executive brief", "Sponsor-ready summary and decision ask."),
    ("change-board-evidence.md", "Change-board evidence", "Redacted evidence pack for approval review."),
    ("migration-runbook.md", "Migration runbook", "Wave-ordered operator actions and stop conditions."),
    ("nutanix-move-plan.csv", "Move staging plan", "Include/hold plan for Nutanix Move review."),
    ("move-staging-brief.md", "Move staging brief", "Reviewer-ready include, hold, blocker, and evidence summary."),
    ("pre-post-validation-checklist.md", "Validation checklist", "Pre, cutover, and post-migration validation checklist."),
    ("source-endpoint-evidence-request.md", "Source endpoint evidence request", "Read-only vCenter and Prism validation request."),
    ("move-lab-closure-checklist.md", "Move lab closure checklist", "Approved lab proof closure path."),
    ("move-lab-evidence-request.md", "Move lab evidence request", "Approved lab proof window request and stop conditions."),
    ("what-will-break-brief.md", "What will break brief", "Executive-readable breakage scenarios, owner holds, and evidence links."),
    ("external-proof-plan.md", "External proof plan", "Closeout plan for approved endpoint and Nutanix Move proof gaps."),
    ("operator-gate-summary.md", "Operator gate summary", "Optional final gate rollup when closure evidence is supplied."),
    ("evidence-manifest.json", "Evidence manifest", "SHA-256 and size manifest for generated artifacts."),
)
OPTIONAL_PORTAL_ARTIFACTS = frozenset({"external-proof-plan.md", "operator-gate-summary.md"})
REQUIRED_TEXT = (
    "<!doctype html>",
    "<title>NMRCP Operator Portal</title>",
    "Nutanix Migration Readiness Portal",
    "Readiness Snapshot",
    "Artifact Launchpad",
    "Proof Posture",
    "Required proof contracts",
    "Move staging brief",
    "What will break brief",
    "External proof plan",
    "nmrcp_external_proof_plan_v1",
    "proof/external-proof-plan.json",
    "nmrcp_move_lab_proof_validation_v1",
    "nmrcp_move_lab_evidence_intake_v1",
    "Open the dashboard first, then use the report, runbook, Move plan, and gate evidence for review.",
    "Do not claim external handoff readiness until approved Nutanix Move lab proof and evidence intake pass.",
    "Do not package external handoff readiness unless the external proof plan validates with approved endpoint and Move lab evidence.",
)


@dataclass(frozen=True)
class OperatorPortalValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def write_operator_portal(
    inventory: dict[str, Any],
    assessments: list[Any],
    waves: list[Any],
    path: Path,
) -> None:
    payload = portal_payload(inventory, assessments, waves)
    cards = "\n".join(
        artifact_card(name, title, description, available=name not in OPTIONAL_PORTAL_ARTIFACTS)
        for name, title, description in PORTAL_ARTIFACTS
    )
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NMRCP Operator Portal</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #5f6b78;
      --line: #d8dde5;
      --panel: #f6f8fb;
      --surface: #ffffff;
      --accent: #245c85;
      --ready: #1f7a4d;
      --research: #7b6114;
      --prepare: #9b4a17;
      --blocked: #a12828;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      color: var(--ink);
      background: var(--surface);
    }}
    header {{
      border-bottom: 1px solid var(--line);
      padding: 26px 30px 20px;
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(220px, 320px);
      gap: 18px;
      align-items: end;
    }}
    h1, h2, h3, p {{ margin-top: 0; }}
    h1 {{ font-size: 28px; margin-bottom: 6px; }}
    h2 {{ font-size: 18px; margin-bottom: 12px; }}
    h3 {{ font-size: 15px; margin-bottom: 6px; }}
    main {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(300px, 390px);
      min-height: calc(100vh - 110px);
    }}
    .workspace {{
      padding: 24px 30px 34px;
      display: grid;
      gap: 22px;
      align-content: start;
    }}
    aside {{
      border-left: 1px solid var(--line);
      background: var(--panel);
      padding: 24px 24px 34px;
    }}
    .muted, .meta, .artifact p, .proof dd {{ color: var(--muted); }}
    .snapshot {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 10px;
    }}
    .metric {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px;
      min-height: 82px;
    }}
    .metric strong {{ display: block; font-size: 26px; line-height: 1.1; }}
    .metric span {{ color: var(--muted); }}
    .launchpad {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 12px;
    }}
    .artifact {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 14px;
      background: white;
      min-height: 128px;
      display: grid;
      gap: 10px;
      align-content: start;
    }}
    .artifact a {{
      color: var(--accent);
      font-weight: 700;
      text-decoration: none;
      word-break: break-word;
    }}
    .artifact a:focus, .artifact a:hover {{
      text-decoration: underline;
      outline: 2px solid transparent;
    }}
    .tag {{
      display: inline-block;
      border-radius: 999px;
      padding: 3px 8px;
      color: white;
      font-size: 12px;
      font-weight: 700;
      text-transform: capitalize;
    }}
    .ready {{ background: var(--ready); }}
    .research {{ background: var(--research); }}
    .prepare {{ background: var(--prepare); }}
    .blocked {{ background: var(--blocked); }}
    .proof {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
      padding: 14px;
    }}
    dl {{
      display: grid;
      grid-template-columns: minmax(120px, .85fr) minmax(0, 1.15fr);
      gap: 10px 12px;
      margin: 0;
    }}
    dt {{ font-weight: 700; }}
    dd {{ margin: 0; word-break: break-word; }}
    ol {{ margin: 0; padding-left: 20px; }}
    li {{ margin: 8px 0; }}
    @media (max-width: 880px) {{
      header, main {{ display: block; }}
      aside {{ border-left: 0; border-top: 1px solid var(--line); }}
    }}
  </style>
</head>
<body>
  <header>
    <div>
      <h1>Nutanix Migration Readiness Portal</h1>
      <p class="muted">Open the dashboard first, then use the report, runbook, Move plan, and gate evidence for review.</p>
    </div>
    <p class="meta">Local, redacted assessment landing page.</p>
  </header>
  <main>
    <section class="workspace">
      <section>
        <h2>Readiness Snapshot</h2>
        <div class="snapshot">{summary_metrics(payload["summary"])}</div>
      </section>
      <section>
        <h2>Artifact Launchpad</h2>
        <div class="launchpad">{cards}</div>
      </section>
    </section>
    <aside>
      <section class="proof">
        <h2>Proof Posture</h2>
        <dl>
          <dt>Schema</dt><dd>{escape(PORTAL_SCHEMA_VERSION)}</dd>
          <dt>Workloads</dt><dd>{escape(payload["summary"]["total"])}</dd>
          <dt>Waves</dt><dd>{escape(len(waves))}</dd>
          <dt>Move proof</dt><dd>Approved Nutanix Move lab proof is required before external handoff.</dd>
          <dt>External proof plan</dt><dd>Generate <code>external-proof-plan.md</code> and package <code>proof/external-proof-plan.json</code> only after <code>nmrcp_external_proof_plan_v1</code> validates.</dd>
          <dt>Required proof contracts</dt><dd><code>nmrcp_move_lab_proof_validation_v1</code><br><code>nmrcp_move_lab_evidence_intake_v1</code></dd>
          <dt>Secret posture</dt><dd>Evidence is generated from redacted assessment data.</dd>
        </dl>
      </section>
      <section>
        <h2>Review Order</h2>
        <ol>
          <li>Open `operator-dashboard.html` to triage held workloads.</li>
          <li>Review `operator-report.html` and `change-board-evidence.md`.</li>
          <li>Validate `nutanix-move-plan.csv` and `pre-post-validation-checklist.md`.</li>
          <li>Use `external-proof-plan.md` to close approved endpoint and Nutanix Move lab proof gaps.</li>
          <li>Do not claim external handoff readiness until approved Nutanix Move lab proof and evidence intake pass.</li>
          <li>Do not package external handoff readiness unless the external proof plan validates with approved endpoint and Move lab evidence.</li>
        </ol>
      </section>
    </aside>
  </main>
  <script id="portal-data" type="application/json">{script_json(payload)}</script>
</body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")


def validate_operator_portal(portal_path: Path, assessment_path: Path) -> OperatorPortalValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    try:
        raw_text = portal_path.read_text(encoding="utf-8")
    except OSError as exc:
        return OperatorPortalValidation("fail", 1, (f"{portal_path}: could not read operator portal: {exc}",), ())
    try:
        assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return OperatorPortalValidation("fail", 1, (f"{assessment_path}: could not read assessment JSON: {exc}",), ())

    text = html.unescape(raw_text)
    for required in REQUIRED_TEXT:
        checks += 1
        if required not in text:
            errors.append(f"Operator portal missing required text: {required}")

    payload = extract_portal_payload(raw_text, errors)
    checks += 1
    if not payload:
        return OperatorPortalValidation("fail", checks, tuple(errors), tuple(warnings))

    checks += 1
    if payload.get("schema_version") != PORTAL_SCHEMA_VERSION:
        errors.append(f"Operator portal schema_version must be {PORTAL_SCHEMA_VERSION}")

    summary = assessment.get("summary") if isinstance(assessment.get("summary"), dict) else {}
    portal_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    for key in ("total", "ready", "research", "prepare", "blocked"):
        checks += 1
        expected = int(summary.get(key) or 0)
        actual = int(portal_summary.get(key) or 0)
        if actual != expected:
            errors.append(f"Operator portal summary {key} expected {expected}, got {actual}")

    for key, label in (
        ("total", "Total workloads"),
        ("ready", "Ready"),
        ("research", "Research"),
        ("prepare", "Prepare"),
        ("blocked", "Blocked"),
    ):
        checks += 1
        expected = int(summary.get(key) or 0)
        if expected_metric_fragment(label, expected) not in text:
            errors.append(f"Operator portal missing visible readiness metric: {label}={expected}")

    checks += 1
    expected_workloads = int(summary.get("total") or 0)
    if expected_proof_posture_fragment("Workloads", expected_workloads) not in text:
        errors.append(f"Operator portal proof posture workload count expected {expected_workloads}")

    checks += 1
    expected_waves = len([wave for wave in assessment.get("waves", []) if isinstance(wave, dict)])
    if expected_proof_posture_fragment("Waves", expected_waves) not in text:
        errors.append(f"Operator portal proof posture wave count expected {expected_waves}")

    artifacts = payload.get("artifacts") if isinstance(payload.get("artifacts"), list) else []
    artifact_names = {str(item.get("name") or "") for item in artifacts if isinstance(item, dict)}
    for name, title, description in PORTAL_ARTIFACTS:
        checks += 1
        if name not in artifact_names:
            errors.append(f"Operator portal missing artifact payload entry: {name}")
        if f'href="{name}"' not in raw_text:
            errors.append(f"Operator portal missing artifact link: {name}")
        for label, fragment in (("title", title), ("description", description)):
            checks += 1
            if fragment not in text:
                errors.append(f"Operator portal missing artifact {label} for {name}: {fragment}")
        if name not in OPTIONAL_PORTAL_ARTIFACTS and not (portal_path.parent / name).exists():
            errors.append(f"Operator portal linked artifact does not exist: {name}")

    checks += 1
    if "[REDACTED" not in text and "redacted" not in text.lower():
        errors.append("Operator portal must state redacted evidence posture")
    checks += 1
    if "vcenter01.corp.local" in text:
        errors.append("Operator portal leaked sample vCenter hostname")
    checks += 1
    if "migration.owner@example.com" in text:
        errors.append("Operator portal leaked sample operator email")

    return OperatorPortalValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def portal_payload(inventory: dict[str, Any], assessments: list[Any], waves: list[Any]) -> dict[str, Any]:
    return {
        "schema_version": PORTAL_SCHEMA_VERSION,
        "summary": summarize_assessments(assessments),
        "source": {
            "metadata_records": safe_source_int(inventory, "metadata_records"),
            "metadata_unmatched_records": safe_source_int(inventory, "metadata_unmatched_records"),
            "dependency_records": safe_source_int(inventory, "dependency_records"),
            "dependency_unmatched_records": safe_source_int(inventory, "dependency_unmatched_records"),
        },
        "artifacts": [
            {"name": name, "title": title, "description": description}
            for name, title, description in PORTAL_ARTIFACTS
        ],
        "waves": [str(getattr(wave, "name", "")) for wave in waves],
    }


def summarize_assessments(assessments: list[Any]) -> dict[str, int]:
    summary = {"ready": 0, "research": 0, "prepare": 0, "blocked": 0}
    for assessment in assessments:
        readiness = str(getattr(assessment, "readiness", ""))
        summary[readiness] = summary.get(readiness, 0) + 1
    summary["total"] = len(assessments)
    return summary


def safe_source_int(inventory: dict[str, Any], key: str) -> int:
    source = inventory.get("source") if isinstance(inventory.get("source"), dict) else {}
    try:
        return int(source.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def artifact_card(name: str, title: str, description: str, *, available: bool) -> str:
    status = "available" if available else "optional"
    return (
        '<article class="artifact">'
        f'<a href="{escape(name)}">{escape(title)}</a>'
        f"<p>{escape(description)}</p>"
        f'<span class="muted">{escape(status)} - {escape(name)}</span>'
        "</article>"
    )


def summary_metrics(summary: dict[str, int]) -> str:
    return "\n".join(
        f'<div class="metric"><strong>{int(summary.get(key, 0))}</strong><span>{escape(label)}</span></div>'
        for key, label in (
            ("total", "Total workloads"),
            ("ready", "Ready"),
            ("research", "Research"),
            ("prepare", "Prepare"),
            ("blocked", "Blocked"),
        )
    )


def expected_metric_fragment(label: str, value: int) -> str:
    return f'<div class="metric"><strong>{value}</strong><span>{label}</span></div>'


def expected_proof_posture_fragment(label: str, value: int) -> str:
    return f"<dt>{label}</dt><dd>{value}</dd>"


def extract_portal_payload(raw_text: str, errors: list[str]) -> dict[str, Any]:
    match = re.search(
        r'<script id="portal-data" type="application/json">(.*?)</script>',
        raw_text,
        flags=re.DOTALL,
    )
    if not match:
        errors.append("Operator portal missing portal-data JSON script")
        return {}
    try:
        payload = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError as exc:
        errors.append(f"Operator portal portal-data JSON is invalid: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append("Operator portal portal-data JSON must be an object")
        return {}
    return payload


def script_json(payload: dict[str, Any]) -> str:
    return html.escape(json.dumps(payload, separators=(",", ":")), quote=False)


def escape(value: object) -> str:
    return html.escape(str(value), quote=True)
