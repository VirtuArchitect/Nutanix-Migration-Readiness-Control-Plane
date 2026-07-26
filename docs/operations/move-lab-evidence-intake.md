# Move Lab Evidence Intake

`validate-move-lab-evidence-intake` is the final approved-lab evidence intake
gate before retiring the Nutanix Move appliance proof gap. It ties together the
reviewed dry-run payload, Move submit review, captured approved-lab transcript,
transcript validation, completed approved proof, proof validation, and capture
kit validation.

It is intentionally fail-closed. Simulated proof, template-only transcripts,
missing transcript validation links, proof validation warnings, and capture-kit
validation errors all block intake.

`generate-move-lab-capture-kit` writes the same final intake command into
`move-lab-capture-checklist.md`, giving the lab operator a single checklist from
preflight transcript capture through `status=pass` evidence intake.

Run `move-lab-evidence-preflight` after capture-kit validation and before the
approved lab window. It checks Move submit readiness, capture-kit validation,
payload-hash linkage, planned approved transcript/proof paths, and writes the
remaining validation commands into a JSON and optional Markdown report.
Follow it with `move-lab-readiness-packet` to produce a single hash-addressed
operator handoff record for the pre-lab artifacts.

```powershell
$env:PYTHONPATH = "src"
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli move-lab-evidence-preflight `
  --payload outputs\smoke\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --capture-kit-validation outputs\smoke\move-lab-capture-kit-validation.json `
  --transcript outputs\move-lab-capture-kit\move-lab-transcript.approved.json `
  --transcript-validation outputs\move-lab-transcript-validation.json `
  --proof outputs\move-lab-proof.approved.json `
  --proof-validation outputs\move-lab-proof-validation.json `
  --evidence-intake outputs\move-lab-evidence-intake.json `
  --out outputs\move-lab-evidence-preflight.json `
  --report outputs\move-lab-evidence-preflight.md
```

The output schema is `nmrcp_move_lab_evidence_preflight_v1`. A passing preflight
does not replace final evidence intake; it only proves the lab capture inputs and
planned artifact paths are ready before the approved window starts.

## Run

```powershell
$env:PYTHONPATH = "src"
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli validate-move-lab-evidence-intake `
  --payload outputs\smoke\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --transcript outputs\move-lab-capture-kit\move-lab-transcript.approved.json `
  --transcript-validation outputs\move-lab-transcript-validation.json `
  --proof outputs\move-lab-proof.approved.json `
  --proof-validation outputs\move-lab-proof-validation.json `
  --capture-kit-validation outputs\smoke\move-lab-capture-kit-validation.json `
  --out outputs\move-lab-evidence-intake.json
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

The output schema is `nmrcp_move_lab_evidence_intake_v1`. When supplied to
`package-mvp-proof` with `--move-lab-evidence-intake`, it is archived as
`proof/move-lab-evidence-intake.json`. When supplied to `package-handoff` with
`--move-lab-evidence-intake`, it is archived as
`move/move-lab-evidence-intake.json`; approved Move lab proof handoff packages
require it. `change-gate`, `summarize-gates`, `mvp-audit`, and
`run-assessment` also accept `--move-lab-evidence-intake`; approved Move proof
fails final gating without passing intake evidence.

## Workflow Script

For approved lab runs, `scripts\move_lab_proof_workflow.ps1` can produce the
same intake artifact after proof validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\move_lab_proof_workflow.ps1 `
  -AssessmentDir outputs\smoke `
  -MovePayload outputs\smoke\move-api-payload.lab.dry-run.json `
  -MoveLabTranscript outputs\move-lab-capture-kit\move-lab-transcript.approved.json `
  -MoveLabTranscriptValidation outputs\move-lab-transcript-validation.json `
  -MoveLabProof outputs\move-lab-proof.approved.json `
  -GenerateApprovedProof `
  -ApprovedBy "Lab Migration Lead" `
  -MoveLabProofValidation outputs\move-lab-proof-validation.json `
  -MoveLabEvidenceIntake outputs\move-lab-evidence-intake.json `
  -MoveSubmitReview examples\sample_move_submit_review.json `
  -MoveLabCaptureKitValidation outputs\smoke\move-lab-capture-kit-validation.json `
  -LiveProof outputs\smoke-live-proof-validation.json `
  -MvpAudit outputs\smoke-mvp-audit.json
```

Do not use `-AllowSimulatedProof` for final evidence intake. Simulated proof is
acceptable only for local smoke packaging and must not be used to claim external
handoff readiness.

The smoke suite includes a separate generated-proof rehearsal that creates a
clean synthetic approved-lab transcript, generates approved proof from it, runs
proof validation, runs evidence intake, and verifies a rehearsal MVP proof
package. The rehearsal package proves the intake contract and packaging
mechanics without feeding synthetic evidence into the main smoke MVP proof
package. Real MVP closure still requires approved non-production Move appliance
evidence plus passing final intake.
