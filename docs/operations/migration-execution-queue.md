# Migration Execution Queue

`migration-execution-queue.csv` is generated with every assessment. It gives
operators one workload-level queue that rolls up wave order, Move-plan decision,
staging status, compatibility research, identity cutover readiness, dependency
connectivity, rollback readiness, and validation checklist status.

Validate it with:

```powershell
python -m nmrcp.cli validate-migration-execution-queue `
  --queue outputs\sample-assessment\migration-execution-queue.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The validator compares the CSV to the
`nmrcp_migration_execution_queue_v1` context embedded in `assessment.json`.
That embedded queue context must also match canonical assessment workload ID,
name, owner, target, readiness, risk score, and valid wave membership.
Validation fails closed when queue context references unknown workloads,
changes workload identity, or relies on unknown or duplicated wave membership.
`change-gate` runs the same contract automatically.

Columns:

- `schema_version`: `nmrcp_migration_execution_queue_v1`.
- `execution_order`: deterministic operator queue order.
- `workload_id`, `name`, `owner`, `target`, `wave`: workload and wave context.
- `move_plan_decision`, `stage_status`, `readiness`, `risk_score`: staging
  posture.
- `compatibility_status`, `identity_status`, `connectivity_status`,
  `rollback_status`, `validation_status`: supporting artifact rollups.
- `execution_status`: `ready`, `review`, or `hold`.
- `blocking_findings`: normalized reasons preventing execution approval.
- `required_action`: next operator action before staging, cutover, or closure.
- `evidence_refs`: source artifacts for reviewer traceability.

Operational use:

- Treat `ready` rows as candidates for Move staging precheck and lab-only
  payload review.
- Treat `review` rows as conditional execution items that need owner or
  migration-lead review before approval.
- Treat `hold` rows as stop conditions until readiness, dependency, identity,
  rollback, or validation blockers are closed.
