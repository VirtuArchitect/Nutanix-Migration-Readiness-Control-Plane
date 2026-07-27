# Environment Access Gates

`environment-access` evaluates whether a requested connector target and
connectivity mode is allowed for the selected environment. It is a gate, not an
execution engine. Write mode records write intent and fails closed until the
required approvals are supplied.

Supported environments:

- `dev`
- `uat`
- `production`

Supported targets:

- `pc`: Prism Central
- `move`: Nutanix Move
- `vcenter`: vCenter
- `esxi`: ESXi

Supported modes:

- `read`
- `write`

## CLI

Validate a Dev read workflow:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli environment-access `
  --environment dev `
  --target vcenter `
  --mode read `
  --gate source_scope_approved `
  --gate credential_source_approved `
  --json-out outputs\environment-access.dev-read.json
```

Validate Production write intent for Prism Central:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli environment-access `
  --environment production `
  --target pc `
  --mode write `
  --gate source_scope_approved `
  --gate credential_source_approved `
  --gate change_reference=CHG-0001 `
  --gate rollback_plan `
  --gate write_scope_approved `
  --gate maintenance_window `
  --gate peer_review `
  --gate dry_run_passed `
  --gate cab_approval `
  --gate backup_verified `
  --gate production_write_break_glass `
  --gate business_owner_approval `
  --gate target_cluster_scope `
  --json-out outputs\environment-access.production-pc-write.json
```

## Gate Model

Read mode always requires:

- `source_scope_approved`
- `credential_source_approved`

Write mode always requires:

- `source_scope_approved`
- `credential_source_approved`
- `change_reference`
- `rollback_plan`
- `write_scope_approved`

Environment-specific gates add stricter control:

- Dev write: `operator_acknowledgement`
- UAT read: `change_reference`
- UAT write: `maintenance_window`, `peer_review`, `dry_run_passed`
- Production read: `change_reference`, `business_owner_approval`
- Production write: `maintenance_window`, `peer_review`, `dry_run_passed`,
  `cab_approval`, `backup_verified`, `production_write_break_glass`

Target write gates add connector-specific scope:

- Prism Central: `target_cluster_scope`
- Nutanix Move: `move_lab_or_approved_appliance`
- vCenter: `vm_scope_approved`
- ESXi: `host_scope_approved`

## Console

When served with `nmrcp serve`, the operations console exposes the same policy
through **Validate Environment Gates**. Operators select Dev, UAT, or Production,
choose read or write intent, select PC, Move, vCenter, or ESXi, and mark the
available gates. The console calls `/api/environment-access` and displays
missing gates before any connector workflow is run.

NMRCP still does not execute mutating actions from this workflow. The purpose is
to make read/write connectivity explicit and gated before future connector
submitters are added.
