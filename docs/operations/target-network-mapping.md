# Target Network Mapping

`target-network-mapping.csv` proves that every network hint on every workload
included in `nutanix-move-plan.csv` has a matching target network in the Move
payload config.

## Command

```powershell
python -m nmrcp.cli validate-network-mappings `
  --plan outputs\sample-assessment\nutanix-move-plan.csv `
  --config examples\sample_move_payload_config.json `
  --out outputs\sample-assessment\target-network-mapping.csv
```

The validator fails closed when an included workload has no network hints or
when any source network lacks a matching `network_mappings[].source_network`
entry in the Move payload config.

## Gate Behavior

`run-assessment --move-config` generates this artifact automatically before the
dry-run Move payload. `generate-move-payload` also refuses to produce a payload
when included workload networks are not mapped.

`change-gate` warns when `target-network-mapping.csv` is absent. When the
artifact is present, any row with `status=fail` fails the gate.

Held or blocked workloads are not evaluated because they are not included in the
Move staging plan.
