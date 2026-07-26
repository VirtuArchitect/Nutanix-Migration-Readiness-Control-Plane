# Target Readiness Comparison

`target-readiness-comparison.csv` is generated with every assessment. It scores
each workload against both AHV and NC2 so operators can see whether a workload is
better suited to one target before committing to a migration path.

## Columns

- `workload_id`, `name`, and `owner`: source workload identity.
- `ahv_readiness`, `ahv_risk_score`, and `ahv_findings`: AHV outcome.
- `nc2_readiness`, `nc2_risk_score`, and `nc2_findings`: NC2 outcome.
- `preferred_target`: `ahv`, `nc2`, `either`, or `review`.
- `decision_reason`: why the preferred target was chosen.

## Use

Review this file with architecture and application owners before selecting the
target for a wave. The selected target-specific `assessment.json` and
`nutanix-move-plan.csv` still represent the target passed to `assess` or
`run-assessment`; this comparison is the decision-support view across both
targets.

The comparison is included in `evidence-manifest.json`, evidence bundles, change
gate required artifacts, and final handoff packages.

Validate the comparison against the canonical assessment before handoff:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-target-comparison `
  --comparison outputs\sample-assessment\target-readiness-comparison.csv `
  --assessment outputs\sample-assessment\assessment.json
```

`assessment.json` includes a redacted `target_comparison_context` block so the
validator can compare AHV and NC2 readiness, risk, findings, preferred target,
and decision reason without reopening raw inventory. The validator also binds
that context to canonical workload ID, name, and owner in `assessments`, and
fails closed when comparison context omits, duplicates, or invents workloads.
`change-gate` runs the same validation automatically.
