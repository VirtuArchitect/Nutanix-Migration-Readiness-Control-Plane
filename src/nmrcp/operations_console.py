from __future__ import annotations

import html
import json
import re
import base64
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import __version__
from .connectors import connector_capability_catalog
from .models import Wave, WorkloadAssessment
from .providers import provider_catalog


OPERATIONS_CONSOLE_SCHEMA_VERSION = "nmrcp_operations_console_v1"


def favicon_data_uri() -> str:
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <rect width="64" height="64" rx="14" fill="#1a2532"/>
  <rect x="18" y="18" width="28" height="28" fill="none" stroke="#20a5b8" stroke-width="6" transform="rotate(45 32 32)"/>
  <path d="M21 32 32 21" fill="none" stroke="#ffffff" stroke-width="6" stroke-linecap="square"/>
</svg>"""
    encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{encoded}"


REQUIRED_TEXT = (
    "<!doctype html>",
    "<title>NMRCP Operations Console</title>",
    'rel="icon"',
    "NMRCP logo favicon",
    "Migration Readiness Control Plane",
    "NMRCP",
    "MRCP",
    "Migration Readiness Control Plane",
    "Nutanix Provider Edition",
    "Provider Pair",
    "VMware vCenter -> Nutanix AHV",
    "Independent migration readiness console",
    "Version",
    "Environment Gate",
    "Connect Environments",
    "vCenter",
    "Prism Central",
    "Prism Element",
    "ESXi",
    "Nutanix Move",
    "RVTools / Import",
    "Environment Gates",
    "Test Connectivity",
    "Test Selected Connector",
    "Connectivity test result",
    "PASS",
    "FAILED",
    "Operator Summary",
    "Next step",
    "No infrastructure changes were made.",
    "Configure",
    "Run",
    "Expected output",
    "Open Environment Gates",
    "Open Connectors",
    "Open Migration Plans",
    "Browser-only preflight",
    "Test Read-only Connections",
    "Collect Source Evidence",
    "Run Readiness Assessment",
    "Prepare Tester Report",
    "Run Compatibility Analysis",
    "Build Move Plan",
    "Operator Workbench",
    "Operations Dashboard",
    "Environment Profiles",
    "Connector Policies",
    "Settings",
    "Users & RBAC",
    "Audit & State",
    "Add Connector",
    "Edit Connector",
    "Delete Connector",
    "Add User",
    "Edit User",
    "Delete User",
    "Add Role",
    "Create Migration Plan",
    "Edit Plan",
    "Delete Plan",
    "Run Dry Run",
    "nmrcp_connector_preflight_v1",
    "Local Operator",
    "Migration Operator",
    "Security Reviewer",
    "Credential Policy",
    "Retention",
    "/api/connection-test",
    "/api/collect-sources",
    "/api/run-readiness",
    "/api/tester-report",
    "/api/environment-access",
    "/api/state",
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
  <link rel="icon" type="image/svg+xml" href="{favicon_data_uri()}" aria-label="NMRCP logo favicon">
  <style>
    :root {{
      color-scheme: light;
      --ink: #17212b;
      --muted: #607080;
      --line: #d6dce4;
      --panel: #f6f8fa;
      --surface: #ffffff;
      --rail: #101721;
      --rail-2: #1a2532;
      --rail-muted: #a8b4c2;
      --accent: #14728c;
      --accent-strong: #0f5d73;
      --mark: #20a5b8;
      --gold: #b88718;
      --violet: #5b5f97;
      --ready: #18704b;
      --research: #7a6417;
      --prepare: #9a4d1c;
      --blocked: #a12a2a;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      font-size: 14px;
      line-height: 1.4;
      color: var(--ink);
      background: #edf1f4;
    }}
    .shell {{
      min-height: 100vh;
      display: grid;
      grid-template-columns: 260px minmax(0, 1fr);
    }}
    nav {{
      background: var(--rail);
      color: white;
      padding: 18px 16px;
      display: grid;
      align-content: start;
      gap: 16px;
      border-right: 1px solid #0b1118;
      box-shadow: 8px 0 24px rgba(17, 25, 35, .08);
    }}
    nav h1 {{
      font-size: 15px;
      line-height: 1.25;
      margin: 0;
    }}
    nav a {{
      display: block;
      width: 100%;
      color: var(--rail-muted);
      background: transparent;
      border: 0;
      text-decoration: none;
      padding: 8px 10px;
      border-radius: 6px;
      font-weight: 700;
      font-size: 13px;
      text-align: left;
      cursor: pointer;
    }}
    nav a:focus, nav a:hover, nav a.active {{
      color: white;
      background: rgba(255,255,255,.1);
      outline: 2px solid transparent;
    }}
    .brand {{
      width: 100%;
      border: 0;
      display: grid;
      grid-template-columns: 38px minmax(0, 1fr);
      gap: 10px;
      align-items: center;
      padding-bottom: 14px;
      border-bottom: 1px solid rgba(255,255,255,.12);
      background: transparent;
      color: inherit;
      text-align: left;
      cursor: pointer;
    }}
    .brand:focus, .brand:hover {{ outline: 2px solid rgba(32,165,184,.58); outline-offset: 3px; }}
    .brand-mark {{
      width: 38px;
      height: 38px;
      display: grid;
      place-items: center;
      border: 1px solid rgba(255,255,255,.18);
      border-radius: 8px;
      background: var(--rail-2);
      color: white;
      font-weight: 800;
      line-height: 1;
    }}
    .brand-mark span {{
      display: block;
      width: 18px;
      height: 18px;
      border: 3px solid var(--mark);
      border-left-color: white;
      transform: rotate(45deg);
    }}
    .brand small {{
      display: block;
      color: var(--rail-muted);
      font-size: 11px;
      line-height: 1.25;
      margin-top: 3px;
    }}
    .edition-tag {{
      display: inline-block;
      margin-top: 7px;
      border: 1px solid rgba(32,165,184,.38);
      border-radius: 999px;
      padding: 3px 7px;
      color: white;
      background: rgba(32,165,184,.16);
      font-size: 10.5px;
      font-weight: 800;
      line-height: 1;
    }}
    .rail-section {{
      display: grid;
      gap: 4px;
    }}
    .rail-status {{
      border: 1px solid rgba(255,255,255,.12);
      border-radius: 8px;
      background: var(--rail-2);
      padding: 10px;
      color: var(--rail-muted);
      font-size: 12px;
      line-height: 1.35;
    }}
    .rail-status strong {{
      display: block;
      color: white;
      margin-bottom: 3px;
      font-size: 12px;
    }}
    main {{
      min-width: 0;
      display: grid;
      grid-template-rows: auto minmax(0, 1fr);
    }}
    header {{
      border-bottom: 1px solid var(--line);
      padding: 14px 22px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: center;
      background: var(--surface);
    }}
    .eyebrow {{
      color: var(--accent-strong);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    h2, h3, p {{ margin-top: 0; }}
    h2 {{ font-size: 17px; line-height: 1.25; margin-bottom: 12px; }}
    h3 {{ font-size: 13px; line-height: 1.25; margin-bottom: 8px; }}
    .content {{
      padding: 18px 22px 28px;
      display: grid;
      gap: 16px;
      align-content: start;
    }}
    .page {{
      display: none;
      gap: 16px;
      align-content: start;
    }}
    .page.active {{
      display: grid;
    }}
    .page-title {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: end;
      border-bottom: 1px solid var(--line);
      padding-bottom: 10px;
    }}
    .page-title h2 {{ margin-bottom: 0; }}
    .ops-ribbon {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
      border: 1px solid var(--line);
      border-left: 4px solid var(--accent);
      border-radius: 8px;
      background: var(--surface);
      padding: 10px 12px;
    }}
    .provider-band {{
      display: grid;
      grid-template-columns: minmax(190px, 1fr) auto minmax(190px, 1fr);
      gap: 10px;
      align-items: stretch;
    }}
    .provider-node, .provider-arrow {{
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      padding: 12px 14px;
      min-height: 78px;
    }}
    .provider-node span {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .provider-node strong {{
      display: block;
      margin-top: 4px;
      font-size: 16px;
      line-height: 1.2;
    }}
    .provider-node small {{
      display: block;
      margin-top: 4px;
      color: var(--muted);
      font-size: 12px;
      line-height: 1.25;
    }}
    .provider-arrow {{
      display: grid;
      place-items: center;
      min-width: 54px;
      color: var(--accent-strong);
      font-weight: 900;
      font-size: 20px;
    }}
    .ops-ribbon span {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      font-weight: 800;
      text-transform: uppercase;
    }}
    .ops-ribbon strong {{
      display: block;
      margin-top: 2px;
      font-size: 13px;
    }}
    .status-strip {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
      gap: 10px;
    }}
    .metric, .connection, .panel, .ops-card {{
      border: 1px solid var(--line);
      border-radius: 7px;
      background: white;
      box-shadow: 0 1px 2px rgba(20, 32, 44, .04);
    }}
    .metric {{ padding: 10px 12px; }}
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
    .connection h3 {{
      margin-bottom: 0;
      font-size: 14px;
    }}
    .connection .meta {{
      border-top: 1px solid var(--line);
      padding-top: 8px;
      margin-bottom: 0;
      font-weight: 700;
    }}
    .connection-status {{
      display: flex;
      align-items: center;
      gap: 7px;
      border-top: 1px solid var(--line);
      padding-top: 8px;
      margin-bottom: 0;
      color: var(--muted);
      font-weight: 700;
    }}
    .result-badge {{
      display: inline-block;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 4px 8px;
      min-width: 64px;
      text-align: center;
      color: var(--ink);
      background: #f7f9fb;
      font-size: 11px;
      line-height: 1;
      font-weight: 900;
      text-transform: uppercase;
      white-space: nowrap;
    }}
    .result-badge.pass {{
      border-color: rgba(24,112,75,.35);
      color: white;
      background: var(--ready);
    }}
    .result-badge.fail, .result-badge.failed {{
      border-color: rgba(161,42,42,.35);
      color: white;
      background: var(--blocked);
    }}
    .result-badge.warn {{
      border-color: rgba(184,135,24,.35);
      color: #5f4709;
      background: #fff5cc;
    }}
    .connection-actions {{
      display: flex;
      gap: 8px;
      align-items: center;
    }}
    .connection-actions button {{
      width: 100%;
      padding: 7px 9px;
      font-size: 12px;
    }}
    .connection-result {{
      border: 1px solid var(--line);
      border-radius: 6px;
      background: #f9fbfc;
      padding: 8px;
      min-height: 48px;
      color: var(--muted);
      font-family: Consolas, "Liberation Mono", monospace;
      font-size: 11.5px;
      line-height: 1.3;
      white-space: pre-wrap;
    }}
    label {{ display: grid; gap: 5px; font-size: 12px; line-height: 1.25; font-weight: 700; }}
    input, select, textarea {{
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 5px;
      padding: 8px 9px;
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
      border-radius: 5px;
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
    .panel {{ padding: 13px; }}
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
      color: var(--ink);
    }}
    .table-wrap {{
      border: 1px solid var(--line);
      border-radius: 7px;
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
      border-radius: 7px;
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
    .workflow-steps {{
      counter-reset: workflow;
    }}
    .workflow-step {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) auto;
      gap: 12px;
      align-items: start;
    }}
    .workflow-step strong {{
      display: block;
      margin-bottom: 6px;
      font-size: 13px;
    }}
    .workflow-step dl {{
      display: grid;
      grid-template-columns: 92px minmax(0, 1fr);
      gap: 5px 10px;
      margin: 0;
      color: var(--ink);
    }}
    .workflow-step dt {{
      color: var(--muted);
      font-weight: 800;
    }}
    .workflow-step dd {{
      margin: 0;
      color: var(--ink);
    }}
    .workflow-step button {{
      min-width: 150px;
      padding: 7px 9px;
      font-size: 12px;
    }}
    .actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      align-items: center;
    }}
    .nav-label {{
      color: var(--rail-muted);
      font-size: 10.5px;
      font-weight: 800;
      letter-spacing: .04em;
      text-transform: uppercase;
      margin: 6px 10px 2px;
    }}
    .ops-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
      gap: 12px;
    }}
    .ops-card {{
      padding: 13px;
      display: grid;
      gap: 8px;
      align-content: start;
      min-height: 118px;
    }}
    .ops-card h3 {{
      margin-bottom: 0;
      font-size: 14px;
    }}
    .kvs {{
      display: grid;
      gap: 6px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .kvs li {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      border-top: 1px solid var(--line);
      padding-top: 6px;
      font-size: 12.5px;
      line-height: 1.25;
    }}
    .kvs span:first-child {{
      color: var(--muted);
      font-weight: 700;
    }}
    .ops-table {{
      min-width: 680px;
    }}
    .status-chip {{
      display: inline-block;
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 3px 7px;
      background: #f7f9fb;
      color: var(--ink);
      font-size: 11px;
      font-weight: 800;
      line-height: 1;
      white-space: nowrap;
    }}
    .status-chip.good {{
      border-color: rgba(24,112,75,.28);
      color: var(--ready);
      background: rgba(24,112,75,.08);
    }}
    .status-chip.warn {{
      border-color: rgba(184,135,24,.28);
      color: var(--gold);
      background: rgba(184,135,24,.08);
    }}
    .status-chip.blocked {{
      border-color: rgba(161,42,42,.25);
      color: var(--blocked);
      background: rgba(161,42,42,.08);
    }}
    .admin-band {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 340px);
      gap: 14px;
      align-items: start;
    }}
    .form-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
      gap: 10px;
      align-items: end;
      margin-bottom: 12px;
    }}
    .toolbar {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 12px;
      align-items: center;
    }}
    .toolbar button {{
      padding: 7px 9px;
      font-size: 12px;
    }}
    .danger {{
      border-color: var(--blocked);
      background: var(--blocked);
    }}
    .managed-output {{
      border: 1px solid var(--line);
      border-radius: 7px;
      background: #f9fbfc;
      min-height: 84px;
      padding: 10px;
      font-size: 12.5px;
      line-height: 1.45;
      overflow: auto;
    }}
    .managed-output pre {{
      margin: 8px 0 0;
      padding-top: 8px;
      border-top: 1px solid var(--line);
      font-family: Consolas, "Liberation Mono", monospace;
      font-size: 11.5px;
      line-height: 1.35;
      white-space: pre-wrap;
    }}
    .operator-summary {{
      display: grid;
      gap: 8px;
    }}
    .operator-summary h4 {{
      margin: 0;
      font-size: 13px;
      line-height: 1.2;
    }}
    .operator-summary ul {{
      margin: 0;
      padding-left: 18px;
    }}
    .operator-summary li {{
      margin: 2px 0;
    }}
    .operator-summary .summary-head {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}
    .check-list {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 8px;
      margin-bottom: 12px;
    }}
    .check-list label {{
      display: flex;
      align-items: center;
      gap: 7px;
      min-height: 28px;
      color: var(--ink);
      font-weight: 600;
    }}
    .proof {{
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--panel);
      padding: 12px;
      min-height: 120px;
      white-space: pre-wrap;
      overflow: auto;
      font-size: 12px;
      font-family: Consolas, "Liberation Mono", monospace;
      line-height: 1.35;
    }}
    .state-summary {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin-top: 10px;
    }}
    .state-summary div {{
      border: 1px solid var(--line);
      border-radius: 7px;
      padding: 9px;
      background: #fff;
    }}
    .state-summary span {{
      display: block;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
    }}
    .state-summary strong {{
      display: block;
      margin-top: 3px;
      font-size: 14px;
    }}
    @media (max-width: 960px) {{
      .shell, .workbench {{ display: block; }}
      .content {{ padding: 18px; }}
      .filters {{ grid-template-columns: 1fr; }}
      .provider-band {{ grid-template-columns: 1fr; }}
      .provider-arrow {{ min-height: 38px; }}
      .admin-band {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>
  <div class="shell">
    <nav aria-label="Primary">
      <button class="brand" type="button" data-page-link="dashboard" aria-label="Open Operations Dashboard">
        <div class="brand-mark" aria-hidden="true"><span></span></div>
        <div>
          <h1>NMRCP</h1>
          <small>MRCP - Nutanix Provider Edition</small>
          <span class="edition-tag">Nutanix Provider Edition</span>
        </div>
      </button>
      <div class="rail-section">
        <div class="nav-label">Operate</div>
        <a href="?page=dashboard" data-page-link="dashboard">Operations Dashboard</a>
        <a href="?page=connect" data-page-link="connect">Connect Environments</a>
        <a href="?page=environment-profiles" data-page-link="environment-profiles">Environment Profiles</a>
        <a href="?page=connector-policies" data-page-link="connector-policies">Connector Policies</a>
        <a href="?page=analyze" data-page-link="analyze">Run Compatibility Analysis</a>
        <a href="?page=plan" data-page-link="plan">Build Move Plan</a>
        <a href="?page=workbench" data-page-link="workbench">Operator Workbench</a>
        <div class="nav-label">Admin</div>
        <a href="?page=settings" data-page-link="settings">Settings</a>
        <a href="?page=users-rbac" data-page-link="users-rbac">Users &amp; RBAC</a>
        <a href="?page=audit-state" data-page-link="audit-state">Audit &amp; State</a>
      </div>
      <div class="rail-status"><strong>Provider Pair</strong>{escape(payload["provider_pair"]["source_label"])} -> {escape(payload["provider_pair"]["target_label"])}<br>Version {escape(payload["product_version"])}. Environment connections are local-only and require explicit operator approval.</div>
    </nav>
    <main>
      <header>
        <div>
          <div class="eyebrow">Independent migration readiness console</div>
          <h2>Migration Readiness Control Plane</h2>
          <p class="muted">Nutanix Provider Edition for source discovery, compatibility analysis, wave planning, and evidence review.</p>
        </div>
        <button type="button" class="secondary" id="copy-command">Copy Run Command</button>
      </header>
      <section class="content">
        <section class="page active" id="page-dashboard" data-page="dashboard" aria-labelledby="title-dashboard">
          <div class="page-title"><h2 id="title-dashboard">Operations Dashboard</h2><span class="status-chip good">Active</span></div>
          <section class="ops-ribbon" aria-label="Operations context">
            <div><span>Identity</span><strong>MRCP Console</strong></div>
            <div><span>Edition</span><strong>Nutanix Provider Edition</strong></div>
            <div><span>Version</span><strong>{escape(payload["product_version"])}</strong></div>
            <div><span>Mode</span><strong>Local-first evidence workflow</strong></div>
            <div><span>Boundary</span><strong>Write intent is gated, not executed</strong></div>
          </section>
          <section class="provider-band" aria-label="Provider Pair">
            <div class="provider-node"><span>Source Provider</span><strong>{escape(payload["provider_pair"]["source_label"])}</strong><small>{escape(payload["provider_pair"]["source_status"])} collector</small></div>
            <div class="provider-arrow" aria-hidden="true">-></div>
            <div class="provider-node"><span>Target Provider</span><strong>{escape(payload["provider_pair"]["target_label"])}</strong><small>{escape(payload["provider_pair"]["rule_set_label"])}</small></div>
          </section>
          <section class="status-strip" aria-label="Readiness summary">
            {metric("Workloads", payload["summary"]["total"])}
            {metric("Ready", payload["summary"]["ready"])}
            {metric("Research", payload["summary"]["research"])}
            {metric("Prepare", payload["summary"]["prepare"])}
            {metric("Blocked", payload["summary"]["blocked"])}
            {metric("Waves", len(payload["waves"]))}
          </section>
          <div class="ops-grid">
            <article class="ops-card">
              <h3>Current Workspace</h3>
              <ul class="kvs">
                <li><span>Auth mode</span><strong>{escape(payload["rbac"]["auth_mode"])}</strong></li>
                <li><span>Data boundary</span><strong>{escape(payload["settings"]["data_boundary"])}</strong></li>
                <li><span>Default access</span><strong>{escape(payload["settings"]["default_access"])}</strong></li>
              </ul>
            </article>
            <article class="ops-card">
              <h3>Operational Readiness</h3>
              <ul class="kvs">
                <li><span>Connectors</span><strong>{len(payload["connector_policies"])}</strong></li>
                <li><span>Environments</span><strong>{len(payload["environment_profiles"])}</strong></li>
                <li><span>Roles</span><strong>{len(payload["rbac"]["roles"])}</strong></li>
              </ul>
            </article>
            <article class="ops-card">
              <h3>Control Status</h3>
              <ul class="kvs">
                <li><span>Credential Policy</span><strong>No persistence</strong></li>
                <li><span>Write mode</span><strong>Gate validation</strong></li>
                <li><span>Audit trail</span><strong>Local state</strong></li>
              </ul>
            </article>
          </div>
        </section>
        <section class="page" id="page-connect" data-page="connect" aria-labelledby="title-connect">
          <div class="page-title"><h2 id="title-connect">Connect Environments</h2><span class="status-chip warn">Local API required</span></div>
          <div class="connections">
            {connection_card("vcenter", "vCenter", "Read-only VM, network, guest, tools, snapshot, and dependency source.")}
            {connection_card("prism", "Prism Central", "Read-only AHV/NC2 target inventory, capacity, categories, and collision checks.")}
            {connection_card("prism-element", "Prism Element", "Read-only AHV cluster, host, storage, network, and VM context.")}
            {connection_card("move", "Nutanix Move", "Approved lab-only payload review and dry-run proof capture.")}
            {connection_card("esxi", "ESXi", "Host-level connectivity gate for approved read or write-intent workflows.")}
            {connection_card("import", "RVTools / Import", "Offline CSV/JSON intake for discovery when live endpoints are not approved.")}
          </div>
          <div class="panel">
            <h3>Tester Connection Workflow</h3>
            <div class="filters" aria-label="Environment gates">
              <label>Environment<select id="environment-select"><option value="dev">Dev</option><option value="uat">UAT</option><option value="production">Production</option></select></label>
              <label>Mode<select id="mode-select"><option value="read">Read</option><option value="write">Write intent</option></select></label>
              <label>Target<select id="target-select"><option value="pc">Prism Central</option><option value="pe">Prism Element</option><option value="move">Nutanix Move</option><option value="vcenter">vCenter</option><option value="esxi">ESXi</option></select></label>
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
              <label><input type="checkbox" data-gate="cluster_admin_scope">Cluster admin scope</label>
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
              <button type="button" id="refresh-state" class="secondary">Refresh Local State</button>
            </div>
            <p class="hint">These buttons call /api/environment-access, /api/connection-test, /api/collect-sources, /api/run-readiness, /api/tester-report, and /api/state on this local console server. Open the served local console URL printed by nmrcp serve, not the static file or GitHub Pages demo, when testing real endpoints. Passwords are sent only to the local process for the active request and are not written to proof files. For Dev or UAT labs with self-signed Nutanix certificates, import the lab CA or clear TLS verification for that test; Production should use trusted certificates. Write intent validates gates only; this workflow does not execute mutating actions.</p>
            <div class="state-summary" aria-label="Local state summary">
              <div><span>Profiles</span><strong id="state-profiles">0</strong></div>
              <div><span>Runs</span><strong id="state-runs">0</strong></div>
              <div><span>Evidence</span><strong id="state-evidence">0</strong></div>
            </div>
            <div class="proof" id="api-proof" role="status" aria-live="polite">Ready for tester input. API actions require the local nmrcp serve console. Use secure endpoints unless you are testing against a loopback simulator.</div>
          </div>
        </section>
        <section class="page" id="page-environment-profiles" data-page="environment-profiles" aria-labelledby="title-environment-profiles">
          <div class="page-title"><h2 id="title-environment-profiles">Environment Profiles</h2><span class="status-chip good">Dev / UAT / Production</span></div>
          <div class="table-wrap">
            <table class="ops-table">
              <thead><tr><th>Environment</th><th>Purpose</th><th>Read Gate</th><th>Write Gate</th><th>Default Targets</th></tr></thead>
              <tbody>{environment_profile_rows(payload["environment_profiles"])}</tbody>
            </table>
          </div>
        </section>
        <section class="page" id="page-connector-policies" data-page="connector-policies" aria-labelledby="title-connector-policies">
          <div class="page-title"><h2 id="title-connector-policies">Connector Policies</h2><span class="status-chip blocked">Mutation disabled</span></div>
          <div class="panel">
            <h3>Add / Edit / Delete Connectors</h3>
            <div class="form-grid">
              <label>Connector Name<input id="connector-name" type="text" autocomplete="off" placeholder="Lab Prism Central"></label>
              <label>Type<select id="connector-type"><option>vCenter</option><option>Prism Central</option><option>Prism Element</option><option>Nutanix Move</option><option>ESXi</option><option>RVTools / Import</option></select></label>
              <label>Environment<select id="connector-environment"><option>Dev</option><option>UAT</option><option>Production</option></select></label>
              <label>Mode<select id="connector-mode"><option>read</option><option>write_intent</option><option>offline</option><option>gate</option></select></label>
              <label>Status<select id="connector-status"><option>not_configured</option><option>ready</option><option>proof_required</option><option>disabled</option></select></label>
            </div>
            <div class="toolbar">
              <button type="button" id="add-connector">Add Connector</button>
              <button type="button" id="edit-connector" class="secondary">Edit Connector</button>
              <button type="button" id="test-selected-connector" class="secondary">Test Selected Connector</button>
              <button type="button" id="delete-connector" class="danger">Delete Connector</button>
            </div>
            <div class="table-wrap">
              <table class="ops-table">
                <thead><tr><th>Select</th><th>Name</th><th>Type</th><th>Environment</th><th>Mode</th><th>Status</th><th>Last Test</th><th>Action</th></tr></thead>
                <tbody id="managed-connectors"></tbody>
              </table>
            </div>
            <div class="managed-output" id="connector-test-output">Connectivity test result: Not run. Select a connector or use a card-level Test Connectivity button.</div>
          </div>
          <div class="table-wrap">
            <table class="ops-table">
              <thead><tr><th>Connector</th><th>Modes</th><th>Write</th><th>Credential Policy</th><th>Status</th></tr></thead>
              <tbody>{connector_policy_rows(payload["connector_policies"])}</tbody>
            </table>
          </div>
        </section>
        <section class="page" id="page-analyze" data-page="analyze" aria-labelledby="title-analyze">
          <div class="panel">
            <div class="page-title"><h2 id="title-analyze">Run Compatibility Analysis</h2><span class="status-chip good">Assessment loaded</span></div>
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
        </section>
        <section class="page" id="page-plan" data-page="plan" aria-labelledby="title-plan">
          <div class="panel">
            <div class="page-title"><h2 id="title-plan">Build Move Plan</h2><span class="status-chip warn">Stage after review</span></div>
            <h3>Create Migration Plan</h3>
            <div class="form-grid">
              <label>Plan Name<input id="plan-name" type="text" autocomplete="off" value="Pilot AHV readiness plan"></label>
              <label>Environment<select id="plan-environment"><option>Dev</option><option>UAT</option><option>Production</option></select></label>
              <label>Target<select id="plan-target"><option>Nutanix AHV</option><option>NC2</option><option>Nutanix Move Lab</option></select></label>
              <label>Wave<select id="plan-wave"></select></label>
            </div>
            <div class="check-list" id="plan-workloads" aria-label="Plan workloads"></div>
            <div class="toolbar">
              <button type="button" id="create-plan">Create Migration Plan</button>
              <button type="button" id="edit-plan" class="secondary">Edit Plan</button>
              <button type="button" id="run-dry-run" class="secondary">Run Dry Run</button>
              <button type="button" id="delete-plan" class="danger">Delete Plan</button>
            </div>
            <div class="table-wrap">
              <table class="ops-table">
                <thead><tr><th>Select</th><th>Plan</th><th>Environment</th><th>Target</th><th>Wave</th><th>Workloads</th><th>Status</th></tr></thead>
                <tbody id="managed-plans"></tbody>
              </table>
            </div>
            <h3>Dry Run Output</h3>
            <div class="managed-output" id="dry-run-output">No dry run executed in this browser session.</div>
            <ol class="steps">
              <li><strong>1. Confirm included workloads</strong><br><span class="muted">Only ready or researched workloads should be staged for downstream Move planning.</span></li>
              <li><strong>2. Review network and capacity fit</strong><br><span class="muted">Validate target network mapping, Prism capacity, and held workload conflicts before handoff.</span></li>
              <li><strong>3. Export planning command</strong><br><span class="muted">Use the local command below to regenerate evidence and Move planning artifacts.</span></li>
            </ol>
            <h3>Generated local command</h3>
            <textarea id="run-command" spellcheck="false">python -m nmrcp.cli run-assessment --inventory examples/sample_inventory.json --metadata examples/sample_metadata.csv --dependencies examples/sample_dependencies.csv --move-config examples/sample_move_payload_config.json --out outputs/assessment</textarea>
            <p class="hint">Do not store credentials in the console or generated artifacts. Use approved read-only collection before claiming endpoint proof. Use approved Nutanix Move lab evidence before external handoff.</p>
          </div>
        </section>
        <section class="page" id="page-workbench" data-page="workbench" aria-labelledby="title-workbench">
          <div class="panel">
            <div class="page-title"><h2 id="title-workbench">Operator Workbench</h2><span class="status-chip good">Workflow</span></div>
            <ol class="steps workflow-steps">
              <li class="workflow-step">
                <div><strong>1. Select environment</strong><dl><dt>Configure</dt><dd>Choose Dev, UAT, or Production, target, mode, and required gates.</dd><dt>Run</dt><dd>Validate Environment Gates.</dd><dt>Expected output</dt><dd>PASS means the selected workflow is allowed to continue; FAILED lists missing gates.</dd></dl></div>
                <button type="button" class="secondary" data-page-link="connect">Open Environment Gates</button>
              </li>
              <li class="workflow-step">
                <div><strong>2. Connect source and target</strong><dl><dt>Configure</dt><dd>Enter approved endpoint, username, request-only password, TLS mode, and timeout for PC, PE, or vCenter.</dd><dt>Run</dt><dd>Test Connectivity on each connector card.</dd><dt>Expected output</dt><dd>Green PASS confirms authenticated read-only API proof; red FAILED explains TLS, auth, or API errors.</dd></dl></div>
                <button type="button" class="secondary" data-page-link="connect">Open Connectors</button>
              </li>
              <li class="workflow-step">
                <div><strong>3. Discover inventory</strong><dl><dt>Configure</dt><dd>Use tested vCenter and Prism Central connectors, or import RVTools/offline inventory.</dd><dt>Run</dt><dd>Collect Source Evidence.</dd><dt>Expected output</dt><dd>Operator summary shows collected artifacts, inventory counts, and redacted evidence paths.</dd></dl></div>
                <button type="button" class="secondary" data-page-link="connect">Open Collection</button>
              </li>
              <li class="workflow-step">
                <div><strong>4. Analyze compatibility</strong><dl><dt>Configure</dt><dd>Filter readiness by workload, owner, finding, readiness state, or wave.</dd><dt>Run</dt><dd>Review blockers, dependencies, top finding, and move action.</dd><dt>Expected output</dt><dd>Only ready or researched workloads should proceed into migration planning.</dd></dl></div>
                <button type="button" class="secondary" data-page-link="analyze">Open Analysis</button>
              </li>
              <li class="workflow-step" id="plan">
                <div><strong>5. Build migration plan</strong><dl><dt>Configure</dt><dd>Name the plan, select environment, target, wave, and included workloads.</dd><dt>Run</dt><dd>Create Migration Plan, then Run Dry Run.</dd><dt>Expected output</dt><dd>Dry-run summary confirms workload count, target, mutation disabled, and next review step.</dd></dl></div>
                <button type="button" class="secondary" data-page-link="plan">Open Migration Plans</button>
              </li>
              <li class="workflow-step">
                <div><strong>6. Package tester feedback</strong><dl><dt>Configure</dt><dd>Complete connection tests, collection, readiness, and environment gate review.</dd><dt>Run</dt><dd>Prepare Tester Report.</dd><dt>Expected output</dt><dd>Redacted report and JSON paths for GitHub tester feedback, with no credentials persisted.</dd></dl></div>
                <button type="button" class="secondary" data-page-link="connect">Open Tester Actions</button>
              </li>
            </ol>
          </div>
        </section>
        <section class="page" id="page-settings" data-page="settings" aria-labelledby="title-settings">
          <div class="panel">
            <div class="page-title"><h2 id="title-settings">Settings</h2><span class="status-chip warn">Local alpha</span></div>
            <div class="ops-grid">
              {settings_cards(payload["settings"])}
            </div>
          </div>
        </section>
        <section class="page" id="page-users-rbac" data-page="users-rbac" aria-labelledby="title-users-rbac">
          <div class="panel">
            <div class="page-title"><h2 id="title-users-rbac">Users &amp; RBAC</h2><span class="status-chip good">Role model</span></div>
            <h3>Add / Edit / Delete Users</h3>
            <div class="form-grid">
              <label>User Name<input id="user-name" type="text" autocomplete="off" placeholder="Migration Reviewer"></label>
              <label>Role<select id="user-role"></select></label>
              <label>Scope<input id="user-scope" type="text" autocomplete="off" placeholder="Dev and UAT evidence"></label>
              <label>Status<select id="user-status"><option>active</option><option>configured</option><option>disabled</option></select></label>
            </div>
            <div class="toolbar">
              <button type="button" id="add-user">Add User</button>
              <button type="button" id="edit-user" class="secondary">Edit User</button>
              <button type="button" id="delete-user" class="danger">Delete User</button>
            </div>
            <div class="table-wrap">
              <table class="ops-table">
                <thead><tr><th>Select</th><th>User</th><th>Role</th><th>Scope</th><th>Status</th></tr></thead>
                <tbody id="managed-users"></tbody>
              </table>
            </div>
            <h3>Add Role</h3>
            <div class="form-grid">
              <label>Role Name<input id="role-name" type="text" autocomplete="off" placeholder="Migration Approver"></label>
              <label>Allowed Work<input id="role-allowed" type="text" autocomplete="off" placeholder="Approve UAT migration plans"></label>
            </div>
            <div class="toolbar">
              <button type="button" id="add-role">Add Role</button>
            </div>
            <div class="table-wrap">
              <table class="ops-table">
                <thead><tr><th>Role</th><th>Allowed Work</th></tr></thead>
                <tbody id="managed-roles"></tbody>
              </table>
            </div>
          </div>
        </section>
        <section class="page" id="page-audit-state" data-page="audit-state" aria-labelledby="title-audit-state">
          <div>
            <div class="page-title"><h2 id="title-audit-state">Audit &amp; State</h2><span class="status-chip good">Local state</span></div>
          </div>
          <aside class="panel">
            <ul class="kvs">
              <li><span>State file</span><strong>console-state.json</strong></li>
              <li><span>Run history</span><strong>Last 50 actions</strong></li>
              <li><span>Evidence index</span><strong>Last 100 artifacts</strong></li>
              <li><span>Raw inventory</span><strong>Not stored in state</strong></li>
            </ul>
            <h3>Role Model</h3>
            <div class="table-wrap">
              <table>
                <thead><tr><th>Role</th><th>Allowed Work</th></tr></thead>
                <tbody>{rbac_role_rows(payload["rbac"]["roles"])}</tbody>
              </table>
            </div>
          </aside>
        </section>
      </section>
    </main>
  </div>
  <script id="operations-console-data" type="application/json">{script_json(payload)}</script>
  <script>
    function embeddedJson(id) {{
      const decoder = document.createElement("textarea");
      decoder.innerHTML = document.getElementById(id).textContent;
      return JSON.parse(decoder.value);
    }}
    const payload = embeddedJson("operations-console-data");
    const pageTitles = {{
      "dashboard": "Operations Dashboard",
      "connect": "Connect Environments",
      "environment-profiles": "Environment Profiles",
      "connector-policies": "Connector Policies",
      "analyze": "Run Compatibility Analysis",
      "plan": "Build Move Plan",
      "workbench": "Operator Workbench",
      "settings": "Settings",
      "users-rbac": "Users & RBAC",
      "audit-state": "Audit & State"
    }};
    function showPage(page, updateUrl = true) {{
      const pageName = pageTitles[page] ? page : "dashboard";
      for (const panel of document.querySelectorAll("[data-page]")) {{
        panel.classList.toggle("active", panel.dataset.page === pageName);
      }}
      for (const link of document.querySelectorAll("[data-page-link]")) {{
        link.classList.toggle("active", link.dataset.pageLink === pageName);
        if (link.tagName === "A") {{
          link.setAttribute("aria-current", link.dataset.pageLink === pageName ? "page" : "false");
        }}
      }}
      document.title = `${{pageTitles[pageName]}} - NMRCP Operations Console`;
      if (updateUrl) {{
        const url = new URL(window.location.href);
        url.searchParams.set("page", pageName);
        history.pushState({{page: pageName}}, "", url);
      }}
      window.scrollTo({{top: 0, left: 0, behavior: "instant"}});
    }}
    for (const link of document.querySelectorAll("[data-page-link]")) {{
      link.addEventListener("click", (event) => {{
        event.preventDefault();
        showPage(event.currentTarget.dataset.pageLink);
      }});
    }}
    window.addEventListener("popstate", (event) => {{
      const page = event.state && event.state.page ? event.state.page : new URL(window.location.href).searchParams.get("page");
      showPage(page || "dashboard", false);
    }});
    showPage(new URL(window.location.href).searchParams.get("page") || "dashboard", false);
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
      const endpoint = card.querySelector("[data-field='endpoint']");
      const username = card.querySelector("[data-field='username']");
      const credential = card.querySelector("[data-field='credential']");
      const verifyTls = card.querySelector("[data-field='verify_tls']");
      const timeout = card.querySelector("[data-field='timeout']");
      return {{
        endpoint: endpoint ? endpoint.value.trim() : "",
        username: username ? username.value.trim() : "",
        credential: credential ? credential.value : "",
        verify_tls: verifyTls ? verifyTls.checked : true,
        timeout_seconds: Number(timeout ? timeout.value || 20 : 20)
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
    function clearNode(node) {{
      while (node.firstChild) node.removeChild(node.firstChild);
    }}
    function appendText(parent, tag, text, className = "") {{
      const node = document.createElement(tag);
      if (className) node.className = className;
      node.textContent = text;
      parent.appendChild(node);
      return node;
    }}
    function appendBadge(parent, status) {{
      const badge = document.createElement("span");
      setStatusBadge(badge, status);
      parent.appendChild(badge);
      return badge;
    }}
    function formatCounts(counts) {{
      const entries = Object.entries(counts || {{}}).filter(([, value]) => value !== undefined && value !== null);
      if (!entries.length) return "No inventory counts returned.";
      return entries.map(([key, value]) => `${{key.replaceAll("_", " ")}}: ${{value}}`).join(", ");
    }}
    function evidenceLine(payload) {{
      const paths = [payload.proof, payload.report, payload.json_report, payload.source_dir, payload.assessment_dir].filter(Boolean);
      return paths.length ? `Evidence: ${{paths.join("; ")}}` : "Evidence: no artifact path returned.";
    }}
    function renderOperatorSummary(target, options) {{
      clearNode(target);
      const wrapper = document.createElement("div");
      wrapper.className = "operator-summary";
      const head = document.createElement("div");
      head.className = "summary-head";
      appendBadge(head, options.status || "not_configured");
      appendText(head, "h4", options.title || "Operator Summary");
      wrapper.appendChild(head);
      const list = document.createElement("ul");
      for (const item of options.items || []) {{
        appendText(list, "li", item);
      }}
      wrapper.appendChild(list);
      if (options.detail) appendText(wrapper, "p", options.detail, "muted");
      if (options.evidence) {{
        const evidence = document.createElement("pre");
        evidence.textContent = options.evidence;
        wrapper.appendChild(evidence);
      }}
      target.appendChild(wrapper);
    }}
    function showProofSummary(payload, title = "Operator Summary") {{
      const target = document.getElementById("api-proof");
      const status = payload.status || "unknown";
      const items = [];
      if (Array.isArray(payload.errors)) {{
        for (const error of payload.errors) items.push(`Error: ${{error}}`);
      }}
      if (Array.isArray(payload.blockers)) {{
        for (const blocker of payload.blockers) items.push(`Blocker: ${{blocker}}`);
      }}
      if (payload.result && Array.isArray(payload.result.checks)) {{
        for (const check of payload.result.checks) {{
          items.push(`${{check.name}}: ${{statusLabel(check.status)}}; ${{formatCounts(check.counts)}}`);
        }}
      }}
      if (payload.missing_gates && payload.missing_gates.length) {{
        items.push(`Missing gates: ${{payload.missing_gates.join(", ")}}`);
      }}
      if (payload.summary && typeof payload.summary === "object") {{
        for (const [key, value] of Object.entries(payload.summary)) {{
          if (typeof value !== "object") items.push(`${{key.replaceAll("_", " ")}}: ${{value}}`);
        }}
      }}
      if (!items.length) items.push("Action completed; review the evidence path and state counters.");
      renderOperatorSummary(target, {{
        status,
        title,
        items,
        detail: "No infrastructure changes were made.",
        evidence: evidenceLine(payload)
      }});
    }}
    function showErrorSummary(error) {{
      let payload = null;
      try {{ payload = JSON.parse(error.message); }} catch (parseError) {{ void parseError; }}
      if (payload && typeof payload === "object") {{
        showProofSummary(payload, "Action failed");
        return;
      }}
      renderOperatorSummary(document.getElementById("api-proof"), {{
        status: "fail",
        title: "Action failed",
        items: [error.message],
        detail: "No infrastructure changes were made."
      }});
    }}
    function connectionIdForCheck(name) {{
      if (name === "prism-central") return "prism";
      if (name === "prism-element") return "prism-element";
      return name;
    }}
    function statusLabel(status) {{
      const normalized = String(status || "not_run").toLowerCase().replaceAll("_", "-");
      if (normalized === "pass" || normalized === "ready") return "PASS";
      if (normalized === "fail" || normalized === "failed") return "FAILED";
      if (normalized === "warn") return "WARNING";
      if (normalized === "not-run" || normalized === "not-configured") return "NOT RUN";
      if (normalized === "needs-input") return "NEEDS INPUT";
      if (normalized === "adapter-required") return "ADAPTER REQUIRED";
      if (normalized === "api-rejected") return "API REJECTED";
      if (normalized === "local-api-required") return "LOCAL API REQUIRED";
      return normalized.toUpperCase();
    }}
    function statusClass(status) {{
      const normalized = String(status || "not_run").toLowerCase().replaceAll("_", "-");
      if (["needs-input", "preflight", "adapter-required", "api-rejected", "local-api-required"].includes(normalized)) return "warn";
      return normalized;
    }}
    function setStatusBadge(node, status) {{
      if (!node) return;
      node.className = `result-badge ${{statusClass(status)}}`;
      node.textContent = statusLabel(status);
    }}
    function checkNameForConnection(connectionId) {{
      if (connectionId === "prism") return "prism-central";
      return connectionId;
    }}
    function connectionIdForConnectorType(type) {{
      const normalized = String(type || "").toLowerCase();
      if (normalized.includes("vcenter")) return "vcenter";
      if (normalized.includes("central")) return "prism";
      if (normalized.includes("element")) return "prism-element";
      if (normalized.includes("move")) return "move";
      if (normalized.includes("esxi")) return "esxi";
      if (normalized.includes("rvtools") || normalized.includes("import")) return "import";
      return "";
    }}
    function connectionTestRequest(connectionId) {{
      const request = {{skip_unconfigured_optional: true}};
      if (connectionId === "vcenter") {{
        request.vcenter = endpointPayload("vcenter");
        request.require_vcenter = true;
      }} else if (connectionId === "prism") {{
        request.prism = endpointPayload("prism");
        request.require_prism = true;
      }} else if (connectionId === "prism-element") {{
        request.prism_element = endpointPayload("prism-element");
        request.require_prism_element = true;
      }}
      return request;
    }}
    function renderConnectionResult(connectionId, result) {{
      const card = document.querySelector(`[data-connection="${{connectionId}}"]`);
      const status = result.status || "unknown";
      const detail = result.detail || result.summary || "No detail returned";
      if (card) {{
        const statusNode = card.querySelector("[data-status]");
        const output = card.querySelector("[data-test-result]");
        setStatusBadge(statusNode, status);
        if (output) {{
          renderOperatorSummary(output, {{
            status,
            title: `Connectivity ${{statusLabel(status)}}`,
            items: [
              detail,
              result.proof_authoritative ? "Authoritative local proof was written." : "Browser-only preflight; no authoritative proof was written.",
              "No infrastructure changes were made."
            ],
            evidence: result.proof ? `Proof file: ${{result.proof}}` : ""
          }});
        }}
      }}
      renderOperatorSummary(document.getElementById("connector-test-output"), {{
        status,
        title: `Connector ${{statusLabel(status)}}`,
        items: [
          `Connector: ${{connectionId}}`,
          detail,
          result.proof_authoritative ? "Result is backed by the local console API." : "Result is a browser-only preflight.",
          "No infrastructure changes were made."
        ],
        evidence: result.proof ? `Proof file: ${{result.proof}}` : ""
      }});
    }}
    function localPreflightResult(connectionId, status, detail) {{
      return {{
        schema_version: "nmrcp_connector_preflight_v1",
        connector: connectionId,
        status,
        detail,
        proof_authoritative: false,
        mode: "Browser-only preflight",
        credentials_serialized: false,
        endpoint_values_serialized: false,
        mutation_allowed: false
      }};
    }}
    async function testConnectionId(connectionId, button) {{
      const supported = ["vcenter", "prism", "prism-element"];
      if (!supported.includes(connectionId)) {{
        const result = localPreflightResult(
          connectionId,
          "adapter_required",
          "No authoritative live probe is implemented for this connector yet. Use the environment gate, approved lab proof, or offline import evidence until the backend adapter is added."
        );
        renderConnectionResult(connectionId, result);
        return result;
      }}
      const details = endpointPayload(connectionId);
      if (!details.endpoint || !details.username || !details.credential) {{
        const result = localPreflightResult(
          connectionId,
          "needs_input",
          "Endpoint, username, and request-only password are required before the local API can test this connector."
        );
        renderConnectionResult(connectionId, result);
        return result;
      }}
      if (button) button.disabled = true;
      try {{
        const response = await postJson("/api/connection-test", connectionTestRequest(connectionId));
        const checkName = checkNameForConnection(connectionId);
        const check = (response.result.checks || []).find((item) => item.name === checkName) || {{}};
        const result = {{
          schema_version: response.schema_version,
          connector: connectionId,
          status: check.status || response.status,
          detail: check.detail || `Authenticated=${{Boolean(check.authenticated)}}; counts=${{JSON.stringify(check.counts || {{}})}}`,
          proof: response.proof,
          proof_authoritative: true,
          read_only_calls: check.read_only_calls || [],
          counts: check.counts || {{}},
          credentials_serialized: false,
          endpoint_values_serialized: false,
          mutation_allowed: false
        }};
        renderConnectionResult(connectionId, result);
        updateStateSummary(await getJson("/api/state"));
        return result;
      }} catch (error) {{
        const unavailable = error.message.includes("Local console API is unavailable");
        const result = localPreflightResult(
          connectionId,
          unavailable ? "local_api_required" : "api_rejected",
          unavailable
            ? "Local API unavailable. Run nmrcp serve or Docker Compose, open the local console URL, then retry the test."
            : `Local API reached this connector path and returned a sanitized failure:\n${{error.message}}`
        );
        renderConnectionResult(connectionId, result);
        return result;
      }} finally {{
        if (button) button.disabled = false;
      }}
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
      showProofSummary(payload, path.replace("/api/", "").replaceAll("-", " "));
      return payload;
    }}
    async function getJson(path) {{
      setProof(`Loading ${{path}}...`);
      const response = await fetch(path, {{method: "GET", headers: {{"Accept": "application/json"}}}});
      const text = await response.text();
      let payload;
      try {{ payload = JSON.parse(text); }}
      catch (error) {{
        throw new Error("Local console API is unavailable. Run nmrcp serve or Docker Compose, then open the local console URL.");
      }}
      if (!response.ok || payload.status === "fail") {{
        throw new Error(scrub(payload));
      }}
      showProofSummary(payload, "Local state refreshed");
      return payload;
    }}
    function updateStateSummary(state) {{
      const profiles = state.environment_profiles || {{}};
      const runs = state.run_history || [];
      const evidence = state.evidence_index || [];
      document.getElementById("state-profiles").textContent = Object.keys(profiles).length;
      document.getElementById("state-runs").textContent = runs.length;
      document.getElementById("state-evidence").textContent = evidence.length;
    }}
    const storagePrefix = `nmrcp-console-${{payload.product_version}}`;
    function loadManaged(key, fallback) {{
      try {{
        const raw = localStorage.getItem(`${{storagePrefix}}-${{key}}`);
        return raw ? JSON.parse(raw) : fallback;
      }} catch (error) {{
        return fallback;
      }}
    }}
    function saveManaged(key, value) {{
      localStorage.setItem(`${{storagePrefix}}-${{key}}`, JSON.stringify(value));
    }}
    function rowCell(row, text) {{
      const cell = document.createElement("td");
      cell.textContent = text;
      row.appendChild(cell);
      return cell;
    }}
    function radioCell(row, name, value) {{
      const cell = document.createElement("td");
      const input = document.createElement("input");
      input.type = "radio";
      input.name = name;
      input.value = value;
      cell.appendChild(input);
      row.appendChild(cell);
      return input;
    }}
    function badgeCell(row, status) {{
      const cell = document.createElement("td");
      const badge = document.createElement("span");
      setStatusBadge(badge, status);
      cell.appendChild(badge);
      row.appendChild(cell);
      return badge;
    }}
    let managedConnectors = loadManaged("connectors", payload.connections.map((item) => ({{
      id: item.id,
      name: item.label,
      type: item.label,
      environment: "Dev",
      mode: item.mode,
      status: item.status,
      lastTest: "Not run"
    }})));
    let managedUsers = loadManaged("users", payload.rbac.users.map((item, index) => ({{
      id: `user-${{index + 1}}`,
      user: item.user,
      role: item.role,
      scope: item.scope,
      status: item.status
    }})));
    let managedRoles = loadManaged("roles", payload.rbac.roles.map((item, index) => ({{
      id: `role-${{index + 1}}`,
      role: item.role,
      allowed: item.allowed
    }})));
    let managedPlans = loadManaged("plans", []);
    function selectedValue(name) {{
      const selected = document.querySelector(`input[name="${{name}}"]:checked`);
      return selected ? selected.value : "";
    }}
    function renderManagedConnectors() {{
      const body = document.getElementById("managed-connectors");
      body.replaceChildren();
      for (const connector of managedConnectors) {{
        const row = document.createElement("tr");
        radioCell(row, "selected-connector", connector.id).addEventListener("change", () => {{
          document.getElementById("connector-name").value = connector.name;
          document.getElementById("connector-type").value = connector.type;
          document.getElementById("connector-environment").value = connector.environment;
          document.getElementById("connector-mode").value = connector.mode;
          document.getElementById("connector-status").value = connector.status;
        }});
        rowCell(row, connector.name);
        rowCell(row, connector.type);
        rowCell(row, connector.environment);
        rowCell(row, connector.mode);
        badgeCell(row, connector.status);
        rowCell(row, connector.lastTest || "Not run");
        const action = document.createElement("td");
        const button = document.createElement("button");
        button.type = "button";
        button.className = "secondary";
        button.textContent = "Test Connectivity";
        button.addEventListener("click", () => testManagedConnector(connector.id, button));
        action.appendChild(button);
        row.appendChild(action);
        body.appendChild(row);
      }}
    }}
    function connectorFormValue(existingId = "") {{
      return {{
        id: existingId || `connector-${{Date.now()}}`,
        name: document.getElementById("connector-name").value.trim() || "Unnamed connector",
        type: document.getElementById("connector-type").value,
        environment: document.getElementById("connector-environment").value,
        mode: document.getElementById("connector-mode").value,
        status: document.getElementById("connector-status").value
      }};
    }}
    function renderRoles() {{
      const roleSelect = document.getElementById("user-role");
      roleSelect.replaceChildren();
      const roleBody = document.getElementById("managed-roles");
      roleBody.replaceChildren();
      for (const role of managedRoles) {{
        const option = document.createElement("option");
        option.value = role.role;
        option.textContent = role.role;
        roleSelect.appendChild(option);
        const row = document.createElement("tr");
        rowCell(row, role.role);
        rowCell(row, role.allowed);
        roleBody.appendChild(row);
      }}
    }}
    function renderManagedUsers() {{
      const body = document.getElementById("managed-users");
      body.replaceChildren();
      for (const user of managedUsers) {{
        const row = document.createElement("tr");
        radioCell(row, "selected-user", user.id).addEventListener("change", () => {{
          document.getElementById("user-name").value = user.user;
          document.getElementById("user-role").value = user.role;
          document.getElementById("user-scope").value = user.scope;
          document.getElementById("user-status").value = user.status;
        }});
        rowCell(row, user.user);
        rowCell(row, user.role);
        rowCell(row, user.scope);
        rowCell(row, user.status);
        body.appendChild(row);
      }}
    }}
    function userFormValue(existingId = "") {{
      return {{
        id: existingId || `user-${{Date.now()}}`,
        user: document.getElementById("user-name").value.trim() || "Unnamed user",
        role: document.getElementById("user-role").value,
        scope: document.getElementById("user-scope").value.trim() || "Current assessment",
        status: document.getElementById("user-status").value
      }};
    }}
    function renderPlanInputs() {{
      const waveSelect = document.getElementById("plan-wave");
      waveSelect.replaceChildren();
      for (const wave of payload.waves) {{
        const option = document.createElement("option");
        option.value = wave.name;
        option.textContent = wave.name;
        waveSelect.appendChild(option);
      }}
      const workloadBox = document.getElementById("plan-workloads");
      workloadBox.replaceChildren();
      for (const workload of payload.workloads) {{
        const label = document.createElement("label");
        const input = document.createElement("input");
        input.type = "checkbox";
        input.value = workload.id;
        input.checked = workload.readiness === "ready" || workload.readiness === "research";
        label.appendChild(input);
        label.append(`${{workload.name}} (${{workload.readiness}})`);
        workloadBox.appendChild(label);
      }}
    }}
    function selectedWorkloads() {{
      return Array.from(document.querySelectorAll("#plan-workloads input:checked")).map((item) => item.value);
    }}
    function planFormValue(existingId = "") {{
      return {{
        id: existingId || `plan-${{Date.now()}}`,
        name: document.getElementById("plan-name").value.trim() || "Unnamed migration plan",
        environment: document.getElementById("plan-environment").value,
        target: document.getElementById("plan-target").value,
        wave: document.getElementById("plan-wave").value,
        workloads: selectedWorkloads(),
        status: "draft"
      }};
    }}
    function renderManagedPlans() {{
      const body = document.getElementById("managed-plans");
      body.replaceChildren();
      for (const plan of managedPlans) {{
        const row = document.createElement("tr");
        radioCell(row, "selected-plan", plan.id).addEventListener("change", () => {{
          document.getElementById("plan-name").value = plan.name;
          document.getElementById("plan-environment").value = plan.environment;
          document.getElementById("plan-target").value = plan.target;
          document.getElementById("plan-wave").value = plan.wave;
          for (const input of document.querySelectorAll("#plan-workloads input")) {{
            input.checked = plan.workloads.includes(input.value);
          }}
        }});
        rowCell(row, plan.name);
        rowCell(row, plan.environment);
        rowCell(row, plan.target);
        rowCell(row, plan.wave);
        rowCell(row, String(plan.workloads.length));
        rowCell(row, plan.status);
        body.appendChild(row);
      }}
    }}
    function persistAndRender() {{
      saveManaged("connectors", managedConnectors);
      saveManaged("users", managedUsers);
      saveManaged("roles", managedRoles);
      saveManaged("plans", managedPlans);
      renderManagedConnectors();
      renderRoles();
      renderManagedUsers();
      renderManagedPlans();
    }}
    document.getElementById("add-connector").addEventListener("click", () => {{
      managedConnectors.push(connectorFormValue());
      persistAndRender();
    }});
    document.getElementById("edit-connector").addEventListener("click", () => {{
      const id = selectedValue("selected-connector");
      managedConnectors = managedConnectors.map((item) => item.id === id ? connectorFormValue(id) : item);
      persistAndRender();
    }});
    document.getElementById("delete-connector").addEventListener("click", () => {{
      const id = selectedValue("selected-connector");
      managedConnectors = managedConnectors.filter((item) => item.id !== id);
      persistAndRender();
    }});
    async function testManagedConnector(id, button) {{
      const connector = managedConnectors.find((item) => item.id === id);
      if (!connector) return;
      const connectionId = connectionIdForConnectorType(connector.type);
      if (!connectionId) {{
        connector.lastTest = "unknown_connector_type";
        persistAndRender();
        return;
      }}
      const result = await testConnectionId(connectionId, button);
      connector.lastTest = `${{result.status}} @ ${{new Date().toLocaleString()}}`;
      connector.status = result.status === "pass" ? "ready" : connector.status;
      persistAndRender();
    }}
    document.getElementById("test-selected-connector").addEventListener("click", (event) => {{
      const id = selectedValue("selected-connector");
      if (id) testManagedConnector(id, event.currentTarget);
    }});
    for (const button of document.querySelectorAll("[data-test-connection]")) {{
      button.addEventListener("click", () => testConnectionId(button.dataset.testConnection, button));
    }}
    document.getElementById("add-user").addEventListener("click", () => {{
      managedUsers.push(userFormValue());
      persistAndRender();
    }});
    document.getElementById("edit-user").addEventListener("click", () => {{
      const id = selectedValue("selected-user");
      managedUsers = managedUsers.map((item) => item.id === id ? userFormValue(id) : item);
      persistAndRender();
    }});
    document.getElementById("delete-user").addEventListener("click", () => {{
      const id = selectedValue("selected-user");
      managedUsers = managedUsers.filter((item) => item.id !== id);
      persistAndRender();
    }});
    document.getElementById("add-role").addEventListener("click", () => {{
      const role = document.getElementById("role-name").value.trim();
      const allowed = document.getElementById("role-allowed").value.trim();
      if (role) {{
        managedRoles.push({{id: `role-${{Date.now()}}`, role, allowed: allowed || "Review migration readiness"}});
        persistAndRender();
      }}
    }});
    document.getElementById("create-plan").addEventListener("click", () => {{
      managedPlans.push(planFormValue());
      persistAndRender();
    }});
    document.getElementById("edit-plan").addEventListener("click", () => {{
      const id = selectedValue("selected-plan");
      managedPlans = managedPlans.map((item) => item.id === id ? planFormValue(id) : item);
      persistAndRender();
    }});
    document.getElementById("delete-plan").addEventListener("click", () => {{
      const id = selectedValue("selected-plan");
      managedPlans = managedPlans.filter((item) => item.id !== id);
      persistAndRender();
    }});
    document.getElementById("run-dry-run").addEventListener("click", () => {{
      const id = selectedValue("selected-plan");
      const plan = managedPlans.find((item) => item.id === id) || planFormValue();
      const result = {{
        schema_version: "nmrcp_console_dry_run_v1",
        status: "ready_for_review",
        dry_run_only: true,
        mutation_allowed: false,
        plan,
        command: document.getElementById("run-command").value
      }};
      renderOperatorSummary(document.getElementById("dry-run-output"), {{
        status: "pass",
        title: "Dry Run Ready For Review",
        items: [
          `Plan: ${{plan.name}}`,
          `Environment: ${{plan.environment}}`,
          `Target: ${{plan.target}}`,
          `Wave: ${{plan.wave}}`,
          `Included workloads: ${{plan.workloads.length}}`,
          "Mutation allowed: No",
          "Next step: review included workloads, owner approval, network fit, and Move lab proof before handoff."
        ],
        detail: "No infrastructure changes were made.",
        evidence: `Schema: ${{result.schema_version}}\nCommand: ${{result.command}}`
      }});
    }});
    renderPlanInputs();
    persistAndRender();
    async function runAction(button, action) {{
      button.disabled = true;
      try {{ await action(); }}
      catch (error) {{ showErrorSummary(error); }}
      finally {{ button.disabled = false; }}
    }}
    document.getElementById("test-connections").addEventListener("click", (event) => runAction(event.currentTarget, async () => {{
      const result = await postJson("/api/connection-test", {{
        vcenter: endpointPayload("vcenter"),
        prism: endpointPayload("prism"),
        prism_element: endpointPayload("prism-element"),
        require_vcenter: true,
        require_prism: true,
        require_prism_element: true
      }});
      for (const check of result.result.checks || []) {{
        const status = document.querySelector(`[data-connection="${{connectionIdForCheck(check.name)}}"] [data-status]`);
        setStatusBadge(status, check.status);
      }}
      updateStateSummary(await getJson("/api/state"));
    }}));
    document.getElementById("environment-access").addEventListener("click", (event) => runAction(event.currentTarget, async () => {{
      await postJson("/api/environment-access", environmentAccessPayload());
      updateStateSummary(await getJson("/api/state"));
    }}));
    document.getElementById("collect-sources").addEventListener("click", (event) => runAction(event.currentTarget, async () => {{
      await postJson("/api/collect-sources", {{
        vcenter: endpointPayload("vcenter"),
        prism: endpointPayload("prism")
      }});
      updateStateSummary(await getJson("/api/state"));
    }}));
    document.getElementById("run-readiness").addEventListener("click", (event) => runAction(event.currentTarget, async () => {{
      await postJson("/api/run-readiness", {{use_collected: true}});
      updateStateSummary(await getJson("/api/state"));
    }}));
    document.getElementById("tester-report").addEventListener("click", (event) => runAction(event.currentTarget, async () => {{
      await postJson("/api/tester-report", {{}});
      updateStateSummary(await getJson("/api/state"));
    }}));
    document.getElementById("refresh-state").addEventListener("click", (event) => runAction(event.currentTarget, async () => {{
      updateStateSummary(await getJson("/api/state"));
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
    if {item.get("id") for item in connections if isinstance(item, dict)} != {"vcenter", "prism", "prism-element", "move", "esxi", "import"}:
        errors.append("Operations console must define vcenter, prism, prism-element, move, esxi, and import connections")
    for leaked in ("vcenter01.corp.local", "migration.owner@example.com"):
        checks += 1
        if leaked in text:
            errors.append(f"Operations console leaked sample sensitive value: {leaked}")
    return OperationsConsoleValidation("pass" if not errors else "fail", checks, tuple(errors), tuple(warnings))


def console_payload(inventory: dict[str, Any], assessments: list[WorkloadAssessment], waves: list[Wave]) -> dict[str, Any]:
    wave_by_workload = {workload_id: wave.name for wave in waves for workload_id in wave.workload_ids}
    return {
        "schema_version": OPERATIONS_CONSOLE_SCHEMA_VERSION,
        "product_version": __version__,
        "provider_catalog": provider_catalog(),
        "connector_capabilities": connector_capability_catalog(),
        "provider_pair": {
            "source": "vmware_vcenter",
            "source_label": "VMware vCenter",
            "source_status": "validated",
            "target": "nutanix_ahv",
            "target_label": "Nutanix AHV",
            "rule_set": "vmware_to_nutanix_ahv",
            "rule_set_label": "VMware vCenter -> Nutanix AHV",
        },
        "summary": summarize(assessments),
        "connections": [
            {"id": "vcenter", "label": "vCenter", "mode": "read-only", "status": "not_configured"},
            {"id": "prism", "label": "Prism Central", "mode": "read-only", "status": "not_configured"},
            {"id": "prism-element", "label": "Prism Element", "mode": "read-only", "status": "not_configured"},
            {"id": "move", "label": "Nutanix Move", "mode": "approved_lab_only", "status": "proof_required"},
            {"id": "esxi", "label": "ESXi", "mode": "gate-only", "status": "gate_only"},
            {"id": "import", "label": "RVTools / Import", "mode": "offline", "status": "available"},
        ],
        "environment_profiles": environment_profiles(),
        "connector_policies": connector_policies(),
        "settings": operational_settings(),
        "rbac": rbac_model(),
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


def environment_profiles() -> list[dict[str, Any]]:
    return [
        {
            "environment": "Dev",
            "purpose": "Connector proof, parser validation, and sample workload readiness.",
            "read_gate": "Source scope + credential source",
            "write_gate": "Write-intent review only",
            "targets": "vCenter, Prism Central, Prism Element, ESXi, Move",
        },
        {
            "environment": "UAT",
            "purpose": "Tester validation against approved lab or non-production customer scopes.",
            "read_gate": "Change reference + rollback plan",
            "write_gate": "Peer review + dry run + target scope",
            "targets": "AHV, NC2, Move, Prism, vCenter",
        },
        {
            "environment": "Production",
            "purpose": "Controlled readiness evidence before production migration activity.",
            "read_gate": "Approved source scope + audited credential path",
            "write_gate": "CAB + backup + maintenance + break-glass",
            "targets": "Scoped production endpoints only",
        },
    ]


def connector_policies() -> list[dict[str, Any]]:
    capabilities = connector_capability_catalog()["connectors"]
    rows: list[dict[str, Any]] = []
    for item in capabilities:
        rows.append(
            {
                "label": item["label"],
                "modes": ", ".join(item["modes"]),
                "write": "enabled" if item["write_enabled"] else "disabled",
                "credential_policy": item["credential_policy"],
                "status": item["status"],
            }
        )
    rows.append(
        {
            "label": "RVTools / Import",
            "modes": "offline",
            "write": "disabled",
            "credential_policy": "no_credentials_required",
            "status": "available",
        }
    )
    return rows


def operational_settings() -> dict[str, str]:
    return {
        "data_boundary": "Local console data directory",
        "default_access": "Read-only connector tests",
        "credential_policy": "Credentials are request-only and never persisted",
        "tls_policy": "TLS verification on; DEV can record an exception",
        "retention": "Run history 50 actions, evidence index 100 artifacts",
        "mutation_policy": "Write intent validates gates without execution",
    }


def rbac_model() -> dict[str, Any]:
    return {
        "auth_mode": "Local Operator",
        "roles": [
            {"role": "Platform Owner", "allowed": "Approve environments, gates, release readiness, and production scope."},
            {"role": "Migration Operator", "allowed": "Configure endpoints, run read-only tests, collect evidence, and run readiness."},
            {"role": "Read-only Reviewer", "allowed": "View assessment output, evidence summaries, findings, and tester reports."},
            {"role": "Security Reviewer", "allowed": "Review credential policy, audit state, redaction posture, and gate compliance."},
        ],
        "users": [
            {"user": "Local Operator", "role": "Migration Operator", "scope": "Current workstation", "status": "active"},
            {"user": "Platform Owner", "role": "Platform Owner", "scope": "Environment approvals", "status": "configured"},
            {"user": "Change Reviewer", "role": "Read-only Reviewer", "scope": "Evidence and wave review", "status": "configured"},
            {"user": "Security Reviewer", "role": "Security Reviewer", "scope": "Audit and credential policy", "status": "configured"},
        ],
    }


def environment_profile_rows(profiles: list[dict[str, Any]]) -> str:
    rows = []
    for profile in profiles:
        rows.append(
            "<tr>"
            f"<td><strong>{escape(profile['environment'])}</strong></td>"
            f"<td>{escape(profile['purpose'])}</td>"
            f"<td><span class=\"status-chip good\">{escape(profile['read_gate'])}</span></td>"
            f"<td><span class=\"status-chip warn\">{escape(profile['write_gate'])}</span></td>"
            f"<td>{escape(profile['targets'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def connector_policy_rows(policies: list[dict[str, Any]]) -> str:
    rows = []
    for policy in policies:
        write_class = "blocked" if policy["write"] == "disabled" else "good"
        rows.append(
            "<tr>"
            f"<td><strong>{escape(policy['label'])}</strong></td>"
            f"<td>{escape(policy['modes'])}</td>"
            f"<td><span class=\"status-chip {write_class}\">{escape(policy['write'])}</span></td>"
            f"<td>{escape(policy['credential_policy'])}</td>"
            f"<td>{escape(policy['status'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


def settings_cards(settings: dict[str, str]) -> str:
    labels = {
        "credential_policy": "Credential Policy",
        "tls_policy": "TLS Policy",
        "retention": "Retention",
        "mutation_policy": "Mutation Policy",
    }
    rows = []
    for key in ("credential_policy", "tls_policy", "retention", "mutation_policy"):
        rows.append(
            '<article class="ops-card">'
            f"<h3>{escape(labels[key])}</h3>"
            f'<p class="muted">{escape(settings[key])}</p>'
            "</article>"
        )
    return "\n".join(rows)


def rbac_user_rows(users: list[dict[str, Any]]) -> str:
    rows = []
    for user in users:
        rows.append(
            "<tr>"
            f"<td><strong>{escape(user['user'])}</strong></td>"
            f"<td>{escape(user['role'])}</td>"
            f"<td>{escape(user['scope'])}</td>"
            f"<td><span class=\"status-chip good\">{escape(user['status'])}</span></td>"
            "</tr>"
        )
    return "\n".join(rows)


def rbac_role_rows(roles: list[dict[str, Any]]) -> str:
    rows = []
    for role in roles:
        rows.append(
            "<tr>"
            f"<td><strong>{escape(role['role'])}</strong></td>"
            f"<td>{escape(role['allowed'])}</td>"
            "</tr>"
        )
    return "\n".join(rows)


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
        f'        <div class="connection-actions"><button type="button" class="secondary" data-test-connection="{escape(identifier)}">Test Connectivity</button></div>',
        '        <p class="connection-status">Status <span class="result-badge not-configured" data-status>NOT RUN</span></p>',
        '        <div class="connection-result" data-test-result>Connectivity test result: Not run</div>',
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
