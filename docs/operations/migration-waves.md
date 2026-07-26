# Migration Waves

`migration-waves.csv` is generated with every assessment. It gives migration
leads a workload-level view of which wave each VM belongs to, including owner,
target, readiness, risk score, and the top readiness findings that explain the
placement.

## Columns

- `wave`: generated migration wave name.
- `workload_id`: source workload identifier.
- `name`: source workload name.
- `owner`: workload owner.
- `target`: `ahv` or `nc2`.
- `readiness`: current readiness state.
- `risk_score`: workload risk score.
- `top_findings`: up to three readiness finding codes driving placement.

Validate the workload-level wave assignment against the canonical assessment:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-migration-waves `
  --waves outputs\sample-assessment\migration-waves.csv `
  --assessment outputs\sample-assessment\assessment.json
```

`change-gate` runs the same validation automatically, so stale or manually
edited workload-level wave assignments cannot pass evidence handoff. The
validator also fails closed when `assessment.json` wave membership references an
unknown workload or places the same workload in multiple waves, so hidden or
duplicated migration scope cannot be ignored.
