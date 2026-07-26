# Move Lab Evidence Request

`move-lab-evidence-request.md` is generated with every assessment. It is the
partner, MSP, or change-board request for an approved non-production Nutanix Move
appliance proof window.

The request is intentionally not proof. It describes the lab-only dry-run scope,
workload counts, represented owners, required controls, redacted evidence chain,
closeout commands, and stop conditions needed before final external handoff can
claim Move appliance behavior has been proven.

## Validate

```powershell
python -m nmrcp.cli validate-move-lab-evidence-request `
  --request outputs\sample-assessment\move-lab-evidence-request.md
```

`change-gate` runs the same validation automatically.

## Required Content

The validator requires:

- non-production Nutanix Move appliance scope.
- dry-run-only submission.
- `started_migrations=0`.
- redacted evidence handling.
- `NMRCP_MOVE_LAB_ACK`.
- `proof_scope=approved_lab_move_appliance`.
- `nmrcp_move_lab_transcript_validation_v1`.
- `generate-approved-move-lab-proof`.
- `nmrcp_move_lab_proof_validation_v1`.
- `nmrcp_move_lab_evidence_intake_v1`.
- `validate-move-lab-proof`.
- `validate-move-lab-evidence-intake`.
- `--move-lab-evidence-intake`.

Use this artifact before the lab window. Use
`validate-move-lab-transcript`, `generate-approved-move-lab-proof`,
`validate-move-lab-proof`, and `validate-move-lab-evidence-intake` after the
approved lab capture to produce the actual final intake proof.
