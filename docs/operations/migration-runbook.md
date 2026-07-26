# Migration Runbook

`migration-runbook.md` is generated with every assessment. It turns readiness
findings into a wave-ordered operator plan with universal stop conditions,
include or hold intent, governance facts, dependency coordination, and required
actions per workload.

Validate the generated runbook against `assessment.json`:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-migration-runbook `
  --runbook outputs\sample-assessment\migration-runbook.md `
  --assessment outputs\sample-assessment\assessment.json
```

The validator checks required sections, universal stop conditions, evidence
handoff references, workload identity, wave assignment, owner, target,
readiness, risk, staging intent, and generated finding actions.

`change-gate` runs the same validation automatically. The runbook remains a
human-reviewed plan; it does not execute migration actions or submit anything to
Nutanix Move.
