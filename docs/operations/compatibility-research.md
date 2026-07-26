# Compatibility Research

`compatibility-research.csv` is generated with every assessment. It turns guest
OS and vendor target-support signals into a workload-level research queue for
AHV and NC2 migration review.

Validate it with:

```powershell
python -m nmrcp.cli validate-compatibility-research `
  --research outputs\sample-assessment\compatibility-research.csv `
  --assessment outputs\sample-assessment\assessment.json
```

The validator compares the CSV to the `nmrcp_compatibility_research_v1` context
embedded in `assessment.json`. `change-gate` runs the same contract
automatically.

Columns:

- `schema_version`: `nmrcp_compatibility_research_v1`.
- `workload_id`, `name`, `owner`, `target`, `readiness`, `tier`: workload and
  migration context.
- `guest_os`: captured operating system evidence.
- `guest_os_status`: `known_good`, `research_required`, or `missing`.
- `vendor_support`: declared target support values from metadata.
- `target_support_status`: `confirmed`, `unconfirmed`, `review`, or
  `not_declared`.
- `compatibility_status`: `ready`, `research`, or `blocked`.
- `blocking_findings`: normalized compatibility findings.
- `required_action`: next operator action before Move staging or approval.
- `evidence_refs`: related evidence files for reviewer traceability.

Operational use:

- Treat `ready` rows as support evidence to confirm during final change review.
- Treat `research` rows as vendor or application-owner follow-up before broad
  staging.
- Treat `blocked` rows as stop conditions until the missing guest OS evidence is
  collected.
