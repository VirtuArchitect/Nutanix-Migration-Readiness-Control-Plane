from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .models import Wave, WorkloadAssessment


OPERATIONS_CONSOLE_SCHEMA_VERSION = "nmrcp_operations_console_v1"
REQUIRED_TEXT = (
    "<!doctype html>",
    "<title>NMRCP Operations Console</title>",
    "Nutanix Migration Readiness Operations Console",
    "Connect Environments",
    "vCenter",
    "Prism Central",
    "ESXi",
    "Nutanix Move",
    "RVTools / Import",
    "Environment Gates",
    "Test Read-only Connections",
    "Collect Source Evidence",
    "Run Readiness Assessment",
    "Prepare Tester Report",
    "Run Compatibility Analysis",
    "Build Move Plan",
    "Operator Workbench",
    "/api/connection-test",
    "/api/collect-sources",
    "/api/run-readiness",
    "/api/tester-report",
    "/api/environment-access",
    "Environment connections are local-only and require explicit operator approval.",
    "Do not store credentials in the console or generated artifacts.",
    "Use approved read-only collection before claiming endpoint proof.",
    "Use approved Nutanix Move lab evidence before external handoff.",
)


@dataclass(frozen=True)
class OperationsConsoleValidation:
    status: str
    checks: int
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors

    def summary(self) -> str:
        return f"{self.status.upper()}: checks={self.checks}, errors={len(self.errors)}, warnings={len(self.warnings)}"


def write_operations_console(
    inventory: dict[str, Any],
    assessments: list[WorkloadAssessment],
    waves: list[Wave],
    path: Path,
) -> None:
    payload = console_payload(inventory, assessments, waves)
    rows = "\n".join(workload_row(row) for row in payload["workloads"])
    html_doc = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>NMRCP Operations Console</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17202a;
      --muted: #5f6b78;
      --line: #d8dde5;
      --panel: #f5f7fa;
      --surface: #ffffff;
      --nav: #101820;
      --nav-muted: #a7b3c2;
      --accent: #1c6b8f;
      --ready: #1f7a4d;
      --research: #7b6114;
      --prepare: #9b4a17;
      --blocked: #a12828;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 14px;
      line-height: 1.4;
      color: var(--ink);
      background: var(--surface);
    }}
    .shell {{
      min-height: 100vh;
      display: grid;
      grid-template-columns: 248px minmax(0, 1fr);
    }}
    nav {{
      background: var(--nav);
      color: white;
      padding: 22px 18px;
      display: grid;
      align-content: start;
      gap: 18px;
    }}
    nav h1 {{
      font-size: 18px;
      line-height: 1.25;
      margin: 0;
    }}
    nav a {{
      display: block;
      color: var(--nav-muted);
      text-decoration: none;
      padding: 9px 10px;
      border-radius: 6px;
      font-weight: 700;
      font-size: 13px;
    }}
    nav a:focus, nav a:hover {{
      color: white;
      background: rgba(255,255,255,.1);
      outline: 2px solid transparent;
    }}
    main {{
      min-width: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }}
    header {{
      border-bottom: 1px solid var(--line);
      padding: 18px 24px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
    }}
    h2, h3, p {{ margin-top: 0; }}
    h2 {{ font-size: 17px; line-height: 1.25; margin-bottom: 12px; }}
    h3 {{ font-size: 13px; line-height: 1.25; margin-bottom: 8px; }}
    .content {{
      padding: 22px 24px 32px;
      display: grid;
      gap: 22px;
      align-content: start;
    }}
    .status-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 10px;
    }}
    .metric, .connection, .panel {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: white;
    }}
    .metric {{ padding: 12px; }}
    .metric strong {{ display: block; font-size: 22px; line-height: 1.1; }}
    .muted, label, .meta, th, .hint {{ color: var(--muted); }}
    .connections {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 12px;
    }}
    .connection {{
      padding: 14px;
      display: grid;
      gap: 10px;
      align-content: start;
      min-height: 228px;
    }}
    label {{ display: grid; gap: 5px; font-size: 12px; line-height: 1.25; font-weight: 700; }}
    input, select, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      font: inherit;
      font-size: 13px;
      line-height: 1.3;
      background: white;
      color: var(--ink);
    }}
    input[type="checkbox"] {{
      width: auto;
      margin: 0;
    }}
    textarea {{ min-height: 88px; resize: vertical; }}
    #run-command {{
      min-height: 104px;
      font-family: Consolas, "Liberation Mono", monospace;
      font-size: 12px;
      line-height: 1.35;
      white-space: pre;
      overflow: auto;
    }}
    button {{
      border: 1px solid var(--accent);
      border-radius: 6px;
      background: var(--accent);
      color: white;
      padding: 9px 11px;
      font-size: 13px;
      line-height: 1.2;
      font-weight: 700;
      cursor: pointer;
    }}
    button.secondary {{
      background: white;
      color: var(--accent);
    }}
    button[disabled] {{
      cursor: not-allowed;
      opacity: .58;
    }}
    button:focus, input:focus, select:focus, textarea:focus {{
      outline: 2px solid var(--accent);
      outline-offset: 2px;
    }}
    .workbench {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(280px, 360px);
      gap: 14px;
    }}
    .panel {{ padding: 14px; }}
    .filters {{
      display: grid;
      grid-template-columns: minmax(180px, 1fr) repeat(2, minmax(120px, 180px));
      gap: 10px;
      margin-bottom: 12px;
    }}
    .gate-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px 12px;
      margin-bottom: 12px;
    }}
    .gate-grid label {{
      display: flex;
      align-items: center;
      gap: 7px;
      min-height: 26px;
      font-weight: 600;
    }}
    .table-wrap {{
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: auto;
    }}
    table {{ width: 100%; border-collapse: collapse; min-width: 760px; }}
    th, td {{
      padding: 9px 11px;
      border-bottom: 1px solid var(--line);
      text-align: left;
      vertical-align: top;
      font-size: 12.5px;
      line-height: 1.3;
    }}
    tr:last-child td {{ border-bottom: 0; }}
    .pill {{
      display: inline-block;
      border-radius: 999px;
      padding: 4px 7px;
      color: white;
      font-size: 11px;
      line-height: 1;
      font-weight: 700;
      text-transform: capitalize;
    }}
    .ready {{ background: var(--ready); }}
    .research {{ background: var(--research); }}
    .prepare {{ background: var(--prepare); }}
    .blocked {{ background: var(--blocked); }}
    .steps {{
      display: grid;
      gap: 8px;
      padding: 0;
      margin: 0;
      list-style: none;
    }}
    .steps li {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 10px;
      background: var(--panel);
      font-size: 13px;
      line-height: 1.25;
    }}
    .steps strong {{
      display: inline-block;
      font-size: 13px;
      line-height: 1.2;
      margin-bottom: 2px;
    }}
    .steps .muted {{ line-height: 1.25; }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }}
    .proof {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      padding: 12px;
      min-height: 120px;
      white-space: pre-wrap;
      overflow: auto;
      font-size: 12px;
    }}
    @media (max-width: 960px) {{
      .shell, .workbench {{ display: block; }}
      .content {{ padding: 18px; }}
      .filters {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <nav aria-label="Primary">
      <h1>Nutanix Migration Readiness Operations Console</h1>
      <div>
        <a href="#connect">Connect Environments</a>
        <a href="#analyze">Run Compatibility Analysis</a>
        <a href="#plan">Build Move Plan</a>
        <a href="#workbench">Operator Workbench</a>
      </div>
      <p class="hint">Environment connections are local-only and require explicit operator approval.</p>
    </nav>
    <main>
      <header>
        <div>
          <h2>Nutanix Migration Readiness Operations Console</h2>
          <p class="muted">Move-style guided assessment console for source discovery, compatibility analysis, wave planning, and evidence review.</p>
        </div>
        <button type="button" class="secondary" id="copy-command">Copy Run Command</button>
      </header>
      <section class="content">
        <section class="status-strip" aria-label="Readiness summary">
          {metric("Workloads", payload["summary"]["total"])}
          {metric("Ready", payload["summary"]["ready"])}
          {metric("Research", payload["summary"]["research"])}
          {metric("Prepare", payload["summary"]["prepare"])}
          {metric("Blocked", payload["summary"]["blocked"])}
          {metric("Waves", len(payload["waves"]))}
        </section>
        <section id="connect">
          <h2>Connect Environments</h2>
          <div class="connections">
            {connection_card("vcenter", "vCenter", "Read-only VM, network, guest, tools, snapshot, and dependency source.")}
            {connection_card("prism", "Prism Central", "Read-only AHV/NC2 target inventory, capacity, categories, and collision checks.")}
            {connection_card("move", "Nutanix Move", "Approved lab-only payload review and dry-run proof capture.")}
            {connection_card("esxi", "ESXi", "Host-level connectivity gate for approved read or write-intent workflows.")}
            {connection_card("import", "RVTools / Import", "Offline CSV/JSON intake for discovery when live endpoints are not approved.")}
          </div>
          <div class="panel">
            <h3>Tester Connection Workflow</h3>
            <div class="filters" aria-label="Environment gates">
              <label>Environment<select id="environment-select"><option value="dev">Dev</option><option value="uat">UAT</option><option value="production">Production</option></select></label>
              <label>Mode<select id="mode-select"><option value="read">Read</option><option value="write">Write intent</option></select></label>
              <label>Target<select id="target-select"><option value="pc">Prism Central</option><option value="move">Nutanix Move</option><option value="vcenter">vCenter</option><option value="esxi">ESXi</option></select></label>
            </div>
            <div class="gate-grid" aria-label="Required environment gates">
              <label><input type="checkbox" data-gate="source_scope_approved">Source scope approved</label>
              <label><input type="checkbox" data-gate="credential_source_approved">Credential source approved</label>
              <label><input type="checkbox" data-gate="change_reference">Change reference</label>
              <label><input type="checkbox" data-gate="rollback_plan">Rollback plan</label>
              <label><input type="checkbox" data-gate="write_scope_approved">Write scope approved</label>
              <label><input type="checkbox" data-gate="operator_acknowledgement">Operator acknowledgement</label>
              <label><input type="checkbox" data-gate="maintenance_window">Maintenance window</label>
              <label><input type="checkbox" data-gate="peer_review">Peer review</label>
              <label><input type="checkbox" data-gate="dry_run_passed">Dry run passed</label>
              <label><input type="checkbox" data-gate="cab_approval">CAB approval</label>
              <label><input type="checkbox" data-gate="backup_verified">Backup verified</label>
              <label><input type="checkbox" data-gate="production_write_break_glass">Production write break-glass</label>
              <label><input type="checkbox" data-gate="target_cluster_scope">Target cluster scope</label>
              <label><input type="checkbox" data-gate="move_lab_or_approved_appliance">Move lab/appliance scope</label>
              <label><input type="checkbox" data-gate="vm_scope_approved">VM scope approved</label>
              <label><input type="checkbox" data-gate="host_scope_approved">Host scope approved</label>
            </div>
            <div class="actions">
              <button type="button" id="environment-access">Validate Environment Gates</button>
              <button type="button" id="test-connections">Test Read-only Connections</button>
              <button type="button" id="collect-sources" class="secondary">Collect Source Evidence</button>
              <button type="button" id="run-readiness" class="secondary">Run Readiness Assessment</button>
              <button type="button" id="tester-report" class="secondary">Prepare Tester Report</button>
            </div>
            <p class="hint">These buttons call /api/environment-access, /api/connection-test, /api/collect-sources, /api/run-readiness, and /api/tester-report on this local console server. Passwords are sent only to the local process for the active request and are not written to proof files. Write intent validates gates only; this workflow does not execute mutating actions.</p>
            <div class="proof" id="api-proof" role="status" aria-live="polite">Ready for tester input. API actions require the local nmrcp serve console. Use secure endpoints unless you are testing against a loopback simulator.</div>
          </div>
        </section>
        <section id="analyze" class="workbench">
          <div class="panel">
            <h2>Run Compatibility Analysis</h2>
            <div class="filters" aria-label="Workload filters">
              <label>Search<input id="search" type="search" placeholder="Workload, owner, finding"></label>
              <label>Readiness<select id="readiness-filter"><option value="">All states</option><option>ready</option><option>research</option><option>prepare</option><option>blocked</option></select></label>
              <label>Wave<select id="wave-filter"><option value="">All waves</option></select></label>
            </div>
            <div class="table-wrap">
              <table>
                <thead>
                  <tr><th>Workload</th><th>Readiness</th><th>Risk</th><th>Wave</th><th>Move action</th><th>Top finding</th></tr>
                </thead>
                <tbody id="workload-rows">{rows}</tbody>
              </table>
            </div>
          </div>
          <aside class="panel" id="workbench">
            <h2>Operator Workbench</h2>
            <ol class="steps">
              <li><strong>1. Select environment</strong><br><span class="muted">Choose Dev, UAT, or Production and validate read/write gates for PC, Move, vCenter, or ESXi.</span></li>
              <li><strong>2. Connect source</strong><br><span class="muted">Validate vCenter and Prism Central with read-only proof.</span></li>
              <li><strong>3. Discover inventory</strong><br><span class="muted">Collect or import source workload, network, storage, and ownership data.</span></li>
              <li><strong>4. Analyze compatibility</strong><br><span class="muted">Review AHV/NC2 readiness, dependencies, blockers, and what-will-break evidence.</span></li>
              <li id="plan"><strong>5. Build Move Plan</strong><br><span class="muted">Stage only ready/research workloads into the Move plan after review.</span></li>
              <li><strong>6. Package tester feedback</strong><br><span class="muted">Prepare a redacted local report for GitHub tester feedback.</span></li>
            </ol>
            <h3>Generated local command</h3>
            <textarea id="run-command" spellcheck="false">python -m nmrcp.cli run-assessment --inventory examples/sample_inventory.json --metadata examples/sample_metadata.csv --dependencies examples/sample_dependencies.csv --move-config examples/sample_move_payload_config.json --out outputs/assessment</textarea>
            <p class="hint">Do not store credentials in the console or generated artifacts. Use approved read-only collection before claiming endpoint proof. Use approved Nutanix Move lab evidence before external handoff.</p>
          </aside>
        </section>
      </section>
    </main>
  </div>
  <script id="operations-console-data" type="application/json">{script_json(payload)}</script>
  <script>
    const payload = JSON.parse(document.getElementById("operations-console-data").textContent);
    const rows = Array.from(document.querySelectorAll("#workload-rows tr"));
    const waveFilter = document.getElementById("wave-filter");
    for (const wave of payload.waves) {{
      const option = document.createElement("option");
      option.value = wave.name;
      option.textContent = wave.name;
      waveFilter.appendChild(option);
    }}
    function applyFilters() {{
      const search = document.getElementById("search").value.toLowerCase();
      const readiness = document.getElementById("readiness-filter").value;
      const wave = waveFilter.value;
      for (const row of rows) {{
        const text = row.textContent.toLowerCase();
        const visible = (!search || text.includes(search)) &&
          (!readiness || row.dataset.readiness === readiness) &&
          (!wave || row.dataset.wave === wave);
        row.hidden = !visible;
      }}
    }}
    document.getElementById("search").addEventListener("input", applyFilters);
    document.getElementById("readiness-filter").addEventListener("change", applyFilters);
    waveFilter.addEventListener("change", applyFilters);
    function endpointPayload(prefix) {{
      const card = document.querySelector(`[data-connection="${{prefix}}"]`);
      if (!card) return {{}};
      return {{
        endpoint: card.querySelector("[data-field='endpoint']").value,
        username: card.querySelector("[data-field='username']").value,
        credential: card.querySelector("[data-field='credential']").value,
        verify_tls: card.querySelector("[data-field='verify_tls']").checked,
        timeout_seconds: Number(card.querySelector("[data-field='timeout']").value || 20)
      }};
    }}
    function environmentAccessPayload() {{
      const gates = {{}};
      for (const gate of document.querySelectorAll("[data-gate]")) {{
        gates[gate.dataset.gate] = gate.checked;
      }}
      return {{
        environment: document.getElementById("environment-select").value,
        mode: document.getElementById("mode-select").value,
        target: document.getElementById("target-select").value,
        gates
      }};
    }}
    function scrub(payload) {{
      return JSON.stringify(payload, (key, value) => key === "credential" ? "[request-only]" : value, 2);
    }}
    function setProof(message) {{
      document.getElementById("api-proof").textContent = message;
    }}
    async function postJson(path, body) {{
      setProof(`Running ${{path}}...`);
      const response = await fetch(path, {{
        method: "POST",
        headers: {{"Content-Type": "application/json"}},
        body: JSON.stringify(body)
      }});
      const text = await response.text();
      let payload;
      try {{ payload = JSON.parse(text); }}
      catch (error) {{
        throw new Error("Local console API is unavailable. Run nmrcp serve or Docker Compose, then open the local console URL.");
      }}
      if (!response.ok || payload.status === "fail") {{
        throw new Error(scrub(payload));
      }}
      setProof(scrub(payload));
      return payload;
    }}
    async function runAction(button, action) {{
      button.disabled = true;
      try {{ await action(); }}
      catch (error) {{ setProof(error.message); }}
      finally {{ button.disabled = false; }}
    }}
    document.getElementById("test-connections").addEventListener("click", (event) => runAction(event.currentTarget, async () => {{
      const result = await postJson("/api/connection-test", {{
        vcenter: endpointPayload("vcenter"),
        prism: endpointPayload("prism"),
        require_vcenter: true,
        require_prism: true
      }});
      for (const check of result.result.checks || []) {{
        const status = document.querySelector(`[data-connection="${{check.name === "prism-central" ? "prism" : check.name}}"] [data-status]`);
        if (status) status.textContent = check.status;
      }}
    }}));
    document.getElementById("environment-access").addEventListener("click", (event) => runAction(event.currentTarget, async () => {{
      await postJson("/api/environment-access", environmentAccessPayload());
    }}));
    document.getElementById("collect-sources").addEventListener("click", (event) => runAction(event.currentTarget, async () => {{
      await postJson("/api/collect-sources", {{
        vcenter: endpointPayload("vcenter"),
        prism: endpointPayload("prism")
      }});
    }}));
    document.getElementById("run-readiness").addEventListener("click", (event) => runAction(event.currentTarget, async () => {{
      await postJson("/api/run-readiness", {{use_collected: true}});
    }}));
    document.getElementById("tester-report").addEventListener("click", (event) => runAction(event.currentTarget, async () => {{
      await postJson("/api/tester-report", {{}});
    }}));
    document.getElementById("copy-command").addEventListener("click", async () => {{
      const command = document.getElementById("run-command").value;
      try {{ await navigator.clipboard.writeText(command); }} catch (error) {{ void error; }}
    }});
  </script>
</body>
</html>
"""
    path.write_text(html_doc, encoding="utf-8")


def validate_operations_console(console_path: Path, assessment_path: Path) -> OperationsConsoleValidation:
    errors: list[str] = []
    warnings: list[str] = []
    checks = 0
    try:
        raw_text = console_path.read_text(encoding="utf-8")
    except OSError as exc:
        return OperationsConsoleValidation("fail", 1, (f"{console_path}: could not read operations console: {exc}",), ())
    try:
        assessment = json.loads(assessment_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return OperationsConsoleValidation("fail", 1, (f"{assessment_path}: could not read assessment JSON: {exc}",), ())
    text = html.unescape(raw_text)
    for required in REQUIRED_TEXT:
        checks += 1
        if required not in text:
            errors.append(f"Operations console missing required text: {required}")
    payload = extract_console_payload(raw_text, errors)
    checks += 1
    if not payload:
        return OperationsConsoleValidation("fail", checks, tuple(errors), tuple(warnings))
    checks += 1
    if payload.get("schema_version") != OPERATIONS_CONSOLE_SCHEMA_VERSION:
        errors.append(f"Operations console schema_version must be {OPERATIONS_CONSOLE_SCHEMA_VERSION}")
    summary = assessment.get("summary") if isinstance(assessment.get("summary"), dict) else {}
    console_summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    for key in ("total", "ready", "research", "prepare", "blocked"):
        checks += 1
        expected = int(summary.get(key) or 0)
        actual = int(console_summary.get(key) or 0)
        if actual != expected:
            errors.append(f"Operations console summary {key} expected {expected}, got {actual}")
        checks += 1
        label = "Workloads" if key == "total" else key.title()
        fragment = f'<div class="metric"><strong>{expected}</strong><span>{label}</span></div>'
        if fragment not in raw_text:
            errors.append(f"Operations console visible metric {label}={expected} is missing")
    workloads = payload.get("workloads") if isinstance(payload.get("workloads"), list) else []
    expected_count = len(assessment.get("assessments") if isinstance(assessment.get("assessments"), list) else [])
    checks += 1
    if len(workloads) != expected_count:
        errors.append(f"Operations console workload count expected {expected_count}, got {len(workloads)}")
    connections = payload.get("connections") if isinstance(payload.get("connections"), list) else []
    checks += 1
    if {item.get("id") for item in connections if isinstance(item, dict)} != {"vcenter", "prism", "move", "import"}:
        errors.append("Operations console must define vcenter, prism, move, and import connections")
    for leaked in ("vcenter01.corp.local", "migration.owner@example.com"):
        checks += 1
        if leaked in text:
            errors.append(f"Operations console leaked sample sensitive value: {leaked}")
    return OperationsConsoleValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def console_payload(inventory: dict[str, Any], assessments: list[WorkloadAssessment], waves: list[Wave]) -> dict[str, Any]:
    wave_by_workload = {workload_id: wave.name for wave in waves for workload_id in wave.workload_ids}
    return {
        "schema_version": OPERATIONS_CONSOLE_SCHEMA_VERSION,
        "summary": summarize(assessments),
        "connections": [
            {"id": "vcenter", "label": "vCenter", "mode": "read-only", "status": "not_configured"},
            {"id": "prism", "label": "Prism Central", "mode": "read-only", "status": "not_configured"},
            {"id": "move", "label": "Nutanix Move", "mode": "approved_lab_only", "status": "proof_required"},
            {"id": "import", "label": "RVTools / Import", "mode": "offline", "status": "available"},
        ],
        "waves": [{"name": wave.name, "workload_count": len(wave.workload_ids)} for wave in waves],
        "workloads": [
            {
                "id": assessment.workload_id,
                "name": assessment.name,
                "owner": assessment.owner or "Unassigned",
                "readiness": assessment.readiness,
                "risk_score": assessment.risk_score,
                "wave": wave_by_workload.get(assessment.workload_id, "Unassigned"),
                "move_action": "stage after review" if assessment.readiness in {"ready", "research"} else "hold until remediated",
                "top_finding": assessment.findings[0].message if assessment.findings else "No open finding",
            }
            for assessment in assessments
        ],
        "source": {"system": str(inventory.get("source", {}).get("system") or "redacted"), "workloads": len(assessments)},
    }


def summarize(assessments: list[WorkloadAssessment]) -> dict[str, int]:
    summary = {"ready": 0, "research": 0, "prepare": 0, "blocked": 0}
    for assessment in assessments:
        summary[assessment.readiness] = summary.get(assessment.readiness, 0) + 1
    summary["total"] = len(assessments)
    return summary


def connection_card(identifier: str, title: str, description: str) -> str:
    if identifier in {"move", "import"}:
        controls = [
            '        <label>Endpoint<input type="text" autocomplete="off" placeholder="Optional local reference" disabled></label>',
            "        <label>Mode<select disabled><option>Not connected by this step</option></select></label>",
        ]
    else:
        controls = [
            '        <label>Endpoint<input data-field="endpoint" type="text" autocomplete="off" placeholder="Approved endpoint URL"></label>',
            '        <label>Username<input data-field="username" type="text" autocomplete="username" placeholder="Read-only account"></label>',
            '        <label>Password<input data-field="credential" type="password" autocomplete="current-password" placeholder="Request-only credential"></label>',
            '        <label>TLS verification<input data-field="verify_tls" type="checkbox" checked></label>',
            '        <label>Timeout seconds<input data-field="timeout" type="number" min="1" value="20"></label>',
        ]
    lines = [
        f'      <article class="connection" data-connection="{escape(identifier)}">',
        f"        <h3>{escape(title)}</h3>",
        f'        <p class="muted">{escape(description)}</p>',
        *controls,
        '        <p class="meta">Status: <span data-status>Not configured</span></p>',
        "      </article>",
    ]
    return "\n".join(lines)


def metric(label: str, value: int) -> str:
    return f'<div class="metric"><strong>{escape(value)}</strong><span>{escape(label)}</span></div>'


def workload_row(row: dict[str, Any]) -> str:
    readiness = str(row["readiness"])
    return (
        f'<tr data-readiness="{escape(readiness)}" data-wave="{escape(row["wave"])}">'
        f'<td><strong>{escape(row["name"])}</strong><br><span class="muted">{escape(row["owner"])}</span></td>'
        f'<td><span class="pill {escape(readiness)}">{escape(readiness)}</span></td>'
        f'<td>{escape(row["risk_score"])}</td>'
        f'<td>{escape(row["wave"])}</td>'
        f'<td>{escape(row["move_action"])}</td>'
        f'<td>{escape(row["top_finding"])}</td>'
        "</tr>"
    )


def extract_console_payload(raw_text: str, errors: list[str]) -> dict[str, Any]:
    match = re.search(r'<script id="operations-console-data" type="application/json">(.*?)</script>', raw_text, flags=re.DOTALL)
    if not match:
        errors.append("Operations console missing operations-console-data JSON script")
        return {}
    try:
        payload = json.loads(html.unescape(match.group(1)))
    except json.JSONDecodeError as exc:
        errors.append(f"Operations console operations-console-data JSON is invalid: {exc}")
        return {}
    if not isinstance(payload, dict):
        errors.append("Operations console operations-console-data JSON must be an object")
        return {}
    return payload


def escape(value: Any) -> str:
    return html.escape(str(value), quote=True)


def script_json(payload: dict[str, Any]) -> str:
    return escape(json.dumps(payload, separators=(",", ":")))
