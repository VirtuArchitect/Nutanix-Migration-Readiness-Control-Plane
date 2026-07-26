# Move Staging Readiness

`move-staging-readiness.csv` and `move-staging-brief.md` are generated with
every assessment. The CSV gives migration leads a single workload-level queue
for deciding whether a VM can enter Nutanix Move staging, must stay on hold, or
needs conditional review. The Markdown brief turns those same rows into a
reviewer-ready include, hold, blocker, and evidence summary before anyone opens
Nutanix Move staging.

## Validate

```powershell
python -m nmrcp.cli validate-move-staging-readiness `
  --readiness outputs\sample-assessment\move-staging-readiness.csv `
  --assessment outputs\sample-assessment\assessment.json

python -m nmrcp.cli validate-move-staging-brief `
  --brief outputs\sample-assessment\move-staging-brief.md `
  --assessment outputs\sample-assessment\assessment.json
```

The validator checks the CSV against the `nmrcp_move_staging_readiness_v1`
context embedded in `assessment.json`. This catches stale or manually edited
staging rows before operator handoff. The brief validator renders
`nmrcp_move_staging_brief_v1` from the same context and rejects stale or
softened stop-condition language.

## Columns

- `schema_version`: `nmrcp_move_staging_readiness_v1`.
- `workload_id`, `name`, `owner`, `target`, `wave`: workload identity and
  migration grouping.
- `move_plan_decision`: `include` or `hold` based on the generated Move plan.
- `readiness`, `risk_score`: current scoring result.
- `tools_driver_status`, `storage_status`, `recovery_status`: downstream
  prerequisite evidence states.
- `application_owner_approval`, `rollback_owner`: governance facts required
  before staging.
- `stage_status`: `ready`, `conditional`, or `hold`.
- `blocking_findings`: normalized staging blocker codes.
- `required_action`: operator action to clear the row.
- `evidence_refs`: local evidence references for review.

## Gate Behavior

`change-gate` validates both artifacts automatically. Held and conditional rows
are valid evidence; they do not fail the validators by themselves. They make the
remaining owner, tools, storage, recovery, or readiness blocker explicit before
Move staging is opened.
