# Operations Console

`operations-console.html` is generated with every assessment. It is a local,
dependency-free operator UI for the guided migration workflow:

- Connect Environments: vCenter, Prism Central, Nutanix Move, and RVTools/import
  sources are presented as explicit local connection panels.
- Run Compatibility Analysis: operators can filter workload readiness, risk,
  wave placement, Move action, and top findings from the embedded assessment.
- Build Move Plan: the console keeps the generated local run command and the
  guardrails for staging only reviewed workloads into the Move plan.

The console does not store credentials and does not contact endpoints by
itself. It is a front door for approved local runs; live vCenter/Prism proof and
approved Nutanix Move lab evidence are still separate gates.

Validate the generated console against `assessment.json`:

```powershell
python -m nmrcp.cli validate-operations-console `
  --console outputs\sample-assessment\operations-console.html `
  --assessment outputs\sample-assessment\assessment.json
```

`change-gate` runs the same validation automatically.
