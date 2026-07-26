# Move Lab Readiness Packet

`move-lab-readiness-packet` creates a pre-lab operator handoff record for the
remaining approved Nutanix Move proof window. It collects the reviewed dry-run
payload, submit review, submit-readiness proof, capture kit, capture-kit
validation, evidence preflight, runbook, evidence request, and closure checklist
into one hash-addressed JSON packet plus an optional Markdown report.

The packet is intentionally not external proof. It proves that the lab operator
has the right local, redacted, lab-only inputs before capture starts. Final MVP
closure still requires approved non-production Move appliance evidence,
`generate-approved-move-lab-proof`, proof validation, and passing evidence
intake.

## Run

```powershell
$env:PYTHONPATH = "src"
$env:NMRCP_MOVE_LAB_ACK = "I_UNDERSTAND_LAB_ONLY"
python -m nmrcp.cli move-lab-readiness-packet `
  --payload outputs\smoke\move-api-payload.lab.dry-run.json `
  --review examples\sample_move_submit_review.json `
  --move-submit-readiness outputs\smoke\move-submit-readiness.json `
  --capture-kit outputs\smoke\move-lab-capture-kit `
  --capture-kit-validation outputs\smoke\move-lab-capture-kit-validation.json `
  --evidence-preflight outputs\smoke\move-lab-evidence-preflight.json `
  --evidence-preflight-report outputs\smoke\move-lab-evidence-preflight.md `
  --runbook outputs\smoke\move-lab-execution-runbook.md `
  --evidence-request outputs\smoke\move-lab-evidence-request.md `
  --closure-checklist outputs\smoke\move-lab-closure-checklist.md `
  --out outputs\smoke\move-lab-readiness-packet.json `
  --report outputs\smoke\move-lab-readiness-packet.md

python -m nmrcp.cli validate-move-lab-readiness-packet `
  --packet outputs\smoke\move-lab-readiness-packet.json `
  --report outputs\smoke\move-lab-readiness-packet.md
Remove-Item Env:\NMRCP_MOVE_LAB_ACK
```

The JSON schema is `nmrcp_move_lab_readiness_packet_v1`. A passing packet
requires every artifact role to be present, SHA-256 hashed, and linked to
passing local validators where a validator exists. The packet report must state
that it is not external proof and must include the final closeout chain:
`validate-move-lab-transcript`, `generate-approved-move-lab-proof`,
`validate-move-lab-proof`, `validate-move-lab-evidence-intake`, and the MVP
audit rerun with `--move-proof --move-lab-evidence-intake`. The report
validator checks the Markdown against the packet JSON so every required
closeout entry and every artifact role remains visible to the lab operator.

When supplied to `package-mvp-proof` with `--move-lab-readiness-packet`, it is
archived as `proof/move-lab-readiness-packet.json` and semantically validated by
`verify-mvp-proof`. When supplied to `package-handoff` or `run-assessment`, it is
archived as `move/move-lab-readiness-packet.json` and semantically validated by
`verify-handoff`. This keeps the pre-lab operator handoff visible inside review
and receiver archives without treating it as approved Move appliance proof.

## CI And Smoke Boundary

Local smoke and GitHub Actions both generate and validate the readiness packet.
That proves the pre-lab handoff mechanics are reproducible in automation. It
does not replace the real approved lab evidence gate; hosted CI still packages
simulated proof for the main MVP proof bundle and keeps approved Move appliance
behavior as an external requirement.
