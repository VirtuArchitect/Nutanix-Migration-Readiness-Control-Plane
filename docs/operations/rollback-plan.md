# Rollback Plan

`rollback-plan.csv` is generated with every assessment. It turns recovery
readiness and Move staging status into a per-workload rollback/backout plan for
change-board review.

Validate it with:

```powershell
python -m nmrcp.cli validate-rollback-plan `
  --plan outputs\sample-assessment\rollback-plan.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The validator compares the CSV to the `nmrcp_rollback_plan_v1` context embedded
in `assessment.json`. The embedded context must also match canonical assessment
workload identity, validated wave membership, findings-derived recovery status,
and internally consistent rollback status, trigger, required action, and
evidence references. `change-gate` runs the same contract automatically.

Columns:

- `schema_version`: `nmrcp_rollback_plan_v1`.
- `workload_id`, `name`, `owner`, `target`, `wave`: workload and migration
  context.
- `move_plan_decision`, `stage_status`, `recovery_status`: readiness posture
  that drives the rollback decision.
- `rollback_owner`: named rollback/backout owner or `not confirmed`.
- `backup_protected`, `backup_last_success_hours`, `snapshot_count`,
  `oldest_snapshot_days`: recovery evidence for the change board.
- `rollback_status`: `ready`, `review`, `blocked`, or `hold`.
- `rollback_trigger`: stop or rollback criteria for the migration window.
- `required_action`: next step before Move staging or cutover approval.
- `evidence_refs`: related evidence files for operator review.

Operational use:

- Treat `ready` rows as rollback criteria to confirm during final change review.
- Treat `review` rows as conditional rollback evidence gaps.
- Treat `blocked` rows as stop conditions for included workloads.
- Treat `hold` rows as remediation evidence until workload readiness clears.
