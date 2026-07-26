# Target Reconciliation

`target-reconciliation.csv` compares source workloads in the Move staging plan
with the current Prism inventory. It catches name collisions before operators
stage workloads in Nutanix Move.

## Generate

```powershell
python -m nmrcp.cli reconcile-target `
  --inventory outputs\source-collection\vcenter-inventory.json `
  --target-inventory outputs\source-collection\prism-inventory.json `
  --plan outputs\source-assessment\nutanix-move-plan.csv `
  --out outputs\source-assessment\target-reconciliation.csv
```

`run-assessment` can generate the same artifact when Prism inventory is
available:

```powershell
python -m nmrcp.cli run-assessment `
  --inventory outputs\source-collection\vcenter-inventory.json `
  --capacity outputs\source-collection\prism-capacity.json `
  --prism-inventory outputs\source-collection\prism-inventory.json `
  --out outputs\source-assessment
```

## Validate

```powershell
python -m nmrcp.cli validate-target-reconciliation `
  --reconciliation outputs\source-assessment\target-reconciliation.csv
```

Included workloads fail validation when their source VM name already exists in
Prism inventory. Held workloads with a name match warn so operators can decide
whether the target VM is an already-migrated workload, a naming collision, or an
unrelated native AHV/NC2 VM.

## Columns

- `source_vm_id` and `source_vm_name`: source workload identity from the Move
  staging plan.
- `move_decision`: `include` or `hold` after Move-plan decision normalization.
- `target_vm_id` and `target_vm_name`: matching Prism workload when present.
- `match_type`: currently `name` or `none`.
- `status`: `pass`, `warn`, or `fail`.
- `notes`: operator explanation for the reconciliation decision.

## Gate Behavior

When `target-reconciliation.csv` is present in an assessment directory,
`change-gate` validates it. Missing reconciliation warns because Prism inventory
collision checks were not evaluated.
