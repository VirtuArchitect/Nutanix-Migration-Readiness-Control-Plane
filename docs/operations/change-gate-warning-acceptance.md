# Change Gate Warning Acceptance

`validate-warning-acceptance` validates a filled CSV register that explicitly
accepts the warnings emitted by a `change-gate --json` run. It is intended for
reviewed closure evidence where a warning is understood and accepted, not for
removing the underlying risk from the assessment.

## Contract

The CSV schema is `nmrcp_change_gate_warning_acceptance_v1` and requires these
columns:

- `schema_version`
- `warning_text`
- `acceptance_status`
- `acceptance_ref`
- `accepted_by`
- `accepted_at`
- `notes`

Each expected warning must appear exactly once with
`acceptance_status=accepted`, an acceptance reference, approver, and timestamp.
Extra rows fail validation because they may refer to warnings from a different
gate run. Missing rows also fail validation.

## Run

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli change-gate `
  --dir outputs\smoke `
  --bundle outputs\smoke-evidence-bundle.zip `
  --validation-results examples\sample_validation_results.csv `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --signoffs examples\sample_owner_signoffs_approved.csv `
  --approval-exceptions examples\sample_approval_exceptions_approved.csv `
  --operator-review examples\sample_operator_review_approved.csv `
  --move-lab-capture-validation outputs\smoke\move-lab-capture-kit-validation.json `
  --json | Set-Content -LiteralPath outputs\smoke-change-gate-final.json -Encoding ASCII

python -m nmrcp.cli validate-warning-acceptance `
  --acceptance examples\sample_change_gate_warning_acceptance.csv `
  --warnings outputs\smoke-change-gate-final.json
```

Pass the accepted register to MVP audit when the handoff reviewer has formally
accepted every remaining change-gate warning:

```powershell
python -m nmrcp.cli mvp-audit `
  --repo-root . `
  --assessment-dir outputs\smoke `
  --evidence-bundle outputs\smoke-evidence-bundle.zip `
  --validation-results examples\sample_validation_results.csv `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --signoffs examples\sample_owner_signoffs_approved.csv `
  --approval-exceptions examples\sample_approval_exceptions_approved.csv `
  --operator-review examples\sample_operator_review_approved.csv `
  --move-lab-capture-validation outputs\smoke\move-lab-capture-kit-validation.json `
  --warning-acceptance examples\sample_change_gate_warning_acceptance.csv `
  --out outputs\mvp-audit.json
```

Accepted change-gate warnings can move the `handoff_and_review` MVP requirement
to `pass` when all structural gate checks pass. This does not retire separate
external proof gaps such as approved Nutanix Move appliance validation; those
remain governed by `mvp-audit --move-proof` and the MVP proof closure report.
