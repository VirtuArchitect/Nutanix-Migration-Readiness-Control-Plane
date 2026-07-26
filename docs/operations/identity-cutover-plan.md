# Identity Cutover Plan

`identity-cutover-plan.csv` is generated with every assessment. It captures the
hostname, DNS, source network, and redacted IP evidence operators need to prove a
workload still has the right identity after migration.

Validate it with:

```powershell
python -m nmrcp.cli validate-identity-cutover-plan `
  --plan outputs\sample-assessment\identity-cutover-plan.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The validator compares the CSV to the `nmrcp_identity_cutover_plan_v1` context
embedded in `assessment.json`. `change-gate` runs the same contract
automatically.

Columns:

- `schema_version`: `nmrcp_identity_cutover_plan_v1`.
- `workload_id`, `name`, `owner`, `target`, `wave`: workload and migration
  context.
- `move_plan_decision`, `readiness`: whether the workload is included or held.
- `hostname`, `dns_name`: captured guest identity evidence.
- `valid_ip_addresses`, `invalid_ip_addresses`: redacted IP evidence.
- `source_networks`: source VLAN, network, or port group hints.
- `identity_status`: `ready`, `review`, `blocked`, or `hold`.
- `required_action`: next step before staging or cutover approval.
- `evidence_refs`: related evidence files for operator review.

Operational use:

- Treat `ready` rows as the DNS/IPAM/hostname pre/post validation queue.
- Treat `review` rows as hostname or DNS ownership gaps before cutover.
- Treat `blocked` rows as stop conditions for included workloads.
- Treat `hold` rows as evidence to keep with remediation work until readiness
  clears.

Raw IP values are redacted in generated evidence. The plan preserves the
presence/validity signal without leaking customer addressing.
