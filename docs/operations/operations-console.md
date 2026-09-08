# Operations Console

`operations-console.html` is generated with every assessment. It is a local,
dependency-free operator UI for the guided migration workflow. The left menu
uses page-style views rather than anchor jumps, so each operational area opens
as its own workspace panel. Selecting the NMRCP logo badge returns operators to
the Operations Dashboard and resets the page to the top of the menu:

- Connect Environments: vCenter, Prism Central, Prism Element, Nutanix Move, ESXi, and
  RVTools/import sources are presented as explicit local connection panels with
  visible per-connector **Test Connectivity** controls and green/amber/red local
  test result badges.
- Operations Dashboard: operators can see the active workspace posture, default
  access mode, local data boundary, connector count, role model, and write-intent
  posture at a glance.
- Environment Gates: operators select Dev, UAT, or Production, choose read or
  write intent, select PC, PE, Move, vCenter, or ESXi, and validate required gates
  before connector workflows proceed.
- Environment Profiles: Dev, UAT, and Production each have visible purpose,
  read gates, write-intent gates, and default target scopes.
- Connector Policies: each connector shows its current modes, credential
  persistence policy, alpha status, and whether mutation is enabled.
- Connector Management: operators can add, edit, and delete local connector
  records for Dev, UAT, and Production planning without storing credentials or
  endpoint values in the repo. Managed connectors can also be selected and tested
  against the matching runtime connection panel.
- Run Compatibility Analysis: operators can filter workload readiness, risk,
  wave placement, Move action, and top findings from the embedded assessment.
- Operator Workbench: each workflow step shows where to configure it, what to
  run, what output to expect, and a button that opens the relevant console page.
- Build Move Plan: the console keeps the generated local run command and the
  guardrails for staging only reviewed workloads into the Move plan.
- Migration Plans and Dry Runs: operators can create, edit, and delete local
  migration plans, select workloads from the current assessment, and generate a
  dry-run summary that is explicitly non-mutating, with the machine-readable
  schema and generated command retained as secondary evidence.
- Settings: credential handling, TLS posture, retention, and mutation policy are
  shown as operator-facing controls and future configuration anchors.
- Users & RBAC: the local alpha console now exposes the intended operator roles,
  user scopes, and review duties. Operators can add, edit, and delete local user
  records and add roles for planning. This is not an enterprise identity
  provider; it is the visible RBAC model that future authenticated deployments
  should enforce.
- Audit & State: operators can see where redacted local state, run history, and
  evidence indexes are tracked.

When served with `nmrcp serve`, the console also exposes a tester workflow:

- **Validate Environment Gates** posts to `/api/environment-access`, evaluates
  the selected environment, target, mode, and supplied gates, and reports missing
  approvals before read/write connectivity is attempted.
- **Test Read-only Connections** posts to `/api/connection-test`, runs the
  existing redacted `live-readiness` checks, and writes local proof without
  serializing passwords, usernames, or endpoint values.
- **Test Connectivity** on an individual connector card posts a scoped
  `/api/connection-test` request for vCenter, Prism Central, or Prism Element
  and skips unconfigured optional peers, so a single endpoint test can pass or
  fail on its own evidence. Nutanix Move, ESXi, and RVTools/import cards return
  an explicit browser-only preflight status until authoritative backend adapters
  are implemented.
- Real connector tests must be run from the served console URL, normally
  `http://127.0.0.1:8080/operations-console.html`, not the static file or the
  GitHub Pages demo. If a Dev or UAT Nutanix lab uses self-signed certificates,
  import the lab CA or clear TLS verification for that test. Production should
  keep TLS verification enabled with trusted certificates.
- **Collect Source Evidence** posts to `/api/collect-sources`, runs the
  read-only vCenter and Prism Central collectors, and writes source artifacts
  plus `collection-summary.json` and `collection-proof-report.md`.
- **Run Readiness Assessment** posts to `/api/run-readiness`, scores collected
  inventory when available, writes assessment artifacts, and refreshes the
  served operations console.
- **Prepare Tester Report** posts to `/api/tester-report`, summarizes the local
  redacted connection, collection, and readiness artifacts, and writes
  `tester-report.md` plus `tester-report.json` for GitHub tester feedback.
- **Refresh Local State** reads `/api/state` and shows the local profile, run,
  and evidence counters from `console-state.json`.

The served console writes `console-state.json` in the configured data directory
so operators can restart the console and still see redacted environment profile
metadata, run history, connector capability metadata, and evidence paths. It
does not persist credentials, usernames, endpoint values, tokens, or raw
inventory in that state file. Live vCenter, Prism Central, Prism Element, and
approved Nutanix Move lab evidence remain explicit gates. Write mode is gate
evaluation only; Nutanix Move, Prism Central, Prism Element, vCenter, or ESXi
mutation is not enabled by this tester workflow.

The operational shell is intentionally visible in the static demo as well as the
served console. The static GitHub Pages version cannot call infrastructure, but
it should still make it obvious where operators would configure environments,
review connector policy, check settings, manage RBAC duties, and inspect audit
state when the console is run locally or packaged as an appliance.

Console outputs should lead with operator-readable summaries rather than raw
JSON. Action panels use visual status badges, short findings, next steps,
evidence paths, and a clear statement when no infrastructure changes were made.
Structured schemas and commands remain available as secondary evidence for
audit and troubleshooting.

Validate the generated console against `assessment.json`:

```powershell
python -m nmrcp.cli validate-operations-console `
  --console outputs\sample-assessment\operations-console.html `
  --assessment outputs\sample-assessment\assessment.json
```

`change-gate` runs the same validation automatically.
