# Owner Risk Summary

`owner-risk-summary.csv` is generated with every assessment. It rolls workload
readiness and findings up by owner so migration leads can see which application
or platform teams need attention before a wave is approved.

## Columns

- `owner`: workload owner from inventory or metadata enrichment.
- `total_workloads`: owner workload count.
- `ready`, `research`, `prepare`, `blocked`: readiness counts.
- `average_risk_score` and `max_risk_score`: owner-level risk view.
- `open_findings`: total readiness findings owned by the team.
- `critical_findings`, `high_findings`, `medium_findings`: severity counts.
- `blocked_workloads`: workloads still in `prepare` or `blocked` states.
- `waves`: migration waves containing the owner's workloads.
- `next_action`: generated action guidance for the owner.

## Use

Use this rollup before change-board submission and during application-owner
working sessions. Owners with blocked workloads or high-severity findings should
close remediation tracker rows and re-run assessment before those workloads are
staged in Nutanix Move.

The owner summary is included in `evidence-manifest.json`, evidence bundles,
change gate required artifacts, and final handoff packages.

Validate the summary against the canonical assessment before handoff:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-owner-risk-summary `
  --summary outputs\smoke\owner-risk-summary.csv `
  --assessment outputs\smoke\assessment.json
```

`change-gate` runs the same validation automatically, so stale or manually
edited owner rollups cannot pass the evidence gate. Validation also fails
closed when assessment waves reference unknown workload IDs or place the same
workload in multiple waves, so owner accountability cannot be built from
invented or duplicated wave membership.
