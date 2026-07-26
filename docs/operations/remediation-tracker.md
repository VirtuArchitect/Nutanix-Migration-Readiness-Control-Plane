# Remediation Tracker

`remediation-tracker.csv` is generated with every assessment. It turns readiness
findings into owner-action rows that can be assigned, filtered, imported into a
ticketing system, or reviewed with application teams.

## Columns

- `status`: defaults to `open`.
- `owner`: workload owner from inventory or metadata enrichment.
- `wave`: generated migration wave.
- `workload_id` and `workload_name`: source workload identity.
- `target`: `ahv` or `nc2`.
- `readiness` and `risk_score`: current assessment result.
- `severity`: finding severity.
- `finding_code`: deterministic readiness finding code.
- `recommended_action`: remediation or validation action.
- `evidence_ref`: pointer back to the assessment evidence.
- `closure_ref`: change, ticket, commit, screenshot, or evidence reference for
  closed, accepted, or waived rows.
- `closed_by`: person or team that closed, accepted, or waived the row.
- `closed_at`: closure timestamp.
- `notes`: closure, risk-acceptance, or waiver rationale.

## Use

Review this tracker before submitting a change request. Workloads in `prepare`
or `blocked` states should remain out of Move execution until the matching
tracker rows are closed and the assessment is re-run.

Validate the generated tracker against the canonical assessment before assigning
rows to owners:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-remediation-tracker `
  --tracker outputs\sample-assessment\remediation-tracker.csv `
  --assessment outputs\sample-assessment\assessment.json
```

Validate a draft filled tracker while rows are still open:

```powershell
python -m nmrcp.cli validate-remediation `
  --tracker outputs\sample-assessment\remediation-tracker.csv `
  --allow-open
```

Validate a final tracker before closure:

```powershell
python -m nmrcp.cli validate-remediation `
  --tracker outputs\sample-assessment\remediation-tracker.csv
```

Final validation fails closed on `open` rows. Rows marked `closed`, `accepted`,
or `waived` must include `closure_ref`, `closed_by`, and `closed_at`.
`change-gate` runs generated tracker validation automatically, and runs final
closure validation when `--remediation-tracker` is supplied.

Supply the final reviewed tracker to closure gates and handoff packaging:

```powershell
python -m nmrcp.cli change-gate `
  --dir outputs\sample-assessment `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv

python -m nmrcp.cli package-handoff `
  --dir outputs\sample-assessment `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --out outputs\sample-handoff-package.zip
```

The generated draft tracker is included in `evidence-manifest.json`, evidence
bundles, and change-gate required artifacts. A supplied final tracker is
validated by closure gates and archived in handoff packages at
`remediation/final-remediation-tracker.csv`.
