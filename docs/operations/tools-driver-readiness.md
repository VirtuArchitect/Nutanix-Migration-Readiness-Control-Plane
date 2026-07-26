# Tools Driver Readiness

`tools-driver-readiness.csv` is generated with every assessment. It gives
operators a focused view of guest tools and Nutanix VirtIO readiness before
workloads are staged in Move.

## Validate

```powershell
python -m nmrcp.cli validate-tools-driver-readiness `
  --readiness outputs\sample-assessment\tools-driver-readiness.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The validator checks the CSV against the `nmrcp_tools_driver_readiness_v1`
context embedded in `assessment.json`. This catches stale or manually edited
driver-readiness rows before change-board handoff.

## Columns

- `schema_version`: `nmrcp_tools_driver_readiness_v1`.
- `workload_id`, `name`, `owner`, `target`, `readiness`: workload identity and
  current assessment state.
- `vmware_tools`: `true`, `false`, or `unknown`.
- `tools_status`: source tooling status when available.
- `virtio_ready`: `true`, `false`, or `unknown`.
- `driver_status`: `ready`, `research`, `remediate`, or `blocked`.
- `blocking_findings`: tools and driver finding codes from the assessment.
- `required_action`: operator remediation or validation action.
- `evidence_refs`: local evidence references for review.

## Gate Behavior

`change-gate` validates this artifact automatically. Remediation rows are valid
evidence; they do not fail the validator by themselves. They tell operators
which workloads need guest tools repair, tools upgrade, or Nutanix VirtIO driver
validation before Move staging.
