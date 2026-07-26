# Partner Handoff Matrix

`partner-handoff-matrix.csv` is generated with every assessment. It maps the
assessment evidence set to the partner, MSP, customer, and operator roles that
must review it before migration handoff.

The artifact is local review evidence only. It does not create tickets, assign
tasks in external systems, send messages, or schedule Nutanix Move activity.

## Validate

```powershell
python -m nmrcp.cli validate-partner-handoff `
  --matrix outputs\sample-assessment\partner-handoff-matrix.csv `
  --assessment outputs\sample-assessment\assessment.json
```

`change-gate` runs the same validator. The CSV must match the handoff rows
recomputed from the `assessments` and `waves` in `assessment.json`, and the
embedded `partner_handoff_context` must match those same recomputed rows. This
prevents a stale or edited context block from making an externally blocked role
look ready. Validation also fails closed when assessment waves reference
unknown workload IDs or place the same workload in multiple waves, so role
owners cannot approve a handoff matrix built from invented or duplicated wave
membership.

## Roles

- `migration_lead`: evidence package, wave calendar, and gate completeness.
- `application_owner`: breakage report, stakeholder plan, workload validation,
  and sign-off.
- `platform_owner`: target readiness, capacity, staging readiness, and Prism
  category plan.
- `network_owner`: source networks, target mappings, connectivity, and identity
  preservation.
- `backup_and_rollback_owner`: recovery posture, rollback plan, snapshots, and
  validation criteria.
- `risk_and_change_board`: risk register, approval exceptions, executive brief,
  and launch readiness.
- `move_operator`: dry-run payload, submit-readiness proof, capture kit, and
  approved lab proof chain.

## Operating Notes

Use the matrix before packaging final handoff evidence. Rows with
`handoff_status=blocked` identify roles that still need remediation, approval,
or external proof before the package can be treated as externally ready.
