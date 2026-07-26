# Move Lab Proof Workflow Script

`scripts\move_lab_proof_workflow.ps1` runs the final Move lab proof checks in
the order an operator needs them: submit-readiness validation, optional
transcript-validation linkage, lab proof validation, approved-proof gate checks,
handoff packaging, MVP audit refresh, MVP proof packaging, closure-report
refresh, launch-readiness refresh, and package verification.

Use [move-lab-runbook.md](move-lab-runbook.md) before the lab window to generate
the redacted operator checklist from the reviewed dry-run payload.
After the capture kit passes validation, run `move-lab-evidence-preflight` to
prove the reviewed payload, submit review, capture-kit validation, planned
approved transcript path, planned proof path, and final evidence-intake path are
ready before the approved lab slot starts.

The script is intentionally fail-closed. It requires:

- `NMRCP_MOVE_LAB_ACK=I_UNDERSTAND_LAB_ONLY`.
- Existing assessment artifacts.
- A reviewed Move dry-run payload.
- A Move submit review file.
- Live endpoint proof validation.
- MVP audit output.
- A Move lab proof JSON record.
- A Move lab transcript validation file for approved lab proof.
- A Move lab evidence intake output path for approved lab proof.
- A Move lab capture-kit validation file when capture preflight evidence should
  be included in gate checks and proof packaging.
- A generated Move lab execution runbook when present.
- Final validation, remediation, sign-off, approval-exception, operator-review,
  evidence-bundle, and warning-acceptance artifacts when the operator wants the
  workflow to refresh handoff, MVP audit, and closure-report outputs in the
  approved lab run.

The workflow is rerun-safe for generated output files. Before writing refreshed
submit-readiness, proof-validation, evidence-intake, gate-summary, handoff,
MVP-audit, MVP-proof, closure-report Markdown, closure-report JSON,
launch-readiness Markdown, or launch-readiness JSON outputs, it removes the
existing file with a short retry loop. Required input files and directories are
still resolved as inputs and are not reset.

## Approved Lab Appliance Proof

Use this mode after a real non-production Nutanix Move appliance API round trip
has been completed and the evidence has been redacted:

```powershell
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
powershell -ExecutionPolicy Bypass -File scripts\move_lab_proof_workflow.ps1 `
  -AssessmentDir outputs\sample-assessment `
  -MovePayload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  -MoveLabTranscript outputs\move-lab-capture-kit\move-lab-transcript.approved.json `
  -MoveLabProof outputs\move-lab-proof.approved.json `
  -MoveLabTranscriptValidation outputs\move-lab-transcript-validation.json `
  -MoveLabEvidenceIntake outputs\move-lab-evidence-intake.json `
  -MoveSubmitReview examples\sample_move_submit_review.json `
  -LiveProof outputs\source-collection\live-proof-validation.json `
  -MvpAudit outputs\mvp-audit.json `
  -MoveLabRunbook outputs\sample-assessment\move-lab-execution-runbook.md `
  -MoveLabCaptureKitDir outputs\move-lab-capture-kit `
  -MoveLabCaptureKitValidation outputs\move-lab-capture-kit-validation.json `
  -EvidenceBundle outputs\evidence-bundle.zip `
  -ValidationResults examples\sample_validation_results.csv `
  -RemediationTracker examples\sample_remediation_tracker_closed.csv `
  -Signoffs examples\sample_owner_signoffs_approved.csv `
  -ApprovalExceptions examples\sample_approval_exceptions_approved.csv `
  -OperatorReview examples\sample_operator_review_approved.csv `
  -WarningAcceptance examples\sample_change_gate_warning_acceptance.csv `
  -HandoffPackage outputs\handoff-package.zip `
  -MvpProofPackage outputs\mvp-proof-package.zip `
  -MvpClosureReport outputs\mvp-closure-report.md `
  -MvpClosureReportJson outputs\mvp-closure-report.json `
  -LaunchReadinessReport outputs\launch-readiness-report.md `
  -LaunchReadinessReportJson outputs\launch-readiness-report.json `
  -LaunchRepoUrl https://github.com/VirtuArchitect/Nutanix-Migration-Readiness-Control-Plane
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

When the approved transcript has already validated cleanly, the workflow can
generate `move-lab-proof.approved.json` before proof validation:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\move_lab_proof_workflow.ps1 `
  -AssessmentDir outputs\sample-assessment `
  -MovePayload outputs\sample-assessment\move-api-payload.lab.dry-run.json `
  -MoveLabTranscript outputs\move-lab-capture-kit\move-lab-transcript.approved.json `
  -MoveLabTranscriptValidation outputs\move-lab-transcript-validation.json `
  -MoveLabProof outputs\move-lab-proof.approved.json `
  -GenerateApprovedProof `
  -ApprovedBy "Lab Migration Lead" `
  -MoveLabEvidenceIntake outputs\move-lab-evidence-intake.json `
  -MoveSubmitReview examples\sample_move_submit_review.json `
  -LiveProof outputs\source-collection\live-proof-validation.json `
  -MvpAudit outputs\mvp-audit.json `
  -MoveLabCaptureKitValidation outputs\move-lab-capture-kit-validation.json `
  -MvpProofPackage outputs\mvp-proof-package.zip
```

Approved proof must validate with `status=pass`,
`move-lab-proof-scope=approved_lab_move_appliance`, and a matching transcript
validation SHA-256 link. In that state the workflow also runs `summarize-gates`
and `change-gate` with the Move proof, capture-kit validation when supplied,
and the generated evidence intake. The workflow runs
`validate-move-lab-evidence-intake` before those gates and writes
`nmrcp_move_lab_evidence_intake_v1` evidence tying together the raw transcript,
transcript validation, proof, proof validation, and capture-kit validation.
When final review artifacts are supplied, the workflow also rebuilds and
verifies the handoff package, reruns `mvp-audit` with proof plus intake, packages
the refreshed MVP proof bundle, and rewrites the closure report so reviewers are
not looking at stale partial evidence. When `-MvpClosureReport` is supplied and
`-MvpClosureReportJson` is omitted, the workflow writes a sibling
`<report>.json` file and runs `validate-mvp-closure-report` against the refreshed
MVP proof package, Markdown report, and JSON report before completing. When
`-LaunchReadinessReport` is supplied and `-LaunchReadinessReportJson` is
omitted, the workflow writes a sibling `<report>.json` file and runs
`validate-launch-readiness-report` against the refreshed MVP proof package,
Markdown report, and JSON report. `-LaunchRepoUrl` and `-LaunchAudience` are
passed through to `launch-readiness-report` when supplied.
`-ExternalProofPlan` can package an already validated
`nmrcp_external_proof_plan_v1` record. For approved-proof runs,
`-ExternalProofPlanReport` and `-ExternalProofPlanJson` generate and validate a
matching external proof plan after proof validation and evidence intake exist,
then archive the JSON in the MVP proof package.
The generated closure commands continue from there by rerunning
`verify-mvp-proof`, `summarize-mvp-proof`, `validate-mvp-proof-summary`,
`validate-mvp-closure-report`, `launch-readiness-report`, and
`validate-launch-readiness-report` against the refreshed package.

Local smoke also runs an isolated generated-proof rehearsal using synthetic
approved-lab transcript evidence. That rehearsal writes
`outputs\smoke\move-lab-proof.generated-approved.json`,
`outputs\smoke\move-lab-proof-validation.generated-approved.json`,
`outputs\smoke\move-lab-evidence-intake.generated-proof-rehearsal.json`, and
`outputs\external-proof-plan.generated-proof-rehearsal.json`, then verifies
`outputs\smoke-generated-proof-rehearsal-package.zip` to prove the
`-GenerateApprovedProof` workflow mechanics and proof-package shape. These
artifacts are contract evidence only and must not be used as external handoff
proof or as a substitute for a real approved non-production Nutanix Move
appliance API round trip.

## Simulated Contract Proof

Use simulated mode only for local smoke or contract testing:

```powershell
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
powershell -ExecutionPolicy Bypass -File scripts\move_lab_proof_workflow.ps1 `
  -AssessmentDir outputs\smoke `
  -MovePayload outputs\smoke\move-api-payload.lab.dry-run.json `
  -MoveLabProof examples\sample_move_lab_proof_simulated.json `
  -MoveLabTranscriptValidation outputs\smoke\move-lab-transcript-validation.json `
  -MoveSubmitReview examples\sample_move_submit_review.json `
  -LiveProof outputs\smoke-live-proof-validation.json `
  -MvpAudit outputs\smoke-mvp-audit.json `
  -MoveLabRunbook outputs\smoke\move-lab-execution-runbook.md `
  -MvpProofPackage outputs\smoke-move-lab-workflow-proof-package.zip `
  -AllowSimulatedProof
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

Simulated proof is accepted for proof packaging only. Final change gate and
handoff readiness remain unproven until approved lab appliance proof is
supplied.
