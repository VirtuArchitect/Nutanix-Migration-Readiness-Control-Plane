# Wave Readiness Summary

`wave-readiness-summary.csv` is generated with every assessment. It gives
change boards, MSP migration factories, and partner leads a wave-level
go/hold view without requiring them to inspect every workload row.

The summary includes:

- wave name and description.
- readiness counts for ready, research, prepare, and blocked workloads.
- average and maximum risk score.
- open, critical, and high finding counts.
- Move staging status: `ready`, `conditional`, or `hold`.
- workloads that can be staged after review.
- held workloads.
- affected owners.
- the next gate required before staging or scheduling.

Validate the summary against `assessment.json`:

```powershell
python -m nmrcp.cli validate-wave-summary `
  --summary outputs\sample-assessment\wave-readiness-summary.csv `
  --assessment outputs\sample-assessment\assessment.json
```

Use this artifact together with `migration-waves.csv`,
`migration-risk-register.csv`, `owner-risk-summary.csv`, and
`nutanix-move-plan.csv`. A wave in `hold` must not be staged in Nutanix Move
until its remediation tracker rows, owner approvals, rollback ownership, and
required risk acceptance are closed.

`change-gate` runs the same validation automatically and fails if the summary
has stale wave rows, mismatched readiness counts, incorrect risk/finding counts,
or a staging status that no longer matches `assessment.json`. The validator also
fails closed when `assessment.json` wave membership references an unknown
workload or places the same workload in multiple waves, so hidden scheduling
scope cannot be ignored during CSV comparison.
