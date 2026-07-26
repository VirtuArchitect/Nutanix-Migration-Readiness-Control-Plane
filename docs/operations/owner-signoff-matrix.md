# Owner Sign-Off Matrix

`owner-signoff-matrix.csv` is generated with every assessment. It gives the
migration lead a workload-level approval register before Move staging,
remediation closure, or change-board handoff.

Columns:

```text
status,owner,wave,workload_id,workload_name,target,readiness,risk_score,required_signoffs,blocking_reason,approval_due,evidence_refs,approval_ref,approved_by,approved_at,notes
```

Default `status` is `pending`. Operators can copy the CSV into a change request,
ticketing system, or owner-review workbook and update status externally without
modifying the generated evidence baseline.

Final `approved` or `waived` rows must include `approval_ref`, `approved_by`,
and `approved_at`. Use `notes` for waiver rationale or approval context,
especially when a held or high-risk workload is approved for lab review while
remaining excluded from Move execution.

Required sign-offs are derived from assessment evidence:

- `application_owner`, `migration_lead`, and `rollback_owner` are always
  required.
- `risk_acceptance` is required for `prepare` or `blocked` workloads and for
  critical or high-severity findings.
- `dependency_owner` is required when dependencies are present.
- `backup_owner` is required when backup proof is missing.
- `network_owner` is required for VDS or NSX/network mapping exposure.
- `storage_owner` is required for raw device mapping, shared disk, independent
  disk, or low source datastore free-space findings.
- `cloud_owner` is required for NC2-targeted workloads.

The matrix is included in `evidence-manifest.json`, evidence bundles, change
gate required artifacts, and final handoff packages.

## Validation

Validate the generated matrix against the canonical assessment before sending
it to owners:

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli validate-signoff-matrix `
  --matrix outputs\sample-assessment\owner-signoff-matrix.csv `
  --assessment outputs\sample-assessment\assessment.json
```

`assessment.json` includes a redacted `signoff_context` block so the validator
can verify dependency, backup, network, storage, risk, rollback, and cloud
approval roles without reopening source inventory.

Validate a draft filled matrix while rows are still pending:

```powershell
python -m nmrcp.cli validate-signoffs `
  --signoffs outputs\sample-assessment\owner-signoff-matrix.csv `
  --allow-pending
```

Validate a final approved matrix before closure:

```powershell
python -m nmrcp.cli validate-signoffs `
  --signoffs examples\sample_owner_signoffs_approved.csv
```

Final validation fails closed when a row is `pending` or `rejected`, or when an
`approved` or `waived` row is missing `approval_ref`, `approved_by`, or
`approved_at`. `waived` rows are allowed but should carry risk-acceptance review
and waiver rationale in `notes`. `change-gate` runs generated matrix validation
automatically, and runs final approval validation when `--signoffs` is supplied.
