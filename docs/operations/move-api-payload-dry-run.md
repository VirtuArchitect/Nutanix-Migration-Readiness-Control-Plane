# Move API Payload Dry Run

## Purpose

`generate-move-payload` turns a validated `nmrcp_move_plan_v1` CSV and a
user-provided mapping config into a dry-run JSON payload.

This command does not connect to Nutanix Move and does not submit anything. It
exists so migration operators can review the provider, target, network mapping,
schedule, and included-workload shape before any lab-only API integration is
enabled.

Payload generation refuses to run when an included workload network is missing
from `network_mappings`. Use
[target-network-mapping.md](target-network-mapping.md) to generate a reviewable
CSV proof before handoff.

Included workload records carry the Move plan's application-owner approval state
and rollback owner so reviewers can see governance proof without cross-opening
the CSV.

## Command

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli generate-move-payload `
  --plan outputs\smoke\nutanix-move-plan.csv `
  --config examples\sample_move_payload_config.json `
  --out outputs\smoke\move-api-payload.dry-run.json
```

## Config Shape

```json
{
  "plan_name": "NMRCP Pilot Wave 0",
  "source_provider": {
    "name": "vcenter-source-lab",
    "type": "vcenter",
    "uuid": "source-provider-placeholder"
  },
  "target_provider": {
    "name": "prism-central-target-lab",
    "type": "prism_central",
    "uuid": "target-provider-placeholder"
  },
  "target_cluster": {
    "name": "target-ahv-cluster",
    "uuid": "target-cluster-placeholder"
  },
  "target_container": {
    "name": "default-container",
    "uuid": "target-container-placeholder"
  },
  "network_mappings": [
    {
      "source_network": "120",
      "target_network": "vlan-120-ahv"
    }
  ],
  "schedule": {
    "mode": "manual",
    "timezone": "UTC",
    "start_immediately": false
  }
}
```

## Safety

- The command first validates `nutanix-move-plan.csv`.
- Invalid plans are refused.
- Only rows marked `include_in_move_plan=yes` are included.
- Included workload records include governance evidence from the Move staging
  plan.
- Generated JSON includes `dry_run_only: true` and `mutation_allowed: false`.
- There is no API submit command in the MVP.

## Next Step

Use [move-submit-readiness.md](move-submit-readiness.md) to fail-closed on
placeholder provider IDs, missing review evidence, missing network mapping
proof, or missing lab acknowledgement before any future lab-only submitter is
considered.
