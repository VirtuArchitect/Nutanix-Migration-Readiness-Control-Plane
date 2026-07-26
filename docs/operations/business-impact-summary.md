# Business Impact Summary

`business-impact-summary.csv` is generated with every assessment. It rolls
readiness evidence up by workload tier so executives, change boards, and
program leads can see whether critical, noncritical, or unknown business groups
are ready to stage.

The summary includes:

- tier.
- readiness counts for ready, research, prepare, and blocked workloads.
- average and maximum risk score.
- open, critical, and high finding counts.
- Move staging status: `ready`, `review`, `remediate`, or `blocked`.
- affected owners.
- held workloads.
- waves represented in the tier.
- executive summary text.

Validate the summary against `assessment.json`:

```powershell
python -m nmrcp.cli validate-business-impact `
  --summary outputs\sample-assessment\business-impact-summary.csv `
  --assessment outputs\sample-assessment\assessment.json
```

Use this artifact with `wave-readiness-summary.csv`,
`migration-risk-register.csv`, `owner-risk-summary.csv`, and
`nutanix-move-plan.csv`. Critical or unknown tiers in `blocked` or `remediate`
state should not be approved for Move staging until the remediation tracker,
owner sign-offs, rollback ownership, and risk acceptance evidence are closed.

`change-gate` runs the same validation automatically. It uses the redacted
`business_context` block in `assessment.json` for tier classification, but binds
that context to canonical workload identity and owner from `assessments` and
fails closed when wave membership references unknown workloads or duplicates a
workload across waves.
