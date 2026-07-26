# Workload Validation Checklist

`workload-validation-checklist.csv` is generated with every assessment. It turns
the generic pre/post validation checklist into workload-level validation rows
that operators can review, assign, and close for each VM before and after
Nutanix Move activity.

## Validate

```powershell
python -m nmrcp.cli validate-workload-validation-checklist `
  --checklist outputs\sample-assessment\workload-validation-checklist.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The validator checks the CSV against the
`nmrcp_workload_validation_checklist_v1` context embedded in `assessment.json`.
This catches stale or manually edited workload validation rows before handoff.

## Columns

- `schema_version`: `nmrcp_workload_validation_checklist_v1`.
- `workload_id`, `name`, `owner`, `target`, `wave`: workload identity and wave.
- `move_plan_decision`, `stage_status`: staging decision from the Move staging
  readiness queue.
- `validation_phase`: `pre_migration`, `cutover`, or `post_migration`.
- `check_name`: stable check identifier.
- `required_evidence`: evidence expected before the check closes.
- `stop_condition`: condition that stops staging, cutover, or closure.
- `status`: `ready` or `blocked` based on staging readiness.
- `evidence_refs`: local evidence references for review.

## Gate Behavior

`change-gate` validates this artifact automatically. Blocked validation rows
are valid evidence rows; they make workload-specific stop conditions explicit
before Move staging, cutover, or post-migration closure.
