# Connectivity Checklist

`connectivity-checklist.csv` is generated with every assessment. It turns
dependency records into a workload-level queue for firewall, DNS, routing, and
application reachability validation before Nutanix Move staging or cutover.

Validate it with:

```powershell
python -m nmrcp.cli validate-connectivity-checklist `
  --checklist outputs\sample-assessment\connectivity-checklist.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The validator compares the CSV to the
`nmrcp_connectivity_checklist_v1` context embedded in `assessment.json`.
`change-gate` runs the same contract automatically.

Columns:

- `schema_version`: `nmrcp_connectivity_checklist_v1`.
- `source_workload_id`, `source_name`, `source_owner`: dependent workload.
- `target`, `source_readiness`: selected migration target and current readiness.
- `dependency_name`, `dependency_id`, `dependency_type`, `dependency_owner`:
  service or workload the source depends on.
- `criticality`, `direction`, `protocol`, `ports`: firewall and routing facts.
- `validation_method`: approved proof method, such as application owner test or
  synthetic probe.
- `connectivity_status`: `ready`, `needs_discovery`, `needs_validation_plan`, or
  `blocked`.
- `required_action`: next action before staging or cutover.
- `evidence_refs`, `notes`: source evidence and operator context.

Operational use:

- Treat `blocked` rows as stop conditions until an owner is assigned.
- Treat `needs_discovery` rows as firewall/DNS discovery work before Move
  staging.
- Treat `needs_validation_plan` rows as change-board gaps before cutover.
- Use `ready` rows as the pre/post connectivity validation queue.
