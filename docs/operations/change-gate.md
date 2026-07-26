# Change Gate

`change-gate` runs the local approval checks that a migration team should pass
before treating an evidence package as change-board ready.

## Pre-Change Package Gate

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli change-gate `
  --dir outputs\sample-assessment `
  --bundle outputs\sample-evidence-bundle.zip
```

This verifies:

- required assessment artifacts.
- `assessment.json` readability.
- change-board evidence contract.
- wave execution calendar contract.
- partner handoff matrix contract.
- inventory coverage rows and included-workload critical coverage gaps.
- evidence manifest hashes and sizes.
- evidence redaction review.
- AHV/NC2 target comparison inclusion.
- dependency review contract.
- connectivity checklist contract.
- identity cutover plan contract.
- compatibility research contract.
- tools and VirtIO driver readiness contract.
- storage posture contract.
- remediation tracker inclusion.
- rollback plan contract.
- owner risk summary inclusion.
- approval exceptions contract.
- generated pre/post validation checklist contract.
- workload validation checklist contract.
- migration runbook operator contract.
- operator portal artifact-link contract.
- operator report HTML contract.
- operator dashboard payload contract.
- recovery readiness contract.
- Move staging readiness contract.
- migration execution queue contract.
- review-only Prism/NCM category mapping contract.
- review-only stakeholder communication plan contract.
- what-will-break report contract.
- Move staging plan validity.
- source network validation status when `source-network-validation.csv` is
  present.
- target network mapping status when `target-network-mapping.csv` is present.
- target capacity-fit status when `target-capacity-fit.csv` is present.
- target reconciliation status when `target-reconciliation.csv` is present.
- optional evidence bundle integrity.
- optional Move lab capture-kit validation proof when
  `--move-lab-capture-validation` is supplied.
- final Move lab evidence intake when `--move-lab-evidence-intake` is supplied.

It warns when validation results are not provided because this is a pre-change
package gate, not post-migration closure.

It fails when an included Move workload has critical inventory coverage gaps in
owner, guest OS, networking, guest identity, tools, backup, storage,
application-owner approval, or rollback-owner evidence. Held workloads with low
coverage warn so teams can drive enrichment before moving them toward staging.

It also warns when `source-network-validation.csv`,
`target-network-mapping.csv`, or `target-capacity-fit.csv` is not present
because source network proof, target network mappings, or cluster/container
headroom were not evaluated. When any of these artifacts is present, any row
with `status=fail` fails the gate.

It warns when `target-reconciliation.csv` is not present because current Prism
inventory collisions were not evaluated. When present, included workload name
collisions fail the gate.

## Closure Gate

```powershell
python -m nmrcp.cli change-gate `
  --dir outputs\sample-assessment `
  --bundle outputs\sample-evidence-bundle.zip `
  --validation-results examples\sample_validation_results.csv `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --signoffs examples\sample_owner_signoffs_approved.csv `
  --approval-exceptions examples\sample_approval_exceptions_approved.csv `
  --operator-review examples\sample_operator_review_approved.csv `
  --move-lab-capture-validation outputs\move-lab-capture-kit-validation.json `
  --move-lab-proof outputs\move-lab-proof-validation.json `
  --move-lab-evidence-intake outputs\move-lab-evidence-intake.json
```

The closure gate also validates final pre/post validation results, final
remediation closure, owner sign-offs, final approval exception closure,
operator assessment review, Move lab capture-kit preflight proof, and approved
Move lab proof with final evidence intake when supplied. It fails when final
validation contains unchecked or failed rows, when remediation rows are still
`open`, when sign-off rows are still `pending` or `rejected`, when approval
exception rows are unresolved, rejected, missing approval evidence, or no longer
match the assessment baseline, when the supplied operator review is not
approved, when capture-kit validation is not `pass`, when supplied Move lab
proof is simulated or not approved, or when approved proof is supplied without
`nmrcp_move_lab_evidence_intake_v1` evidence with `status=pass`.

`--move-lab-capture-validation` proves the lab capture kit was generated,
redacted, and still in template-only pre-capture state. It does not prove that a
real Nutanix Move appliance accepted the payload; use `--move-lab-proof` with
approved lab evidence and `--move-lab-evidence-intake` for that gate.

If `--remediation-tracker` is omitted, the gate warns that remediation closure
was not evaluated. Pre-change gates can omit it; closure gates should supply the
final reviewed tracker.

Use `--allow-pending-signoffs` only for draft owner-review gates. Use
`--allow-draft-operator-review` only when checking draft review packets before
final change-board handoff.

## Machine Output

```powershell
python -m nmrcp.cli change-gate --dir outputs\sample-assessment --json
```

Use JSON output for CI, partner factories, or future UI integration.
