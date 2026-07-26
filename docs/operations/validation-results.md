# Validation Results

`pre-post-validation-checklist.md` is the human cutover checklist generated with
each assessment. Validate the generated checklist contract before handoff:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-validation-checklist `
  --checklist outputs\sample-assessment\pre-post-validation-checklist.md
```

The checklist contract requires pre-migration, cutover, and post-migration
sections, evidence capture, rollback criteria, and the stop condition for
excluded or blocked workloads.

Validation results convert the pre/post checklist into structured evidence that
can be reviewed before closing a migration change.

## Generate Template

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli generate-validation-template `
  --plan outputs\sample-assessment\nutanix-move-plan.csv `
  --out outputs\validation-results.template.csv
```

The template includes only workloads marked `include_in_move_plan=yes` in the
Move staging plan.

## Validate Draft Or Final Results

Draft review allows open checks:

```powershell
python -m nmrcp.cli validate-validation-results `
  --results outputs\validation-results.template.csv `
  --allow-open
```

Final validation fails closed on `not_checked` or `fail` rows:

```powershell
python -m nmrcp.cli validate-validation-results `
  --results examples\sample_validation_results.csv
```

Failed checks must include notes. Passed checks should include an `evidence_ref`
that points to a change ticket, screenshot, monitoring check, backup job, or
other approved evidence location.

## CSV Columns

```text
schema_version,source_vm_id,source_vm_name,phase,check_name,status,evidence_ref,validated_by,validated_at,notes
```

Allowed phases are `pre` and `post`. Allowed statuses are `pass`, `fail`,
`not_checked`, and `na`.
