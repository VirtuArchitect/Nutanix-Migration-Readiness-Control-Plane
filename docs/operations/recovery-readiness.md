# Recovery Readiness

`recovery-readiness.csv` is generated with every assessment. It gives operators
a focused view of backup proof, snapshot cleanup, and rollback ownership before
workloads are staged in Nutanix Move.

## Validate

```powershell
python -m nmrcp.cli validate-recovery-readiness `
  --readiness outputs\sample-assessment\recovery-readiness.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The validator checks the CSV against the `nmrcp_recovery_readiness_v1` context
embedded in `assessment.json`. This catches stale or manually edited recovery
rows before change-board handoff. The embedded context must also match
canonical assessment workload ID, name, owner, target, readiness, findings-based
recovery status, blocking findings, required action, and evidence references
before recovery evidence is trusted.

## Columns

- `schema_version`: `nmrcp_recovery_readiness_v1`.
- `workload_id`, `name`, `owner`, `target`, `readiness`: workload identity and
  current assessment state.
- `backup_protected`: `true`, `false`, or `unknown`.
- `backup_last_success_hours`: age of the last successful backup when known.
- `snapshot_count`: source snapshot count.
- `oldest_snapshot_days`: age of the oldest snapshot when known.
- `oldest_snapshot_created_at`: source timestamp for the oldest snapshot when
  collected.
- `rollback_owner`: confirmed rollback owner or `not confirmed`.
- `recovery_status`: `ready`, `review`, `remediate`, or `blocked`.
- `blocking_findings`: backup, snapshot, and rollback finding codes.
- `required_action`: operator remediation or validation action.
- `evidence_refs`: local evidence references for review.

## Gate Behavior

`change-gate` validates this artifact automatically. Review, remediation, and
blocked rows are valid evidence; they do not fail the validator by themselves.
They tell application and backup owners what must be closed before Move staging
or production handoff.
