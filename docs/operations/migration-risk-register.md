# Migration Risk Register

`migration-risk-register.csv` is generated with every assessment. It groups
readiness findings by finding code so migration leads can see the estate-wide
breakage patterns before opening every workload or remediation row.

## Columns

- `finding_code`: deterministic readiness finding code.
- `highest_severity`: highest severity observed for that finding.
- `affected_workloads`: number of unique workloads with the finding.
- `ready`, `research`, `prepare`, `blocked`: readiness counts for affected
  workloads.
- `max_risk_score`: highest workload risk score in the finding group.
- `owners`: affected workload owners.
- `waves`: waves containing affected workloads.
- `workloads`: affected workload names.
- `move_staging_blocker`: `yes` when the finding group includes prepare or
  blocked workloads, or high/critical severity.
- `recommended_action`: generated remediation or validation action.

## Use

Use the register during triage and change-board preparation to answer:

- Which breakage patterns repeat across the migration estate?
- Which owners need coordinated remediation?
- Which findings block Move staging even before reviewing individual rows?

The risk register complements `remediation-tracker.csv`. The remediation tracker
is the owner-action work queue; the risk register is the pattern-level summary
for leads, partners, and MSP migration factories.

Validate the register against the canonical assessment before handoff:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-risk-register `
  --register outputs\smoke\migration-risk-register.csv `
  --assessment outputs\smoke\assessment.json
```

`change-gate` runs the same validation automatically, so stale or manually
edited risk registers cannot pass the evidence gate. The validator also fails
closed when `assessment.json` wave membership references unknown workloads or
places one workload in multiple waves.
