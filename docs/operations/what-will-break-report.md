# What Will Break Report

`what-will-break-report.csv` and `what-will-break-brief.md` are generated with
every assessment. The CSV turns each readiness finding into a workload-level
breakage scenario, impact statement, operator signal, required action, and
evidence reference. The Markdown brief condenses the same assessment-backed rows
into executive signal, top breakage scenarios, owner and wave holds, clean
signals, evidence to inspect, and stop conditions.

The report is designed for app-owner, partner, MSP, and change-board review. It
answers the product promise directly: know what is likely to break before a
VMware workload is staged for Nutanix migration.

## Validate

```powershell
python -m nmrcp.cli validate-what-will-break `
  --report outputs\sample-assessment\what-will-break-report.csv `
  --assessment outputs\sample-assessment\assessment.json

python -m nmrcp.cli validate-what-will-break-brief `
  --brief outputs\sample-assessment\what-will-break-brief.md `
  --assessment outputs\sample-assessment\assessment.json
```

`change-gate` runs both validators. The CSV must match rows rebuilt from
canonical `assessment.json` workload assessments, wave membership, and
`inventory_coverage_context`; the embedded `what_will_break_context` must match
that rebuilt source as well. The Markdown brief is rendered from the same rows
and fails validation if the decision signal, top scenarios, owner/wave holds,
evidence references, or stop-condition language drift from `assessment.json`.

## Columns

- `workload_id`, `name`, `owner`, `target`, and `wave`: workload scope.
- `readiness` and `risk_score`: current assessment posture.
- `finding_code` and `severity`: readiness signal or
  `no_open_readiness_breakage`.
- `inventory_coverage_percent`: source-data completeness for the workload.
- `inventory_coverage_gaps`: missing or partial inventory fields that can hide
  migration risk, or `none`.
- `coverage_risk`: `complete`, `coverage_followup`,
  `critical_coverage_gap`, or `unknown`.
- `move_staging_decision`: `hold`, `conditional_review`, or
  `include_after_validation`.
- `breakage_scenario`: human-readable failure mode.
- `impact`: migration and business impact if the issue is ignored.
- `operator_signal`: scheduling guidance such as `do_not_schedule`.
- `required_action`: remediation or validation action.
- `evidence_refs`: local evidence rows to attach or inspect.

## Operating Notes

Use this report before stakeholder review and change-board approval. Rows with
`operator_signal=do_not_schedule` should stay out of Move staging until the
referenced evidence is remediated or formally accepted.
Rows with `coverage_risk=critical_coverage_gap` or
`operator_signal=complete_inventory_before_schedule` should not be treated as
clean no-breakage evidence until the missing source facts are collected or
explicitly accepted by the migration owner.

Use `what-will-break-brief.md` when a sponsor, app owner, partner, MSP, or
change-board reviewer needs the short version first. Use
`what-will-break-report.csv` when operators need the full row-level evidence.
