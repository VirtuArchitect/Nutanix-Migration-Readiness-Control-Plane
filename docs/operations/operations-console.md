# Operations Console

`operations-console.html` is generated with every assessment. It is a local,
dependency-free operator UI for the guided migration workflow:

- Connect Environments: vCenter, Prism Central, Nutanix Move, ESXi, and
  RVTools/import sources are presented as explicit local connection panels.
- Environment Gates: operators select Dev, UAT, or Production, choose read or
  write intent, select PC, Move, vCenter, or ESXi, and validate required gates
  before connector workflows proceed.
- Run Compatibility Analysis: operators can filter workload readiness, risk,
  wave placement, Move action, and top findings from the embedded assessment.
- Build Move Plan: the console keeps the generated local run command and the
  guardrails for staging only reviewed workloads into the Move plan.

When served with `nmrcp serve`, the console also exposes a tester workflow:

- **Validate Environment Gates** posts to `/api/environment-access`, evaluates
  the selected environment, target, mode, and supplied gates, and reports missing
  approvals before read/write connectivity is attempted.
- **Test Read-only Connections** posts to `/api/connection-test`, runs the
  existing redacted `live-readiness` checks, and writes local proof without
  serializing passwords, usernames, or endpoint values.
- **Collect Source Evidence** posts to `/api/collect-sources`, runs the
  read-only vCenter and Prism Central collectors, and writes source artifacts
  plus `collection-summary.json` and `collection-proof-report.md`.
- **Run Readiness Assessment** posts to `/api/run-readiness`, scores collected
  inventory when available, writes assessment artifacts, and refreshes the
  served operations console.
- **Prepare Tester Report** posts to `/api/tester-report`, summarizes the local
  redacted connection, collection, and readiness artifacts, and writes
  `tester-report.md` plus `tester-report.json` for GitHub tester feedback.

The console does not persist credentials. Live vCenter/Prism proof and approved
Nutanix Move lab evidence remain explicit gates. Write mode is gate evaluation
only; Nutanix Move, Prism Central, vCenter, or ESXi mutation is not enabled by
this tester workflow.

Validate the generated console against `assessment.json`:

```powershell
python -m nmrcp.cli validate-operations-console `
  --console outputs\sample-assessment\operations-console.html `
  --assessment outputs\sample-assessment\assessment.json
```

`change-gate` runs the same validation automatically.
