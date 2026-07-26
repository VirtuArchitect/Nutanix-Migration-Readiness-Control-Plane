# Target Capacity Fit

`target-capacity-fit.csv` is an optional assessment artifact that compares the
workloads included in `nutanix-move-plan.csv` with an approved target capacity
JSON file.

It answers: can the current Move staging list fit inside the AHV or NC2
capacity envelope that migration owners approved for this wave?

## Capacity Input

```json
{
  "schema_version": "nmrcp_target_capacity_v1",
  "targets": [
    {
      "target": "ahv",
      "cluster_name": "target-ahv-cluster",
      "usable_cpu_cores": 48,
      "cpu_overcommit_ratio": 1.0,
      "cpu_reserved_percent": 20,
      "usable_memory_gib": 384,
      "memory_reserved_percent": 25,
      "usable_storage_gib": 4096,
      "storage_reserved_percent": 30
    }
  ]
}
```

Use usable target capacity after platform reservations, failure-domain planning,
and any project-specific constraints have been reviewed by the Nutanix/platform
owner. Reserved percentages are applied on top of those usable numbers.

## Commands

Draft target capacity from Prism Central read-only cluster inventory:

```powershell
python -m nmrcp.cli collect-prism-capacity `
  --endpoint https://prism-central.example.com:9440 `
  --username admin `
  --out outputs\prism-capacity.json
```

The draft uses `/api/nutanix/v3/clusters/list`, records
`source.mutating_calls=0`, and keeps the capacity assumptions editable for
platform-owner review before approval.

Generate capacity fit during assessment:

```powershell
python -m nmrcp.cli assess `
  --inventory outputs\enriched-inventory.json `
  --capacity outputs\prism-capacity.json `
  --out outputs\sample-assessment
```

Validate or regenerate capacity fit from an existing Move staging plan:

```powershell
python -m nmrcp.cli validate-capacity `
  --inventory outputs\enriched-inventory.json `
  --plan outputs\sample-assessment\nutanix-move-plan.csv `
  --capacity outputs\prism-capacity.json `
  --out outputs\sample-assessment\target-capacity-fit.csv
```

`run-assessment` also accepts `--capacity` and includes
`target-capacity-fit.csv` in the evidence manifest, evidence bundle, and handoff
package.

## Gate Behavior

`change-gate` warns when `target-capacity-fit.csv` is absent. When the artifact
is present, any row with `status=fail` fails the gate.

The fit calculation only counts rows where `include_in_move_plan=yes`; held or
blocked workloads are not counted until they are remediated and included in a
future assessment.
