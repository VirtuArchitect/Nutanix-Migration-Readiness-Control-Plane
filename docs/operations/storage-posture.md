# Storage Posture

`storage-posture.csv` is generated with every assessment. It gives operators a
focused view of source storage risks before workloads are staged in Nutanix Move.

## Validate

```powershell
python -m nmrcp.cli validate-storage-posture `
  --posture outputs\sample-assessment\storage-posture.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The validator checks the CSV against the `nmrcp_storage_posture_v1` context
embedded in `assessment.json`. This catches stale or manually edited storage
rows before change-board handoff.

## Columns

- `schema_version`: `nmrcp_storage_posture_v1`.
- `workload_id`, `name`, `owner`, `target`, `readiness`: workload identity and
  current assessment state.
- `disk_count`, `disk_gib`: source VM storage footprint.
- `thin_provisioned`: source thin-provisioning evidence.
- `raw_device_mapping`: RDM or raw disk evidence.
- `shared_disk`: shared or multi-writer disk evidence.
- `independent_disk`: independent disk evidence that may be excluded from
  snapshot-based workflows.
- `encrypted`: disk encryption evidence.
- `datastores`: source datastore or storage-container names.
- `min_datastore_free_percent`: lowest captured source datastore free-space
  percent.
- `storage_status`: `ready`, `review`, `remediate`, or `blocked`.
- `blocking_findings`: storage finding codes from the assessment.
- `required_action`: operator remediation or validation action.
- `evidence_refs`: local evidence references for review.

## Gate Behavior

`change-gate` validates this artifact automatically. Review, remediation, and
blocked rows are valid evidence; they do not fail the validator by themselves.
They tell storage owners what must be redesigned, approved, or verified before
Move staging.
