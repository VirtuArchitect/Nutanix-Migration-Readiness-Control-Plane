# Operator Gate Summary

`operator-gate-summary.md` is a compact human-readable summary of optional
evidence gates. It is designed for change-board packets and migration-factory
handoffs where reviewers need to see what was evaluated without opening every
CSV first.

## Generate

`run-assessment` writes the summary automatically after optional gate artifacts
are generated:

```powershell
python -m nmrcp.cli run-assessment `
  --inventory examples\sample_inventory.json `
  --capacity examples\sample_target_capacity.json `
  --prism-inventory examples\sample_prism_inventory.json `
  --source-networks outputs\source-collection\vcenter-networks.json `
  --move-config examples\sample_move_payload_config.json `
  --validation-results examples\sample_validation_results.csv `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --signoffs examples\sample_owner_signoffs_approved.csv `
  --approval-exceptions examples\sample_approval_exceptions_approved.csv `
  --operator-review examples\sample_operator_review_approved.csv `
  --move-lab-capture-kit outputs\move-lab-capture-kit `
  --move-lab-capture-validation outputs\move-lab-capture-kit-validation.json `
  --move-lab-proof outputs\move-lab-proof-validation.json `
  --move-lab-evidence-intake outputs\move-lab-evidence-intake.json `
  --out outputs\workflow-assessment
```

For standalone assessment runs, write it after generating optional artifacts:

```powershell
python -m nmrcp.cli summarize-gates `
  --dir outputs\sample-assessment `
  --validation-results examples\sample_validation_results.csv `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --signoffs examples\sample_owner_signoffs_approved.csv `
  --approval-exceptions examples\sample_approval_exceptions_approved.csv `
  --operator-review examples\sample_operator_review_approved.csv `
  --move-lab-capture-validation outputs\move-lab-capture-kit-validation.json `
  --move-lab-proof outputs\move-lab-proof-validation.json `
  --move-lab-evidence-intake outputs\move-lab-evidence-intake.json

python -m nmrcp.cli validate-operator-gate-summary `
  --summary outputs\sample-assessment\operator-gate-summary.md
```

## Gates

The summary reports:

- source endpoint evidence request.
- Move lab evidence request.
- target capacity fit.
- target reconciliation.
- source network validation.
- target network mapping.
- final validation results.
- final remediation closure.
- final owner sign-offs.
- approval exception closure.
- operator assessment review.
- Move lab capture kit.
- Move lab closure checklist.
- approved Move lab proof.
- Move lab evidence intake.

Each row is marked `pass`, `warn`, `fail`, `not evaluated`, or `not supplied`.
Warnings and errors are repeated below the table for reviewer scanning.
`validate-operator-gate-summary` verifies the required gate rows, allowed row
statuses, use guidance, and the rule that approved Move lab proof cannot be
marked `pass` unless Move lab evidence intake is also `pass`.

The source endpoint and Move lab evidence-request rows prove the generated
request artifacts still contain the required scope, privacy controls, closeout
commands, and stop conditions. They are preflight/change-board request checks;
they do not prove live endpoint collection or Nutanix Move execution completed.

The Move lab capture-kit row is a preflight proof for a later approved lab
capture window. It is not evidence that Nutanix Move accepted or started any
migration.
Approved Move lab proof should be reviewed with the evidence-intake row as a
pair; the change gate fails approved proof without passing intake evidence.

When supplied to `package-mvp-proof`, the summary is archived as
`proof/operator-gate-summary.md` and verified with the same contract.
