# Source Network Validation

`validate-source-networks` verifies that every included Move-plan source network
hint exists in the collected vCenter network inventory before operators review
source-to-target mappings.

This catches stale VLAN hints, typoed network names, or Move-plan rows produced
from incomplete source evidence.

## Run

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-source-networks `
  --plan outputs\source-assessment\nutanix-move-plan.csv `
  --networks outputs\source-collection\vcenter-networks.json `
  --out outputs\source-assessment\source-network-validation.csv
python -m nmrcp.cli validate-source-network-results `
  --results outputs\source-assessment\source-network-validation.csv
```

## Inputs

- `nutanix-move-plan.csv`: generated Move staging plan.
- `vcenter-networks.json`: read-only source network inventory from
  `collect-sources`.

The validator matches included workload source network hints against vCenter
network IDs, names, VLAN IDs, and VLAN lists when those fields are present.

## Output

`source-network-validation.csv` uses schema
`nmrcp_source_network_validation_v1` and records one row per included workload
source network hint:

- `source_vm_id`
- `source_vm_name`
- `wave`
- `owner`
- `target`
- `source_network`
- `status`
- `notes`

Final review fails closed when any included workload network hint is not found
in the vCenter network inventory.
