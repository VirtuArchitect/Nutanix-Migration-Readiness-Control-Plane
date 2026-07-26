# Dependency Review

`dependency-review.csv` is generated with every assessment. It gives migration
teams a workload-level dependency register that includes internal dependencies,
external services, dependency owners, criticality, staging impact, and imported
dependency records that did not match a workload.

## Validate

```powershell
python -m nmrcp.cli validate-dependency-review `
  --review outputs\sample-assessment\dependency-review.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The validator checks the CSV against the `nmrcp_dependency_review_v1` context
embedded in `assessment.json`. This catches stale or manually edited dependency
rows before change-board or partner handoff.

## Columns

- `schema_version`: `nmrcp_dependency_review_v1`.
- `row_type`: `dependency` or `unmatched_dependency`.
- `source_workload_id`, `source_name`, `source_owner`, `target`,
  `source_readiness`: source workload identity and readiness.
- `dependency_name`, `dependency_id`, `dependency_type`, `dependency_owner`,
  `criticality`: declared dependency facts.
- `dependency_scope`: `internal`, `external`, or `unmatched`.
- `dependency_readiness`: readiness of an internal dependency when it maps to an
  assessed workload.
- `stage_impact`: `ready`, `review`, `blocks_staging`, or `cleanup`.
- `blocking_findings`: normalized dependency blocker codes.
- `required_action`: operator action to clear or validate the dependency.
- `evidence_refs`: local evidence references for review.
- `notes`: imported dependency notes when supplied.

## Gate Behavior

`change-gate` validates this artifact automatically. Rows with
`blocks_staging`, `review`, or `cleanup` are valid evidence rows; they make
dependency ownership, ordering, and cleanup work explicit before Nutanix Move
staging is opened.
