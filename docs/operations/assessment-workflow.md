# Assessment Workflow

`run-assessment` is the one-command operator path from normalized inventory to
verified handoff package. It reuses the same local validators as the individual
commands, so teams can run the full workflow in a migration factory without
stitching every step together by hand.

## Run

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli run-assessment `
  --inventory examples\sample_inventory.json `
  --metadata examples\sample_metadata.csv `
  --dependencies examples\sample_dependencies.csv `
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
  --out outputs\workflow-assessment
```

## Gates

The workflow runs these steps in order:

1. Inventory validation.
2. Optional metadata and dependency enrichment.
3. AHV or NC2 readiness scoring.
4. Wave, evidence, runbook, portal, report, dashboard, checklist, and Move staging
   export.
5. Move plan validation.
6. Validation-results template generation.
7. Optional target reconciliation against current Prism inventory.
8. Optional source network validation against collected vCenter network
   inventory.
9. Optional target network mapping validation and dry-run Move API payload
   generation.
10. Operator gate summary generation.
11. Evidence manifest verification and bundle packaging.
12. Change gate.
13. Final handoff package creation.

When `--remediation-tracker` is provided, the workflow validates final
remediation closure in the change gate and archives the reviewed tracker in the
handoff package. When `--signoffs` is provided, the workflow validates final
owner approvals, runs the sign-off closure gate, and archives the approved
sign-off matrix in the handoff package. When `--approval-exceptions` is
provided, the workflow validates final exception approval closure against the
generated assessment baseline and archives the filled register in the handoff
package. When `--operator-review` is provided, the workflow validates the
approved operator/customer assessment review and archives it in the handoff
package. When `--move-lab-capture-validation` is
provided, the workflow validates capture-kit preflight proof and includes it in
the change gate and operator gate summary. When `--move-lab-capture-kit` is
also supplied, the workflow archives the capture template, checklist, and
validation proof in the handoff package. When `--move-lab-proof` is provided,
the workflow validates approved non-production Move appliance proof and requires
`--move-lab-evidence-intake` for final change-gate proof. The workflow archives
both the proof validation and evidence intake in the handoff package. When
`--move-lab-readiness-packet` is provided, the workflow archives the pre-lab
operator readiness packet in the handoff package and `verify-handoff` validates
the packet schema, flags, artifact roles, and empty error list.

When `--source-networks` is provided, the workflow writes
`source-network-validation.csv`, includes it in the operator gate summary, and
fails before target mapping if an included Move-plan source network hint is not
present in collected vCenter network inventory.

Use `--strict-inventory` when warning-level inventory gaps should fail the run.
Use `--json` when the workflow result will be consumed by CI, a partner portal,
or a future UI.

## Output Defaults

- Assessment directory: value passed to `--out`.
- Validation template: `<assessment-dir>\validation-results.template.csv`.
- Source network validation: `<assessment-dir>\source-network-validation.csv`
  when `--source-networks` is provided.
- Dry-run Move payload: `<assessment-dir>\move-api-payload.dry-run.json` when
  `--move-config` is provided.
- Dependency review: `<assessment-dir>\dependency-review.csv`.
- Connectivity checklist: `<assessment-dir>\connectivity-checklist.csv`.
- Identity cutover plan: `<assessment-dir>\identity-cutover-plan.csv`.
- Compatibility research: `<assessment-dir>\compatibility-research.csv`.
- Tools driver readiness: `<assessment-dir>\tools-driver-readiness.csv`.
- Storage posture: `<assessment-dir>\storage-posture.csv`.
- Recovery readiness: `<assessment-dir>\recovery-readiness.csv`.
- Rollback plan: `<assessment-dir>\rollback-plan.csv`.
- Move staging readiness: `<assessment-dir>\move-staging-readiness.csv`.
- Move staging brief: `<assessment-dir>\move-staging-brief.md`.
- Move plan brief: `<assessment-dir>\move-plan-brief.md`.
- Wave execution calendar: `<assessment-dir>\wave-execution-calendar.csv`.
- Workload validation checklist: `<assessment-dir>\workload-validation-checklist.csv`.
- Migration execution queue: `<assessment-dir>\migration-execution-queue.csv`.
- Stakeholder communication plan: `<assessment-dir>\stakeholder-communication-plan.csv`.
- What will break report: `<assessment-dir>\what-will-break-report.csv`.
- What will break brief: `<assessment-dir>\what-will-break-brief.md`.
- Partner handoff matrix: `<assessment-dir>\partner-handoff-matrix.csv`.
- Approval exceptions: `<assessment-dir>\approval-exceptions.csv`.
- Evidence bundle: sibling `<assessment-dir-name>-evidence-bundle.zip`.
- Handoff package: sibling `<assessment-dir-name>-handoff-package.zip`.
- Operator portal: `<assessment-dir>\operator-portal.html`.
- Operator dashboard: `<assessment-dir>\operator-dashboard.html`.
- Operator gate summary: `<assessment-dir>\operator-gate-summary.md`.
- Move lab closure checklist: `<assessment-dir>\move-lab-closure-checklist.md`.

Run `mvp-audit` after workflow or smoke execution to generate a requirement
evidence ledger with explicit external proof gaps.

All generated artifacts remain local. The command does not call vCenter, Prism
Central, AHV, NC2, or Nutanix Move unless the input inventory has already been
collected by a separate read-only collector command.
