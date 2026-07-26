# MVP Readiness Audit

`mvp-audit` writes a machine-readable matrix that maps the product MVP
requirements to current local evidence, verification commands, generated
artifacts, and remaining external proof gaps.

It is intentionally conservative. Local files, tests, docs, smoke scripts, and
generated artifacts can prove local implementation coverage. They do not prove
that real customer vCenter, Prism Central, or Nutanix Move environments have
been validated.

## Run

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli mvp-audit `
  --repo-root . `
  --assessment-dir outputs\smoke `
  --assessment-intake examples\sample_assessment_intake.csv `
  --live-proof outputs\source-collection\live-proof-validation.json `
  --evidence-bundle outputs\smoke-evidence-bundle.zip `
  --validation-results examples\sample_validation_results.csv `
  --remediation-tracker examples\sample_remediation_tracker_closed.csv `
  --signoffs examples\sample_owner_signoffs_approved.csv `
  --approval-exceptions examples\sample_approval_exceptions_approved.csv `
  --operator-review examples\sample_operator_review_approved.csv `
  --move-lab-capture-validation outputs\smoke\move-lab-capture-kit-validation.json `
  --warning-acceptance examples\sample_change_gate_warning_acceptance.csv `
  --move-proof outputs\move-lab-proof-validation.json `
  --out outputs\mvp-audit.json
```

Use `--json` to print the full payload:

```powershell
python -m nmrcp.cli mvp-audit --repo-root . --json
```

## Status

- `pass`: required local evidence files are present and no external proof gap is
  attached to the requirement.
- `partial`: local evidence exists, but a named external validation gap remains.
- `fail`: required local evidence files or expected assessment artifacts are
  missing, or a generated artifact contract fails validation.

When `--assessment-dir` contains `assessment.json`, the audit also validates
the generated assessment artifacts against their contracts. It checks migration
waves, wave summary, change-board evidence, migration runbook, dependency
review, connectivity checklist, identity cutover plan, compatibility research,
approval exceptions, risk register, business impact, tools driver readiness, storage posture,
recovery readiness, rollback plan, Move staging readiness, migration execution
queue, executive brief, operator report, operator dashboard, Move plan,
validation checklist, workload validation checklist, and the assessment change
gate. This means a stale or manually edited artifact can fail the MVP audit even
when the file is still present.

When final handoff evidence is supplied, the handoff-and-review requirement
uses the same closure gate as `change-gate`. Pass `--evidence-bundle`,
`--validation-results`, `--remediation-tracker`, `--signoffs`,
`--approval-exceptions`, `--operator-review`, and
`--move-lab-capture-validation` to prove that final validation, remediation,
owner approvals, exception approvals, human review, capture preflight, and
bundle integrity were evaluated instead of merely present.
When remaining warning-level gate findings have been reviewed, pass
`--warning-acceptance` with a CSV validated by `validate-warning-acceptance`.
The register must match the exact warnings from the final `change-gate --json`
run.

The expected whole-product status is `partial` until approved live vCenter,
Prism Central, and lab Nutanix Move validation evidence exists.

When `--live-proof` points to a passing `nmrcp_live_endpoint_proof_v1` file and
`--assessment-intake` points to a completed intake CSV, the read-only
vCenter/Prism requirement can move from `partial` to `pass`. The proof must be
the output of `validate-live-proof`, including passing checks for live readiness
security, collection summary privacy, assessment-intake binding, proof-manifest
security, API allowlist scope, and proof-manifest intake checksum match. A
status-only `nmrcp_live_endpoint_proof_v1` JSON file is rejected as stale proof.
Live proof without the completed intake remains `partial` because the collection
kickoff acknowledgements are not bound to the proof. The Nutanix Move appliance
gap remains separate.

When `--move-proof` points to a passing
`nmrcp_move_lab_proof_validation_v1` file whose `move-lab-proof-scope` check is
`approved_lab_move_appliance` and whose transcript validation link check passes,
the Move appliance proof gap can move from `partial` to `pass`. Simulated proof
or approved proof without transcript linkage does not retire this gap. Pair
approved proof with `--move-lab-evidence-intake` before external handoff so the
raw transcript, proof, validation files, and capture-kit validation are checked
together and reflected in the closure report.

## Covered Requirements

The audit covers:

- read-only vCenter and Prism Central collection.
- VM, network, storage, guest, snapshot, tools, tags, ownership, and dependency
  inventory scope.
- AHV/NC2 readiness scoring.
- migration waves and change-board evidence.
- Move-ready planning and pre/post validation checklist.
- local-secret handling and evidence redaction.
- validated handoff package and operator review.

The audit is included in the smoke script as `outputs\smoke-mvp-audit.json` so
each smoke run leaves behind an explicit product-readiness ledger. Smoke passes
closure evidence into the audit but still omits approved Move proof because the
local smoke proof is simulated. Smoke also accepts the remaining change-gate
warnings so `handoff_and_review` can be evaluated separately from the approved
Move appliance proof gap.
