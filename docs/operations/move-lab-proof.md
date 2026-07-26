# Move Lab Proof

`validate-move-lab-proof` validates redacted evidence from non-production
Nutanix Move testing. It extends the existing dry-run payload and
submit-readiness checks with an explicit proof record for lab appliance
behavior.

The validator remains fail-closed:

- The payload must pass `validate-move-submit-readiness`.
- The proof must use schema `nmrcp_move_lab_proof_v1`.
- `environment` must be `lab`.
- `api_round_trip` and `dry_run_only` must be true.
- `mutation_performed` and `production_targets` must be false.
- approved proof must be linked to `move-lab-transcript-validation.json` by
  SHA-256; transcript warnings keep final proof in `warn` status.
- required operator approvals must all be true.
- proof text is scanned for URLs, IPs, emails, hostnames, and secret-like
  assignments.

## Simulated Contract Proof

Local smoke uses `proof_scope=simulated_contract` to prove the validator and
handoff contract. This is useful CI evidence, but it does not prove a real Move
appliance.

Generate a template first:

```powershell
python -m nmrcp.cli generate-move-lab-proof-template `
  --payload outputs\smoke\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --proof-scope simulated_contract `
  --out outputs\smoke\move-lab-proof.template.json
```

```powershell
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli validate-move-lab-proof `
  --proof examples\sample_move_lab_proof_simulated.json `
  --payload outputs\smoke\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --out outputs\smoke\move-lab-proof-validation.simulated.json
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

The expected status for simulated proof is `warn`.

## Approved Lab Appliance Proof

Only `proof_scope=approved_lab_move_appliance` should be used after a real
non-production Move appliance API round trip has been tested, reviewed, and
redacted. A passing validation file with that scope can be supplied to
`mvp-audit --move-proof` to retire the Move appliance proof gap.

Generate the approved proof from the cleaned transcript and passing transcript
validation so the validation SHA-256 and result counts are derived, not copied
by hand:

```powershell
python -m nmrcp.cli generate-approved-move-lab-proof `
  --payload outputs\smoke\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --transcript outputs\move-lab-capture-kit\move-lab-transcript.approved.json `
  --transcript-validation outputs\move-lab-transcript-validation.json `
  --approved-by "Lab Migration Lead" `
  --out outputs\move-lab-proof.approved.json
```

The generator refuses to run if submit readiness, transcript validation, current
transcript validation, payload hash linkage, `captured_approved_lab`, or
`started_migrations=0` checks are not clean. Then validate the generated proof
with the same transcript validation file:

```powershell
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli validate-move-lab-proof `
  --proof outputs\move-lab-proof.approved.json `
  --payload outputs\smoke\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --transcript-validation outputs\move-lab-transcript-validation.json `
  --out outputs\move-lab-proof-validation.json
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

For a stricter operator workflow that validates submit readiness, validates the
Move lab proof, runs approved-proof gates, and packages the MVP proof bundle,
use [move-lab-proof-workflow.md](move-lab-proof-workflow.md).

Before the lab window, generate the redacted operator runbook from the reviewed
payload and proof template with [move-lab-runbook.md](move-lab-runbook.md).

Draft the approved-lab proof record before the lab window, then fill it only
after the real lab evidence has been reviewed:

```powershell
python -m nmrcp.cli generate-move-lab-proof-template `
  --payload outputs\smoke\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --proof-scope approved_lab_move_appliance `
  --out outputs\move-lab-proof.template.json
```

```powershell
python -m nmrcp.cli mvp-audit `
  --repo-root . `
  --assessment-dir outputs\smoke `
  --live-proof outputs\source-collection\live-proof-validation.json `
  --move-proof outputs\move-lab-proof-validation.json `
  --out outputs\mvp-audit.json
```

Do not use production targets or real production migrations for MVP proof.

## Final Gates

Approved proof can also be supplied to the final change gate, operator gate
summary, handoff package, and one-command workflow:

```powershell
python -m nmrcp.cli change-gate `
  --dir outputs\sample-assessment `
  --move-lab-proof outputs\move-lab-proof-validation.json

python -m nmrcp.cli package-handoff `
  --dir outputs\sample-assessment `
  --move-lab-proof outputs\move-lab-proof-validation.json `
  --out outputs\sample-handoff-package.zip
```

These final gates require a passing validation file whose scope check is
`approved_lab_move_appliance`. Simulated proof is rejected for final handoff.
