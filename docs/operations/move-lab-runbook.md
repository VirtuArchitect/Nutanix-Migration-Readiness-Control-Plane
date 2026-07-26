# Move Lab Execution Runbook

`generate-move-lab-runbook` creates a redacted Markdown runbook for the
approved Nutanix Move lab proof window. It does not submit to Move and does not
enable mutation. It turns the dry-run payload, submit review, and optional proof
template into an operator checklist with stop conditions and validation
commands.

## Generate

```powershell
$env:PYTHONPATH = "src"
python -m nmrcp.cli generate-move-lab-runbook `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --proof-template outputs\sample-assessment\move-lab-proof.template.json `
  --out outputs\sample-assessment\move-lab-execution-runbook.md

python -m nmrcp.cli validate-move-lab-runbook `
  --runbook outputs\sample-assessment\move-lab-execution-runbook.md
```

The runbook includes:

- required lab acknowledgement.
- pre-run gates.
- stop conditions.
- validation commands, including `generate-approved-move-lab-proof` and final
  `validate-move-lab-evidence-intake`.
- evidence to capture.
- workload scope by VM ID, wave, target, readiness, risk, and dependency count.
- submit-review approval status.
- proof-template state.

Endpoint-like values are redacted in the generated Markdown. Review the runbook
with `review-evidence` when it is generated inside an assessment directory.
When supplied to `package-mvp-proof`, it is archived as
`proof/move-lab-execution-runbook.md` and verified with the same
`validate-move-lab-runbook` contract. Package verification rejects stale
runbooks that omit final evidence intake, capture-kit validation, lab-only
acknowledgement, the approved proof generator, production stop conditions, or
redaction/secret handling.

Every assessment also writes `move-lab-closure-checklist.md`. Use that
assessment artifact before the lab window to verify the full closeout chain,
including final evidence intake and gate reruns with both `--move-proof` and
`--move-lab-evidence-intake`.

## Lab Closeout

After a real non-production Move appliance API round trip, validate the
redacted API transcript, generate the approved proof JSON from that transcript,
and run:

```powershell
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli validate-move-lab-transcript `
  --transcript outputs\move-lab-transcript.approved.json `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --out outputs\move-lab-transcript-validation.json
python -m nmrcp.cli generate-approved-move-lab-proof `
  --transcript outputs\move-lab-transcript.approved.json `
  --transcript-validation outputs\move-lab-transcript-validation.json `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --approved-by "[LAB_APPROVER]" `
  --out outputs\move-lab-proof.approved.json
python -m nmrcp.cli validate-move-lab-proof `
  --proof outputs\move-lab-proof.approved.json `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --transcript-validation outputs\move-lab-transcript-validation.json `
  --out outputs\move-lab-proof-validation.json
python -m nmrcp.cli validate-move-lab-evidence-intake `
  --payload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --transcript outputs\move-lab-transcript.approved.json `
  --transcript-validation outputs\move-lab-transcript-validation.json `
  --proof outputs\move-lab-proof.approved.json `
  --proof-validation outputs\move-lab-proof-validation.json `
  --capture-kit-validation outputs\move-lab-capture-kit-validation.json `
  --out outputs\move-lab-evidence-intake.json
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

Only a generated proof with `approved_lab_move_appliance`, a matching transcript
validation link, and passing validation should be supplied to
`mvp-audit --move-proof`. External handoff also requires passing
`--move-lab-evidence-intake`.
